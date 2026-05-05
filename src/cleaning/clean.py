from gevent import monkey
monkey.patch_all()

import pandas as pd
import math
import zipfile
from pathlib import Path
from cassandra.cluster import Cluster
from cassandra.policies import RoundRobinPolicy
from cassandra.concurrent import execute_concurrent_with_args
from loguru import logger
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))
from config.settings import settings

log_path = Path(settings.log_dir)
log_path.mkdir(exist_ok=True)
logger.add(log_path / "cleaning.log", rotation="50 MB")

COLUMNS_MAP = {
    "Origin": "origin",
    "Dest": "dest",
    "FlightDate": "flight_date",
    "Marketing_Airline_Network": "marketing_airline",
    "Operating_Airline": "operating_airline",
    "Tail_Number": "tail_number",
    "Flight_Number_Operating_Airline": "flight_number",
    "DepDelay": "dep_delay",
    "ArrDelay": "arr_delay",
    "Cancelled": "cancelled",
    "CancellationCode": "cancellation_code",
    "Diverted": "diverted",
    "WeatherDelay": "weather_delay",
    "CarrierDelay": "carrier_delay",
    "NASDelay": "nas_delay",
    "SecurityDelay": "security_delay",
    "LateAircraftDelay": "late_aircraft_delay",
    "CRSDepTime": "crs_dep_time",
    "DepTime": "dep_time",
    "CRSArrTime": "crs_arr_time",
    "ArrTime": "arr_time",
    "TaxiOut": "taxi_out",
    "TaxiIn": "taxi_in",
    "CRSElapsedTime": "crs_elapsed_time",
    "ActualElapsedTime": "actual_elapsed_time",
    "AirTime": "air_time",
    "Distance": "distance",
    "OriginCityName": "origin_city",
    "OriginState": "origin_state",
    "DestCityName": "dest_city",
    "DestState": "dest_state",
    "Year": "year",
    "Month": "month",
    "DayofMonth": "day_of_month",
    "DayOfWeek": "day_of_week",
}

STRING_COLS = [
    "origin", "dest", "marketing_airline", "operating_airline",
    "tail_number", "flight_number", "cancellation_code",
    "crs_dep_time", "dep_time", "crs_arr_time", "arr_time",
    "origin_city", "dest_city", "origin_state", "dest_state",
    "delay_category"
]

DELAY_COLS = [
    "dep_delay", "arr_delay", "carrier_delay", "weather_delay",
    "nas_delay", "security_delay", "late_aircraft_delay",
    "taxi_out", "taxi_in", "crs_elapsed_time", "actual_elapsed_time",
    "air_time", "distance"
]


def connect_cassandra():
    logger.info("Connecting to Cassandra...")
    cluster = Cluster(
        [settings.cassandra_host],
        port=settings.cassandra_port,
        load_balancing_policy=RoundRobinPolicy(),
        protocol_version=4
    )
    session = cluster.connect(settings.cassandra_keyspace)
    logger.info("Connected successfully")
    return session


def safe_float(val: object, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        f = float(val)  # type: ignore[arg-type]
        return default if math.isnan(f) else f
    except (ValueError, TypeError):
        return default


def to_str_or_none(val) -> str | None:
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    s = str(val).strip()
    if s.lower() in ("nan", "none", ""):
        return None
    return s


def derive_delay_category(total_delay: float, cancelled: bool) -> str:
    if cancelled:
        return "CANCELLED"
    if total_delay <= 0:
        return "ON_TIME"
    if total_delay <= 15:
        return "MINOR"
    if total_delay <= 60:
        return "MODERATE"
    return "SEVERE"


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    # Strip column name whitespace
    df.columns = df.columns.str.strip()

    # Keep and rename only needed columns
    available = {k: v for k, v in COLUMNS_MAP.items() if k in df.columns}
    df = df[list(available.keys())].rename(columns=available)

    # Drop rows missing critical fields
    df = df.dropna(subset=["origin", "dest", "flight_date", "marketing_airline"])

    # Uppercase code columns
    for col in ["origin", "dest", "marketing_airline", "operating_airline",
                "origin_state", "dest_state"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.upper()

    # Convert flight number to string
    df["flight_number"] = df["flight_number"].apply(
        lambda x: None if pd.isna(x) else str(int(float(x)))
    )

    # Convert time columns to string
    for col in ["crs_dep_time", "dep_time", "crs_arr_time", "arr_time"]:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: None if pd.isna(x) else str(int(float(x)))
            )

    # Cancellation code
    df["cancellation_code"] = df["cancellation_code"].apply(
        lambda x: None if pd.isna(x) else str(x).strip().upper()
    )

    # Tail number
    df["tail_number"] = df["tail_number"].apply(
        lambda x: None if pd.isna(x) else str(x).strip()
    )

    # Boolean conversion
    df["cancelled"] = df["cancelled"].apply(lambda x: bool(safe_float(x)))
    df["diverted"] = df["diverted"].apply(lambda x: bool(safe_float(x)))

    # Fill delay columns with 0
    for col in DELAY_COLS:
        if col in df.columns:
            df[col] = df[col].apply(safe_float)

    # Derive total_delay
    df["total_delay"] = (
        df["carrier_delay"] + df["weather_delay"] +
        df["nas_delay"] + df["security_delay"] + df["late_aircraft_delay"]
    )

    # Derive delay_category
    df["delay_category"] = df.apply(
        lambda row: derive_delay_category(row["total_delay"], row["cancelled"]),
        axis=1
    )

    # Convert flight_date
    df["flight_date"] = pd.to_datetime(
        df["flight_date"], errors="coerce"
    ).dt.date

    # Convert int columns
    for col in ["year", "month", "day_of_month", "day_of_week"]:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: int(x) if pd.notna(x) else None
            )

    # Final pass — must be absolutely last thing before return
    for col in STRING_COLS:
        if col in df.columns:
            new_vals: list[str | None] = []            
            for val in df[col]:
                if val is None:
                    new_vals.append(None)
                elif isinstance(val, float):
                    new_vals.append(None)
                else:
                    s = str(val).strip()
                    new_vals.append(None if s.lower() in ("nan", "none", "") else s)
            # Use pd.array with object dtype to prevent None -> NaN conversion
            df[col] = pd.array(new_vals, dtype=object)

    return df


def safe_str(val):
    if val is None:
        return None
    if isinstance(val, float):
        return None
    s = str(val).strip()
    return None if s.lower() in ("nan", "none", "") else s


def insert_clean_batch(session, prepared, df: pd.DataFrame):
    params = []
    for _, row in df.iterrows():
        params.append((
            safe_str(row.get("origin")),
            safe_str(row.get("dest")),
            row.get("flight_date"),
            safe_str(row.get("marketing_airline")),
            safe_str(row.get("operating_airline")),
            safe_str(row.get("tail_number")),
            safe_str(row.get("flight_number")),
            row.get("dep_delay"),
            row.get("arr_delay"),
            row.get("cancelled"),
            safe_str(row.get("cancellation_code")),
            row.get("diverted"),
            row.get("weather_delay"),
            row.get("carrier_delay"),
            row.get("nas_delay"),
            row.get("security_delay"),
            row.get("late_aircraft_delay"),
            row.get("total_delay"),
            safe_str(row.get("delay_category")),
            safe_str(row.get("crs_dep_time")),
            safe_str(row.get("dep_time")),
            safe_str(row.get("crs_arr_time")),
            safe_str(row.get("arr_time")),
            row.get("taxi_out"),
            row.get("taxi_in"),
            row.get("crs_elapsed_time"),
            row.get("actual_elapsed_time"),
            row.get("air_time"),
            row.get("distance"),
            safe_str(row.get("origin_city")),
            safe_str(row.get("origin_state")),
            safe_str(row.get("dest_city")),
            safe_str(row.get("dest_state")),
            row.get("year"),
            row.get("month"),
            row.get("day_of_month"),
            row.get("day_of_week"),
        ))

    results = execute_concurrent_with_args(
        session, prepared, params, concurrency=200
    )

    errors = sum(1 for success, _ in results if not success)
    return len(params) - errors, errors


def main():
    session = connect_cassandra()

    prepared = session.prepare("""
        INSERT INTO flights_clean (
            origin, dest, flight_date, marketing_airline, operating_airline,
            tail_number, flight_number, dep_delay, arr_delay, cancelled,
            cancellation_code, diverted, weather_delay, carrier_delay, nas_delay,
            security_delay, late_aircraft_delay, total_delay, delay_category,
            crs_dep_time, dep_time, crs_arr_time, arr_time, taxi_out, taxi_in,
            crs_elapsed_time, actual_elapsed_time, air_time, distance,
            origin_city, origin_state, dest_city, dest_state,
            year, month, day_of_month, day_of_week
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """)

    data_dir = Path(settings.data_dir)
    zip_files = sorted(data_dir.glob("*.zip"))

    if not zip_files:
        logger.error(f"No zip files found in {data_dir}")
        return

    logger.info(f"Found {len(zip_files)} zip files to clean")

    total_inserted = 0
    total_errors = 0

    for zip_path in zip_files:
        logger.info(f"Cleaning {zip_path.name}")
        file_inserted = 0
        file_errors = 0

        try:
            with zipfile.ZipFile(zip_path, "r") as z:
                csv_name = [f for f in z.namelist() if f.endswith(".csv")][0]
                with z.open(csv_name) as f:
                    for chunk in pd.read_csv(f, low_memory=False, chunksize=50000):
                        try:
                            cleaned = clean_dataframe(chunk)
                            inserted, errors = insert_clean_batch(
                                session, prepared, cleaned
                            )
                            file_inserted += inserted
                            file_errors += errors
                        except Exception as e:
                            logger.warning(f"Chunk error in {zip_path.name}: {e}")
                            file_errors += len(chunk)

            total_inserted += file_inserted
            total_errors += file_errors
            logger.info(
                f"Finished {zip_path.name} — "
                f"inserted: {file_inserted}, errors: {file_errors}"
            )

        except Exception as e:
            logger.error(f"Failed to process {zip_path.name}: {e}")

    logger.info(
        f"Cleaning complete — "
        f"total inserted: {total_inserted}, total errors: {total_errors}"
    )


if __name__ == "__main__":
    main()
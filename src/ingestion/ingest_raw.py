from gevent import monkey
monkey.patch_all()

import zipfile
import pandas as pd
from pathlib import Path
from cassandra.cluster import Cluster
from cassandra.policies import RoundRobinPolicy
from loguru import logger
import sys
import time

sys.path.append(str(Path(__file__).resolve().parents[2]))
from config.settings import settings
from src.models.flight import FlightRaw

# Setup logging
log_path = Path(settings.log_dir)
log_path.mkdir(exist_ok=True)
logger.add(log_path / "ingestion.log", rotation="50 MB", retention="10 days")

COLUMNS_TO_KEEP = {
    "Origin": "origin",
    "Dest": "dest",
    "FlightDate": "flight_date",
    "Marketing_Airline_Network": "marketing_airline",
    "Operating_Airline ": "operating_airline",
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

INSERT_QUERY = """
INSERT INTO flights_raw (
    origin, dest, flight_date, marketing_airline, operating_airline,
    tail_number, flight_number, dep_delay, arr_delay, cancelled,
    cancellation_code, diverted, weather_delay, carrier_delay, nas_delay,
    security_delay, late_aircraft_delay, crs_dep_time, dep_time,
    crs_arr_time, arr_time, taxi_out, taxi_in, crs_elapsed_time,
    actual_elapsed_time, air_time, distance, origin_city, origin_state,
    dest_city, dest_state, year, month, day_of_month, day_of_week
) VALUES (
    %(origin)s, %(dest)s, %(flight_date)s, %(marketing_airline)s, %(operating_airline)s,
    %(tail_number)s, %(flight_number)s, %(dep_delay)s, %(arr_delay)s, %(cancelled)s,
    %(cancellation_code)s, %(diverted)s, %(weather_delay)s, %(carrier_delay)s, %(nas_delay)s,
    %(security_delay)s, %(late_aircraft_delay)s, %(crs_dep_time)s, %(dep_time)s,
    %(crs_arr_time)s, %(arr_time)s, %(taxi_out)s, %(taxi_in)s, %(crs_elapsed_time)s,
    %(actual_elapsed_time)s, %(air_time)s, %(distance)s, %(origin_city)s, %(origin_state)s,
    %(dest_city)s, %(dest_state)s, %(year)s, %(month)s, %(day_of_month)s, %(day_of_week)s
)
"""


def connect_cassandra():
    logger.info("Connecting to Cassandra...")
    cluster = Cluster(
        [settings.cassandra_host],
        port=settings.cassandra_port,
        load_balancing_policy=RoundRobinPolicy(),
        protocol_version=4
    )
    session = cluster.connect(settings.cassandra_keyspace)
    logger.info("Connected to Cassandra successfully")
    return session


def read_zip(zip_path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(zip_path, "r") as z:
        csv_name = [f for f in z.namelist() if f.endswith(".csv")][0]
        with z.open(csv_name) as f:
            df = pd.read_csv(f, low_memory=False)
    return df


def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    # Strip whitespace from column names
    df.columns = df.columns.str.strip()

    # Rebuild column map with stripped names
    stripped_map = {k.strip(): v for k, v in COLUMNS_TO_KEEP.items()}

    # Keep only needed columns that exist
    available = {k: v for k, v in stripped_map.items() if k in df.columns}
    df = df[list(available.keys())].rename(columns=available)

    # Drop completely empty rows
    df = df.dropna(subset=["origin", "dest", "flight_date", "marketing_airline"])

    # Convert flight_date
    df["flight_date"] = pd.to_datetime(df["flight_date"], errors="coerce").dt.date

    # Convert time columns to string
    for col in ["crs_dep_time", "dep_time", "crs_arr_time", "arr_time"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df


def ingest_file(session, zip_path: Path):
    logger.info(f"Processing {zip_path.name}")
    bad_records = 0
    inserted = 0

    try:
        df = read_zip(zip_path)
        df = prepare_dataframe(df)
        logger.info(f"{zip_path.name} — {len(df)} rows after preparation")

        for batch_start in range(0, len(df), 1000):
            batch = df.iloc[batch_start:batch_start + 1000]
            for _, row in batch.iterrows():
                try:
                    record = FlightRaw(**row.to_dict())
                    session.execute(INSERT_QUERY, record.model_dump())
                    inserted += 1
                except Exception as e:
                    bad_records += 1
                    logger.warning(f"Bad record skipped: {e}")

            if batch_start % 50000 == 0:
                logger.info(f"  Progress: {batch_start}/{len(df)} rows")

        logger.info(f"Finished {zip_path.name} — inserted: {inserted}, skipped: {bad_records}")

    except Exception as e:
        logger.error(f"Failed to process {zip_path.name}: {e}")


def main():
    session = connect_cassandra()
    data_dir = Path(settings.data_dir)
    zip_files = sorted(data_dir.glob("*.zip"))

    if not zip_files:
        logger.error(f"No zip files found in {data_dir}")
        return

    logger.info(f"Found {len(zip_files)} zip files to ingest")

    for zip_path in zip_files:
        ingest_file(session, zip_path)
        time.sleep(1)

    logger.info("All files ingested successfully")


if __name__ == "__main__":
    main()
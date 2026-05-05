from gevent import monkey
monkey.patch_all()

import pandas as pd
import zipfile
import math
from pathlib import Path
from cassandra.cluster import Cluster
from cassandra.policies import RoundRobinPolicy
from cassandra.concurrent import execute_concurrent_with_args
from loguru import logger
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))
from config.settings import settings
from src.cleaning.clean import clean_dataframe

log_path = Path(settings.log_dir)
log_path.mkdir(exist_ok=True)
logger.add(log_path / "aggregation.log", rotation="50 MB")


def connect_cassandra():
    cluster = Cluster(
        [settings.cassandra_host],
        port=settings.cassandra_port,
        load_balancing_policy=RoundRobinPolicy(),
        protocol_version=4
    )
    return cluster.connect(settings.cassandra_keyspace)


def load_all_data() -> pd.DataFrame:
    logger.info("Loading all zip files for aggregation...")
    data_dir = Path(settings.data_dir)
    zip_files = sorted(data_dir.glob("*.zip"))
    chunks = []

    for zip_path in zip_files:
        logger.info(f"Reading {zip_path.name}")
        with zipfile.ZipFile(zip_path, "r") as z:
            csv_name = [f for f in z.namelist() if f.endswith(".csv")][0]
            with z.open(csv_name) as f:
                for chunk in pd.read_csv(f, low_memory=False, chunksize=50000):
                    cleaned = clean_dataframe(chunk)
                    chunks.append(cleaned)

    df = pd.concat(chunks, ignore_index=True)
    logger.info(f"Loaded {len(df)} total rows for aggregation")
    return df


def aggregate_carrier_performance(df: pd.DataFrame, session):
    logger.info("Aggregating carrier performance by month...")

    agg = df.groupby(["marketing_airline", "year", "month"]).agg(
        total_flights=("flight_number", "count"),
        cancelled_flights=("cancelled", "sum"),
        diverted_flights=("diverted", "sum"),
        avg_dep_delay=("dep_delay", "mean"),
        avg_arr_delay=("arr_delay", "mean"),
    ).reset_index()

    agg["on_time_rate"] = (
        (agg["total_flights"] - agg["cancelled_flights"]) / agg["total_flights"] * 100
    ).round(2)

    prepared = session.prepare("""
        INSERT INTO carrier_performance_monthly (
            airline, year, month, total_flights, cancelled_flights,
            diverted_flights, avg_dep_delay, avg_arr_delay, on_time_rate
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """)

    params = [
        (
            row["marketing_airline"],
            int(row["year"]),
            int(row["month"]),
            int(row["total_flights"]),
            int(row["cancelled_flights"]),
            int(row["diverted_flights"]),
            float(row["avg_dep_delay"]),
            float(row["avg_arr_delay"]),
            float(row["on_time_rate"]),
        )
        for _, row in agg.iterrows()
    ]

    execute_concurrent_with_args(session, prepared, params, concurrency=100)
    logger.info(f"Carrier performance complete — {len(agg)} records written")


def aggregate_route_delays(df: pd.DataFrame, session):
    logger.info("Aggregating route delay summaries...")

    agg = df.groupby(["origin", "dest", "year"]).agg(
        total_flights=("flight_number", "count"),
        avg_arr_delay=("arr_delay", "mean"),
        avg_weather_delay=("weather_delay", "mean"),
        avg_carrier_delay=("carrier_delay", "mean"),
        avg_nas_delay=("nas_delay", "mean"),
        cancelled_flights=("cancelled", "sum"),
    ).reset_index()

    agg["cancellation_rate"] = (
        agg["cancelled_flights"] / agg["total_flights"] * 100
    ).round(2)

    prepared = session.prepare("""
        INSERT INTO route_delay_summary (
            origin, dest, year, total_flights, avg_arr_delay,
            avg_weather_delay, avg_carrier_delay, avg_nas_delay, cancellation_rate
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """)

    params = [
        (
            row["origin"],
            row["dest"],
            int(row["year"]),
            int(row["total_flights"]),
            float(row["avg_arr_delay"]),
            float(row["avg_weather_delay"]),
            float(row["avg_carrier_delay"]),
            float(row["avg_nas_delay"]),
            float(row["cancellation_rate"]),
        )
        for _, row in agg.iterrows()
    ]

    execute_concurrent_with_args(session, prepared, params, concurrency=100)
    logger.info(f"Route delay complete — {len(agg)} records written")


def aggregate_seasonal_delays(df: pd.DataFrame, session):
    logger.info("Aggregating seasonal delays by state...")

    df["quarter"] = ((df["month"] - 1) // 3 + 1).astype(int)

    agg = df.groupby(["origin_state", "year", "quarter"]).agg(
        total_flights=("flight_number", "count"),
        avg_weather_delay=("weather_delay", "mean"),
        avg_total_delay=("total_delay", "mean"),
        cancelled_flights=("cancelled", "sum"),
    ).reset_index()

    agg["cancellation_rate"] = (
        agg["cancelled_flights"] / agg["total_flights"] * 100
    ).round(2)

    prepared = session.prepare("""
        INSERT INTO seasonal_delay_by_state (
            origin_state, year, quarter, total_flights,
            avg_weather_delay, avg_total_delay, cancellation_rate
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """)

    params = [
        (
            row["origin_state"],
            int(row["year"]),
            int(row["quarter"]),
            int(row["total_flights"]),
            float(row["avg_weather_delay"]),
            float(row["avg_total_delay"]),
            float(row["cancellation_rate"]),
        )
        for _, row in agg.iterrows()
        if row["origin_state"] is not None
    ]

    execute_concurrent_with_args(session, prepared, params, concurrency=100)
    logger.info(f"Seasonal delay complete — {len(agg)} records written")


def main():
    session = connect_cassandra()
    df = load_all_data()

    aggregate_carrier_performance(df, session)
    aggregate_route_delays(df, session)
    aggregate_seasonal_delays(df, session)

    logger.info("All aggregations complete")


if __name__ == "__main__":
    main()
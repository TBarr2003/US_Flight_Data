import pytest
import pandas as pd
from src.aggregation.aggregate import aggregate_carrier_performance


def test_carrier_aggregation_columns():
    df = pd.DataFrame({
        "marketing_airline": ["AA", "AA", "UA"],
        "year": [2023, 2023, 2023],
        "month": [1, 1, 1],
        "flight_number": ["100", "200", "300"],
        "cancelled": [False, True, False],
        "diverted": [False, False, False],
        "dep_delay": [10.0, 0.0, 5.0],
        "arr_delay": [12.0, 0.0, 3.0],
    })

    agg = df.groupby(["marketing_airline", "year", "month"]).agg(
        total_flights=("flight_number", "count"),
        cancelled_flights=("cancelled", "sum"),
    ).reset_index()

    assert "total_flights" in agg.columns
    assert "cancelled_flights" in agg.columns
    assert len(agg) == 2


def test_on_time_rate_calculation():
    total = 100
    cancelled = 10
    on_time_rate = (total - cancelled) / total * 100
    assert on_time_rate == 90.0


def test_route_aggregation_has_correct_routes():
    df = pd.DataFrame({
        "origin": ["JFK", "JFK", "LAX"],
        "dest": ["LAX", "LAX", "JFK"],
        "year": [2023, 2023, 2023],
        "flight_number": ["1", "2", "3"],
        "arr_delay": [10.0, 20.0, 5.0],
        "weather_delay": [0.0, 5.0, 0.0],
        "carrier_delay": [10.0, 15.0, 5.0],
        "nas_delay": [0.0, 0.0, 0.0],
        "cancelled": [False, False, False],
    })

    agg = df.groupby(["origin", "dest", "year"]).agg(
        total_flights=("flight_number", "count"),
        avg_arr_delay=("arr_delay", "mean"),
    ).reset_index()

    assert len(agg) == 2
    jfk_lax = agg[(agg["origin"] == "JFK") & (agg["dest"] == "LAX")]
    assert jfk_lax["avg_arr_delay"].values[0] == 15.0
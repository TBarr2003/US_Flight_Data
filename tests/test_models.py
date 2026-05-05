import pytest
from datetime import date
from src.models.flight import FlightRaw


def test_valid_flight():
    flight = FlightRaw(
        origin="JFK",
        dest="LAX",
        flight_date=date(2023, 1, 15),
        marketing_airline="AA",
        operating_airline="AA",
        flight_number="100"
    )
    assert flight.origin == "JFK"
    assert flight.dest == "LAX"


def test_origin_uppercased():
    flight = FlightRaw(
        origin="jfk",
        dest="lax",
        flight_date=date(2023, 1, 15),
        marketing_airline="aa",
        operating_airline="aa"
    )
    assert flight.origin == "JFK"
    assert flight.marketing_airline == "AA"


def test_empty_origin_raises():
    with pytest.raises(Exception):
        FlightRaw(
            origin="",
            dest="LAX",
            flight_date=date(2023, 1, 15),
            marketing_airline="AA",
            operating_airline="AA"
        )


def test_nan_cancellation_code_becomes_none():
    flight = FlightRaw(
        origin="JFK",
        dest="LAX",
        flight_date=date(2023, 1, 15),
        marketing_airline="AA",
        operating_airline="AA",
        cancellation_code=float("nan")
    )
    assert flight.cancellation_code is None


def test_flight_number_coerced_to_string():
    flight = FlightRaw(
        origin="JFK",
        dest="LAX",
        flight_date=date(2023, 1, 15),
        marketing_airline="AA",
        operating_airline="AA",
        flight_number=1447
    )
    assert flight.flight_number == "1447"
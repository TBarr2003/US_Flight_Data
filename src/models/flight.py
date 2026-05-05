from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import date
import math


class FlightRaw(BaseModel):
    origin: str
    dest: str
    flight_date: date
    marketing_airline: str
    operating_airline: str
    tail_number: Optional[str] = None
    flight_number: Optional[str] = None
    dep_delay: Optional[float] = None
    arr_delay: Optional[float] = None
    cancelled: Optional[float] = None
    cancellation_code: Optional[str] = None
    diverted: Optional[float] = None
    weather_delay: Optional[float] = None
    carrier_delay: Optional[float] = None
    nas_delay: Optional[float] = None
    security_delay: Optional[float] = None
    late_aircraft_delay: Optional[float] = None
    crs_dep_time: Optional[str] = None
    dep_time: Optional[str] = None
    crs_arr_time: Optional[str] = None
    arr_time: Optional[str] = None
    taxi_out: Optional[float] = None
    taxi_in: Optional[float] = None
    crs_elapsed_time: Optional[float] = None
    actual_elapsed_time: Optional[float] = None
    air_time: Optional[float] = None
    distance: Optional[float] = None
    origin_city: Optional[str] = None
    origin_state: Optional[str] = None
    dest_city: Optional[str] = None
    dest_state: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    day_of_month: Optional[int] = None
    day_of_week: Optional[int] = None

    @field_validator("origin", "dest", "marketing_airline", "operating_airline")
    @classmethod
    def must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field must not be empty")
        return v.strip().upper()

    @field_validator("flight_date", mode="before")
    @classmethod
    def parse_date(cls, v) -> date:
        if isinstance(v, date):
            return v
        try:
            from datetime import datetime
            return datetime.strptime(str(v), "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(f"Invalid date format: {v}")

    @field_validator(
    "flight_number", "cancellation_code", "tail_number",
    "crs_dep_time", "dep_time", "crs_arr_time", "arr_time",
    mode="before"
    )
    @classmethod
    def coerce_to_string(cls, v) -> Optional[str]:
        if v is None:
            return None
        # Handle nan float values
        if isinstance(v, float) and math.isnan(v):
            return None
        return str(int(v)) if isinstance(v, float) and v == int(v) else str(v)        
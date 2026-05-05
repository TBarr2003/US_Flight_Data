-- Flight Delays Keyspace
CREATE KEYSPACE IF NOT EXISTS flight_delays
WITH replication = {
  'class': 'NetworkTopologyStrategy',
  'dc1': 3
};

USE flight_delays;

-- Raw Layer
CREATE TABLE IF NOT EXISTS flights_raw (
    origin TEXT,
    dest TEXT,
    flight_date DATE,
    marketing_airline TEXT,
    operating_airline TEXT,
    tail_number TEXT,
    flight_number TEXT,
    dep_delay FLOAT,
    arr_delay FLOAT,
    cancelled FLOAT,
    cancellation_code TEXT,
    diverted FLOAT,
    weather_delay FLOAT,
    carrier_delay FLOAT,
    nas_delay FLOAT,
    security_delay FLOAT,
    late_aircraft_delay FLOAT,
    crs_dep_time TEXT,
    dep_time TEXT,
    crs_arr_time TEXT,
    arr_time TEXT,
    taxi_out FLOAT,
    taxi_in FLOAT,
    crs_elapsed_time FLOAT,
    actual_elapsed_time FLOAT,
    air_time FLOAT,
    distance FLOAT,
    origin_city TEXT,
    origin_state TEXT,
    dest_city TEXT,
    dest_state TEXT,
    year INT,
    month INT,
    day_of_month INT,
    day_of_week INT,
    PRIMARY KEY ((origin, dest), flight_date, marketing_airline, flight_number)
);

-- Clean Layer
CREATE TABLE IF NOT EXISTS flights_clean (
    origin TEXT,
    dest TEXT,
    flight_date DATE,
    marketing_airline TEXT,
    operating_airline TEXT,
    tail_number TEXT,
    flight_number TEXT,
    dep_delay FLOAT,
    arr_delay FLOAT,
    cancelled BOOLEAN,
    cancellation_code TEXT,
    diverted BOOLEAN,
    weather_delay FLOAT,
    carrier_delay FLOAT,
    nas_delay FLOAT,
    security_delay FLOAT,
    late_aircraft_delay FLOAT,
    total_delay FLOAT,
    delay_category TEXT,
    crs_dep_time TEXT,
    dep_time TEXT,
    crs_arr_time TEXT,
    arr_time TEXT,
    taxi_out FLOAT,
    taxi_in FLOAT,
    crs_elapsed_time FLOAT,
    actual_elapsed_time FLOAT,
    air_time FLOAT,
    distance FLOAT,
    origin_city TEXT,
    origin_state TEXT,
    dest_city TEXT,
    dest_state TEXT,
    year INT,
    month INT,
    day_of_month INT,
    day_of_week INT,
    PRIMARY KEY ((origin, dest), flight_date, marketing_airline, flight_number)
);

-- Aggregation Layer: Carrier Performance
CREATE TABLE IF NOT EXISTS carrier_performance_monthly (
    airline TEXT,
    year INT,
    month INT,
    total_flights BIGINT,
    cancelled_flights BIGINT,
    diverted_flights BIGINT,
    avg_dep_delay FLOAT,
    avg_arr_delay FLOAT,
    on_time_rate FLOAT,
    PRIMARY KEY ((airline), year, month)
);

-- Aggregation Layer: Route Delay Summary
CREATE TABLE IF NOT EXISTS route_delay_summary (
    origin TEXT,
    dest TEXT,
    year INT,
    total_flights BIGINT,
    avg_arr_delay FLOAT,
    avg_weather_delay FLOAT,
    avg_carrier_delay FLOAT,
    avg_nas_delay FLOAT,
    cancellation_rate FLOAT,
    PRIMARY KEY ((origin, dest), year)
);

-- Aggregation Layer: Seasonal Delay by State
CREATE TABLE IF NOT EXISTS seasonal_delay_by_state (
    origin_state TEXT,
    year INT,
    quarter INT,
    total_flights BIGINT,
    avg_weather_delay FLOAT,
    avg_total_delay FLOAT,
    cancellation_rate FLOAT,
    PRIMARY KEY ((origin_state), year, quarter)
);
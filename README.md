# ✈️ US Flight Delay Analytics Pipeline

A large-scale Big Data engineering pipeline that ingests, cleans, aggregates,
and visualizes 14.4 million US domestic flight records from 2023–2024.

## Platform Chosen: Apache Cassandra

Cassandra was chosen because flight delay data is fundamentally time-series
in nature. Every flight has a timestamp, a route, and a carrier — making
Cassandra's partition-based model a natural fit. By partitioning on
`(origin, dest)` and clustering on `flight_date`, queries like
"all delays on route JFK→LAX over time" execute efficiently across
all three nodes without full table scans.

Traditional RDBMS would struggle at this volume. Cassandra distributes
the data automatically across nodes, provides linear scalability,
and handles the write-heavy ingestion workload without locking.

## Dataset

- **Source:** Bureau of Transportation Statistics (BTS)
- **Dataset:** Marketing Carrier On-Time Performance
- **URL:** https://transtats.bts.gov
- **Volume:** 14.4 million rows across 24 monthly files (2023–2024)
- **Columns:** 42 meaningful fields including delay causes, route info,
  carrier codes, timestamps, and cancellation data

## Architecture

```
BTS Website → ZIP/CSV Files → Python Ingestion → Cassandra (Raw)
→ Python Cleaning → Cassandra (Clean)
→ Python Aggregation → Cassandra (Aggregated)
→ Streamlit Dashboard
```

See `architecture/architecture.pdf` for the full diagram.

## Team Members

- Tristan Barrera
- Tyler Henry
- Gibbs Dang

## Setup Instructions

### Prerequisites
- Docker Desktop
- Python 3.13+
- UV package manager (`pip install uv`)

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd BigDataFinalProject
```

### 2. Install dependencies
```bash
uv install
```

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env with your local paths
```

### 4. Start Cassandra cluster
```bash
docker compose up -d
```

Wait for all 3 nodes to show UN status:
```bash
docker exec -it cassandra-1 nodetool status
```

### 5. Create keyspace and tables
```bash
docker exec -it cassandra-1 cqlsh
```
Then run the contents of `database/schema.sql`

## Pipeline Stages

### Raw Layer
Ingests all 24 monthly ZIP files from BTS directly into Cassandra.
Validates every row using Pydantic before inserting.
Bad records are logged to `logs/ingestion.log` and skipped.

```bash
uv run python -m src.ingestion.ingest_raw
```

### Clean Layer
Reads from `flights_raw`, applies transformations, writes to `flights_clean`.
Key transformations:
- NaN delay values replaced with 0.0
- Derived `total_delay` field (sum of all delay causes)
- Derived `delay_category` (ON_TIME / MINOR / MODERATE / SEVERE / CANCELLED)
- Boolean conversion for `cancelled` and `diverted`
- Standardized uppercase for all codes

```bash
uv run python -m src.cleaning.clean
```

### Aggregation Layer
Creates 3 summary tables from `flights_clean`:
- `carrier_performance_monthly` — on-time rates per airline per month
- `route_delay_summary` — average delays per route per year
- `seasonal_delay_by_state` — weather and cancellation patterns by state and quarter

```bash
uv run python -m src.aggregation.aggregate
```

## Running Tests

```bash
uv run pytest tests/ -v
```

## Viewing the Dashboard

```bash
uv run streamlit run src/visualization/app.py
```

Open http://localhost:8501 in your browser.

## Query Performance

The primary partition key `(origin, dest)` was chosen to optimize
the most common query pattern — looking up all flights on a specific route.
With 14.4M rows distributed across 3 nodes, this partition strategy
ensures route-based queries hit only the relevant node rather than
scanning the entire dataset.

An index on `marketing_airline` was added to support carrier-based
queries without requiring a full table scan.

**Before index:** Carrier query scans all partitions (~14.4M rows)
**After index:** Carrier query goes directly to relevant rows

## Screenshots

_(Add screenshots of your Streamlit dashboard here)_

## Pipeline Reliability

- Pydantic validation on every ingested row
- Bad records logged to `logs/` directory, never silently dropped
- Retry-safe INSERT statements (Cassandra upserts by default)
- Cleaning layer handles NaN, null, and type mismatch gracefully

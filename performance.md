# Query Modeling and Performance

## Partition Key Decision

The primary table schema uses the following partition key:

```sql
PRIMARY KEY ((origin, dest), flight_date, marketing_airline, flight_number)
```

### Why This Partition Key?

The most common query pattern in flight delay analysis is route-based —
"show me all flights from JFK to LAX" or "what is the average delay on
this route over time?" By partitioning on `(origin, dest)`, all flights
on a given route are stored together on the same Cassandra node. This
means route-based queries hit exactly one node rather than scanning
the entire cluster.

### Clustering Columns

`flight_date` is the clustering column, which means rows within each
partition are physically sorted by date. This makes time-range queries
on a specific route extremely efficient.

### Trade-offs

- **Good for:** Route queries, time-series queries per route, carrier
  performance on specific routes
- **Not ideal for:** Carrier-wide queries (e.g. all AA flights) which
  require scanning all partitions — solved by adding a secondary index

---

## Secondary Index

To support carrier-based queries without full table scans, a secondary
index was added on `marketing_airline`:

```sql
CREATE INDEX ON flights_raw (marketing_airline);
```

### Before Index — Carrier Query

```sql
-- Requires ALLOW FILTERING — scans all partitions
SELECT * FROM flights_raw 
WHERE marketing_airline = 'AA' 
ALLOW FILTERING 
LIMIT 100;
```

Result: Slow — scans across all nodes and partitions

### After Index — Carrier Query

```sql
-- Uses index — goes directly to relevant rows
SELECT * FROM flights_raw 
WHERE marketing_airline = 'AA' 
LIMIT 100;
```

Result: Fast — index lookup on specific node

---

## Replication Strategy

```
NetworkTopologyStrategy with replication factor 3
```

All data is replicated across all 3 nodes in the cluster. This means:
- If one node goes down, data is still available on 2 other nodes
- Reads can be served from any node
- Writes are confirmed when at least one node acknowledges

---

## Sharding

Cassandra handles sharding automatically using consistent hashing on
the partition key. With 3 nodes each holding 16 tokens, data is
distributed evenly across the cluster. The `nodetool status` output
confirms each node owns roughly 33% of the data:

```
UN  172.18.0.4  129.22 KiB  16      76.0%
UN  172.18.0.3  70.23 KiB   16      59.3%
UN  172.18.0.2  109.39 KiB  16      64.7%
```
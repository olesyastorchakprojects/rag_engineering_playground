# Routing Policy

Consult `Qdrant MCP` first when you need to:

- check what is actually in the live Qdrant collection
- confirm whether a collection exists and matches the dense or hybrid ingest config
- inspect a point payload by `point_id`
- find points by `chunk_id` or `doc_id`
- find points by `content_hash`
- quickly check for a duplicate or anomaly around `chunk_id`
- inspect payload health before analyzing retrieval regressions
- verify retrieval truth without touching secondary storage

Do not start with `Qdrant MCP` when you need to:

- understand the broader retrieval pipeline architecture
  - start with `Project Context MCP`
- find the formal contract, schema, or codegen source of truth
  - start with `Spec MCP`
- understand traces, dashboards, Prometheus targets, or OTEL wiring
  - start with `Observability MCP`
- inspect request captures, eval rows, or request summaries
  - start with `Postgres MCP`

Useful distinction:

- `Qdrant MCP` answers what is in retrieval storage right now
- `Spec MCP` answers what should be true by contract
- `Project Context MCP` answers who operationally owns the storage and how it fits into the flow

# Postgres MCP

This MCP server exposes the project's eval-truth layer in PostgreSQL.

Its purpose is to give the agent structured access to:

- eval storage tables
- request capture rows
- eval processing state
- judge result rows
- request summaries
- runtime and eval run config rows
- request-level and run-level eval inspection helpers
- table schemas and indexes
- row-count and backlog-oriented inspection

This server does not replace:

- `Project Context MCP` for service roles and operational defaults
- `Spec MCP` for formal storage contracts and SQL source-of-truth docs

Routing guidance lives in:

- [routing_policy.md](routing_policy.md)

## Tool Surface

- `check_connection()`
- `get_connection_defaults()`
- `get_known_tables()`
- `describe_table(table_name)`
- `get_table_row_counts()`
- `get_recent_request_captures(limit=20)`
- `find_requests_by_query_text(query_text, limit=20)`
- `get_request_capture(request_id)`
- `get_request_capture_full(request_id)`
- `find_request_capture_by_trace_id(trace_id, limit=20)`
- `get_eval_processing_state(request_id)`
- `get_request_summary(request_id)`
- `get_request_summary_full(request_id)`
- `get_request_eval_bundle(request_id, generation_limit=20, retrieval_limit=50)`
- `get_incomplete_eval_requests(limit=20)`
- `get_eval_stage_summary()`
- `get_failed_eval_requests(limit=20)`
- `get_requests_by_run_id(run_id, limit=200)`
- `get_run_results(run_id)`

## When To Use It

Use this server when you need the actual PostgreSQL-backed eval truth.

Good examples:

- "does the local eval database respond?"
- "what tables are present?"
- "show me the request capture for this `request_id`"
- "what did the runtime write for this trace?"
- "what is the current eval backlog?"
- "how many judge rows did this run produce?"

## Error Handling

DB-facing tools return structured error payloads on connection/query failures instead of crashing the MCP process.

Request-oriented lookup tools intentionally distinguish between:

- lightweight projections for routine debugging
- explicit full-row tools for rare deep inspection

This keeps normal MCP responses smaller while preserving an escape hatch for full-row analysis.

## Connection Model

The server reads PostgreSQL through:

- `POSTGRES_URL` when present
- otherwise the project default local stack DSN:
  - `postgres://postgres:postgres@localhost:5432/rag_eval`

## Local Run

```bash
./.venv/bin/python Tools/mcp/postgres/server.py
```

## Expected MCP Registration

This server is intended to be registered as a local stdio MCP server in the local Codex configuration.

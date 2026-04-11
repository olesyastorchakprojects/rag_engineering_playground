# Postgres MCP Routing Policy

Consult `Postgres MCP` first when the question is about:

- request capture rows
- eval processing state
- generation judge rows
- retrieval judge rows
- runtime and eval run config rows
- request summaries
- run-scoped request summaries
- eval backlog or failed requests
- run-scoped judge results in PostgreSQL
- whether eval data was actually written

Use `Postgres MCP` especially for:

- `check_connection()` when checking whether local eval Postgres is reachable and initialized
- `get_table_row_counts()` when checking whether eval tables are being populated
- `find_requests_by_query_text(query_text)` when the query text is known before `request_id`
- `get_request_capture(request_id)` when inspecting one runtime capture row
- `get_request_capture_full(request_id)` only when the full `retrieval_results` payload is really needed
- `find_request_capture_by_trace_id(trace_id)` when the trace is known first
- `get_request_eval_bundle(request_id)` when debugging one request across capture/state/summary
- `get_request_summary_full(request_id)` only when the full summary row is really needed
- `get_eval_stage_summary()` when checking aggregate eval progress
- `get_incomplete_eval_requests()` when checking pending/running/failed backlog
- `get_failed_eval_requests()` when checking true failures only
- `get_requests_by_run_id(run_id)` when checking which requests are present in one run and how much data each already produced
- `get_run_results(run_id)` when checking how many judge rows one run produced

Do not consult `Postgres MCP` first when the question is primarily about:

- formal storage contracts
- SQL DDL source of truth
- schema/codegen requirements

For those questions, consult `Spec MCP` first.

Do not consult `Postgres MCP` first when the question is primarily about:

- service roles
- canonical data flow
- whether Postgres is the right system of record for a concern

For those questions, consult `Project Context MCP` first.

Do not consult `Postgres MCP` first when the question is primarily about:

- retrieval payload truth
- chunk/vector/index state

For those questions, consult `Qdrant MCP` first.

# Project Context MCP Routing Policy

Consult `Project Context MCP` first when the question is about:

- which service owns which responsibility
- where data is canonically stored
- high-level data flow between systems
- launcher entrypoints and profile-aware launch behavior
- provider topology for generation, reranking, and eval judging
- hybrid ingest and workflow control-plane roles
- default debugging path
- Rust vs Python ownership boundaries
- which MCP should be consulted next

Consult `Spec MCP` first when the question is about:

- formal contracts
- required fields
- schemas
- storage keys
- stage and module behavior
- run semantics

Consult `Qdrant MCP` first when the question is about:

- chunk collections
- indexed payloads
- vector points
- retrieval candidates
- retrieval results

Consult `Observability MCP` first when the question is about:

- traces
- spans
- runtime latency
- Phoenix and Tempo behavior
- Grafana and Prometheus-backed runtime inspection

Consult `Postgres MCP` first when the question is about:

- request_captures
- eval_processing_state
- judge results
- request summaries
- run-level eval outcomes

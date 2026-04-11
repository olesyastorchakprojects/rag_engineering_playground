# Routing Policy

Use `Agent Orchestrator MCP` when:

- the user gives one high-level task and expects end-to-end coordination
- the task needs more than one specialist agent
- the task may require looping between code, tests, conformance, and review
- the user wants one final report rather than several manual agent hops

Prefer direct specialist-agent use when:

- the task is trivial
- only one agent role is clearly needed
- the user wants manual control of execution order

Escalate internally to project truth sources:

- `Project Context MCP` for ownership and operational topology
- `Spec MCP` for formal source-of-truth documents
- `Spec Conformance MCP` for curated drift detection
- `Postgres MCP` when storage semantics or eval tables matter
- `Observability MCP` when metrics, dashboards, or telemetry surfaces matter
- `Eval Experiments MCP` for run-oriented eval analysis
- `Qdrant MCP` when retrieval payload or collection truth matters

Repository-specific routing rules:

- any `Execution/ingest/hybrid` or `Execution/ingest/schemas` change should pull in `Project Context MCP`, `Spec MCP`, `Spec Conformance MCP`, and usually `Qdrant MCP`
- any `Execution/bin` or `Execution/orchestration` change should pull in `Project Context MCP` and `Spec MCP`
- any `Specification/tasks/multi_agent` change should pull in `Project Context MCP` and `Spec MCP`
- any `Measurement/observability` change should pull in `Observability MCP`
- any `Measurement/evals` change should pull in `Observability MCP` and usually `Eval Experiments MCP`
- any `Execution/docker/postgres/init/*.sql` change should pull in `Postgres MCP`
- any `Tools/mcp/*` change should trigger stale-truth review
- any `rag_runtime` spec-sensitive change should include `Spec Conformance MCP`

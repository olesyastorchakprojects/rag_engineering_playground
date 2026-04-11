# Observability MCP

This MCP server exposes the project's observability layer through two complementary views:

- repo-backed observability assets
- live local observability stack inspection

The repo-backed asset view currently covers both:

- `Measurement/observability`
- `Measurement/evals`

Its purpose is to give the agent structured access to:

- Grafana dashboards
- Grafana provisioning files
- Tempo configuration
- OTEL collector configuration
- Docker compose observability stack wiring
- live local health and trace inspection

Important limitation:

- `get_live_stack_status()` is availability-oriented
- it checks HTTP surfaces and readiness-style endpoints
- it does not by itself prove end-to-end telemetry delivery into Tempo, Phoenix, or Prometheus
- use `get_tempo_trace(trace_id)` when you need concrete trace-level confirmation

Important startup assumptions:

- start `tempo` and `phoenix` before `otel-collector`
- start `prometheus` after `otel-collector`, since it scrapes collector metrics
- allow about 15 seconds of warmup for Tempo before treating readiness/trace checks as authoritative
- treat early collector failures during stack boot as potentially caused by dependency timing, not only by bad config

This server does not replace:

- `Project Context MCP` for operational ownership and workflow defaults
- `Spec MCP` for formal specification and codegen requirements

Routing guidance lives in:

- [routing_policy.md](routing_policy.md)

## Strong MVP Scope

The current scaffold supports:

- listing observability asset roots
- listing observability documents
- reading one observability document
- summarizing Docker compose / Tempo / OTEL collector configuration
- returning a focused OTEL collector pipeline summary
- enumerating Grafana dashboards and datasources
- drilling into one Grafana dashboard by uid or title
- returning Prometheus scrape target health
- checking live local stack status
- reading one Tempo trace by `trace_id`
- best-effort Tempo trace search by attribute/value, strongest for `request_id`

## Tool Surface

- `get_observability_roots()`
- `list_observability_documents(prefix="")`
- `read_observability_document(path)`
- `get_runtime_endpoints()`
- `get_stack_config_summary()`
- `get_dashboard_catalog()`
- `get_datasource_configs()`
- `get_dashboard_details(uid_or_title)`
- `get_collector_pipeline_summary()`
- `get_prometheus_target_status(job_name="")`
- `get_live_stack_status()`
- `get_tempo_trace(trace_id)`
- `find_trace_by_attribute(attribute, value)`

## When To Use It

Use this server when you need to inspect repository-owned observability assets or the live local stack.

Good examples:

- "which dashboards are provisioned?"
- "what exporter endpoints does the collector use?"
- "is Prometheus scraping the collector?"
- "did this request emit a trace in Tempo?"
- "what runtime or eval observability assets live in the repo?"

## Local Run

```bash
./.venv/bin/python Tools/mcp/observability/server.py
```

## Expected MCP Registration

This server is intended to be registered as a local stdio MCP server in the local Codex configuration.

# Observability MCP Routing Policy

Consult `Observability MCP` first when the question is about:

- live traces
- runtime latency
- Grafana dashboards and datasources
- Tempo configuration and trace storage behavior
- OTEL collector routing and exporters
- live local observability stack health
- whether telemetry reached Tempo, Phoenix, Prometheus, or Grafana-backed assets

Use `Observability MCP` especially for:

- `get_live_stack_status()` when checking whether local observability services are healthy
- `get_prometheus_target_status()` when checking whether Prometheus scrape targets are actually up
- `get_tempo_trace(trace_id)` when inspecting one concrete trace
- `find_trace_by_attribute(attribute, value)` when you know `request_id` and need a best-effort trace lookup
- `get_dashboard_catalog()` when checking existing Grafana dashboards
- `get_dashboard_details(uid_or_title)` when checking panel queries or one dashboard's concrete metric usage
- `get_datasource_configs()` when checking Grafana datasource provisioning
- `get_stack_config_summary()` when reasoning about compose wiring, collector exporters, and local endpoints
- `get_collector_pipeline_summary()` when reasoning specifically about receiver/processor/exporter pipeline shape
- startup-order and warmup questions for the local observability stack

Prefer `get_tempo_trace(trace_id)` over `get_live_stack_status()` when the real question is:

- did one concrete request emit a trace
- did Tempo store one concrete trace
- can one known trace id be resolved end-to-end

Treat `get_live_stack_status()` as an availability check, not a full telemetry-path assertion.
Also account for stack boot timing:

- `otel-collector` should be treated as downstream of Phoenix and Tempo
- `prometheus` should be treated as downstream of `otel-collector` for collector-metrics scraping
- Tempo needs about 15 seconds of warmup before readiness and trace-ingestion checks are reliable

Do not consult `Observability MCP` first when the question is primarily about:

- formal contracts
- schemas
- code generation requirements
- curated generation or validation context

For those questions, consult `Spec MCP` first.

Do not consult `Observability MCP` first when the question is primarily about:

- service roles
- project data flow
- language ownership boundaries
- debugging defaults as a policy question

For those questions, consult `Project Context MCP` first.

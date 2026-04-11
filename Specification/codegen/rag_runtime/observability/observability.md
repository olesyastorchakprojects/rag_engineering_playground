========================
1) Purpose / Scope
========================

This document defines the top-level observability model for `rag_runtime`.

It defines:
- signal architecture;
- observability document structure;
- backend routing model;
- artifact placement;
- top-level safety constraints.

This document does not define:
- detailed span contracts;
- detailed metric contracts;
- infra bootstrap;
- evals.

========================
2) Observability Objectives
========================

Observability in `rag_runtime` exists for exactly three purposes:
- reconstruct the full execution path of one request;
- diagnose errors, early termination, and latency degradation;
- support operational inspection and AI trace inspection from the same OTEL signal flow.

When reranking is enabled, the observability contract must include reranking as its own first-class stage rather than folding reranking latency into retrieval or generation.

========================
3) Signal Architecture
========================

`rag_runtime` emits exactly two required signal types:
- traces;
- metrics.

Logs are outside the required observability contract.

Signal routing is fixed:
- `rag_runtime` exports traces and metrics through OTLP;
- OTEL Collector is the single ingress point for both signal types;
- OTEL Collector routes traces to Tempo and Phoenix;
- OTEL Collector routes metrics to Prometheus;
- Grafana reads traces from Tempo and metrics from Prometheus.

Direct export from `rag_runtime` to multiple backends is forbidden.

========================
4) Document Structure
========================

The observability specification is split into the following documents:

- `observability.md`
  - top-level observability model;
- `spans.md`
  - root span contract, span hierarchy, span ownership, span attributes;
- `metrics.md`
  - metric semantics, metric label rules, and metric record points;
- `openinference_spans.md`
  - Phoenix/OpenInference semantic span classification and compact semantic span payload;
- `openinference_metrics.md`
  - Phoenix/OpenInference semantic metric contract;
- `grafana_dashboards.md`
  - Grafana dashboard artifact contract;
- `references.md`
  - local reference artifact contract;
- `implementation.md`
  - validated Rust implementation pattern, including short-lived validation behavior, log filter contract, and lifecycle follow-up notes.

Generation must follow this document split. Detailed span and metric rules must not be reintroduced into this file.
Dashboard inventory, panel structure, and PromQL requirements belong only in `grafana_dashboards.md`.
`references.md` is limited to read-only local wiring/provisioning templates and must not be treated as the source of truth for runtime dashboard composition.

========================
5) Configuration Model
========================

Observability configuration belongs to the typed runtime configuration model.

Observability settings are read from the observability config section.

Business modules:
- do not read raw environment variables for observability;
- do not define sampling behavior;
- do not override exporter routing.

========================
6) Safety Constraints
========================

The following values must not be written to telemetry:
- secrets;
- API keys;
- authorization headers;
- environment variable values;
- raw prompt text;
- raw retrieved document text;
- raw model output text.

========================
7) Troubleshooting Missing Telemetry
========================

If expected telemetry is missing during validation, the troubleshooting order is fixed.

The canonical repository smoke for this workflow is:

- `Execution/otel_runtime_smoke/`

The validating agent must not start patching `rag_runtime` observability code or CLI behavior until all earlier troubleshooting steps below have been checked.

Required troubleshooting order:

1. Check the effective `RUST_LOG` and confirm that it does not filter out the required `INFO` spans and events.
2. Check that the local observability and eval-storage stack defined in `Execution/docker/` is healthy according to the service-specific readiness criteria defined in `Specification/codegen/rag_runtime/rag_runtime.md`.
3. Check that the effective `TRACING_ENDPOINT` and `METRICS_ENDPOINT` environment values point to the live OTEL collector ingress defined by the active observability stack.
4. Check, using OTEL collector metrics or logs together with backend APIs, that telemetry accepted by the collector is being forwarded to Tempo, Phoenix, and Prometheus.
5. Run `Execution/otel_runtime_smoke/` and verify through backend APIs that its telemetry reaches the backends.
6. Only after all previous checks succeed may the validating agent debug or modify `rag_runtime` CLI or runtime observability code.

Troubleshooting rules:

- absence of traces must not be treated as a CLI or runtime bug before the effective `RUST_LOG` is known;
- absence of traces must not be treated as a CLI or runtime bug before backend health is confirmed;
- absence of traces must not be treated as a CLI or runtime bug before endpoint correctness is confirmed;
- absence of traces must not be treated as a CLI or runtime bug before collector-to-backend forwarding is confirmed;
- absence of traces in a failing smoke run means the validation environment is still not trustworthy for CLI conclusions;
- a smoke run counts as successful only when backend APIs confirm that its telemetry is actually present in the backends, not merely when the smoke process exits successfully;
- `Execution/otel_runtime_smoke/` is the canonical repository smoke for this troubleshooting workflow and is read-only under all conditions.

========================
8) Artifact Placement
========================

Observability specification documents belong in:
- `Specification/codegen/rag_runtime/observability/`

Generated observability artifacts belong in:
- `Measurement/observability/`

The local OTEL validation project belongs in:
- `Execution/otel_smoke/`
- `Execution/otel_runtime_smoke/`

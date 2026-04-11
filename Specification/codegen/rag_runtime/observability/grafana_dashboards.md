========================
1) Purpose / Scope
========================

This document defines the Grafana dashboard contract for `rag_runtime` observability.

It defines:
- required dashboard artifacts;
- required dashboard set;
- required artifact filenames;
- artifact placement;
- required panel/query structure.

========================
2) Required Dashboard Artifacts
========================

The required Grafana artifact set is:
- dashboard JSON definitions;
- dashboard provisioning config;
- datasource provisioning config.

Generation must create and update only the repository artifacts listed in this document.

Required generated filenames are fixed:
- `Measurement/observability/grafana/dashboards/request_overview.json`
- `Measurement/observability/grafana/dashboards/ai_overview.json`
- `Measurement/observability/grafana/provisioning/dashboards/dashboards.yml`
- `Measurement/observability/grafana/provisioning/datasources/prometheus.yml`
- `Measurement/observability/grafana/provisioning/datasources/tempo.yml`

Required datasource names are fixed:
- `Prometheus`
- `Tempo`

Required datasource identifiers are fixed:
- Prometheus datasource file defines `uid = prometheus`
- Tempo datasource file defines `uid = tempo`

Required datasource contract is fixed:
- `Prometheus`
  - `type = prometheus`
  - `uid = prometheus`
  - `url = http://prometheus:9090`
- `Tempo`
  - `type = tempo`
  - `uid = tempo`
  - `url = http://tempo:3200`

Required dashboard provisioning contract is fixed for:
- `Measurement/observability/grafana/provisioning/dashboards/dashboards.yml`

The provisioning file must define:
- one provider
- `type = file`
- `disableDeletion = false`
- `allowUiUpdates = true`
- `options.path = /var/lib/grafana/dashboards`

All panel queries in this document use the `Prometheus` datasource.

Sparse-traffic dashboard rule is fixed:
- the local validation workflow often uses low-volume CLI traffic and short-lived processes;
- for runtime Grafana dashboards in this repository, percentile latency panels must query cumulative histogram buckets directly rather than using `rate()` or `increase()` window functions;
- token totals, chunk totals, and retrieval score averages must also use cumulative `_sum` and `_count` series directly rather than `increase()` window functions;
- this rule exists because short-lived local runtime processes frequently produce only one useful scrape point per metric series, which makes `rate()`/`increase()` return zero or `NaN` even when the underlying metric was emitted successfully.

Retriever-kind dashboard rule is fixed:
- runtime dashboards must surface `dense` and `hybrid` retrieval separately when retrieval metrics are shown;
- retrieval panels that aggregate dependency or retrieval-quality metrics must preserve `retriever_kind` as a visible series split or panel breakdown;
- dashboards must not collapse `dense` and `hybrid` retrieval into one unlabeled series when the underlying metric includes the `retriever_kind` label.

========================
3) Required Dashboard Set
========================

The required dashboard set is:

`request_overview`
- purpose:
  - primary operational dashboard for request reliability and latency
- dashboard title:
  - `Runtime Reliability & Latency`
- dashboard file:
  - `Measurement/observability/grafana/dashboards/request_overview.json`
- layout:
  - dashboard is organized as six rows
  - first five rows each contain exactly three panels
  - final row contains exactly three counter panels
- required panels:
  - `Request Duration p50`
    - panel type: time series
    - query: `histogram_quantile(0.50, sum by (le) (rag_request_duration_ms_bucket))`
  - `Request Duration p90`
    - panel type: time series
    - query: `histogram_quantile(0.90, sum by (le) (rag_request_duration_ms_bucket))`
  - `Request Duration p99`
    - panel type: time series
    - query: `histogram_quantile(0.99, sum by (le) (rag_request_duration_ms_bucket))`
  - `Fast Stage Latency p50`
    - panel type: time series
    - query: `histogram_quantile(0.50, sum by (le, stage) (rag_stage_duration_ms_bucket{stage=~"input_validation|retrieval"}))`
  - `Fast Stage Latency p90`
    - panel type: time series
    - query: `histogram_quantile(0.90, sum by (le, stage) (rag_stage_duration_ms_bucket{stage=~"input_validation|retrieval"}))`
  - `Fast Stage Latency p99`
    - panel type: time series
    - query: `histogram_quantile(0.99, sum by (le, stage) (rag_stage_duration_ms_bucket{stage=~"input_validation|retrieval"}))`
  - `Generation Latency p50`
    - panel type: time series
    - query: `histogram_quantile(0.50, sum by (le) (rag_stage_duration_ms_bucket{stage="generation"}))`
  - `Generation Latency p90`
    - panel type: time series
    - query: `histogram_quantile(0.90, sum by (le) (rag_stage_duration_ms_bucket{stage="generation"}))`
  - `Generation Latency p99`
    - panel type: time series
    - query: `histogram_quantile(0.99, sum by (le) (rag_stage_duration_ms_bucket{stage="generation"}))`
  - `Fast Dependency Latency p50`
    - panel type: time series
    - query: `histogram_quantile(0.50, sum by (le, dependency, retriever_kind) (rag_dependency_duration_ms_bucket{dependency=~"embedding|vector_search"}))`
  - `Fast Dependency Latency p90`
    - panel type: time series
    - query: `histogram_quantile(0.90, sum by (le, dependency, retriever_kind) (rag_dependency_duration_ms_bucket{dependency=~"embedding|vector_search"}))`
  - `Fast Dependency Latency p99`
    - panel type: time series
    - query: `histogram_quantile(0.99, sum by (le, dependency, retriever_kind) (rag_dependency_duration_ms_bucket{dependency=~"embedding|vector_search"}))`
  - `Chat Latency p50`
    - panel type: time series
    - query: `histogram_quantile(0.50, sum by (le) (rag_dependency_duration_ms_bucket{dependency="chat"}))`
  - `Chat Latency p90`
    - panel type: time series
    - query: `histogram_quantile(0.90, sum by (le) (rag_dependency_duration_ms_bucket{dependency="chat"}))`
  - `Chat Latency p99`
    - panel type: time series
    - query: `histogram_quantile(0.99, sum by (le) (rag_dependency_duration_ms_bucket{dependency="chat"}))`
  - `Requests Total`
    - panel type: time series
    - query: `sum(rag_requests_total)`
  - `Failures`
    - panel type: time series
    - required series:
      - `requests_failed_total`: `sum(rag_requests_failed_total)`
      - `dependency <dependency, retriever_kind>`: `sum by (dependency, retriever_kind) (rag_dependency_failures_total)`
  - `Retry Attempts`
    - panel type: time series
    - query: `sum by (dependency, retriever_kind) (rag_retry_attempts_total)`

`ai_overview`
- purpose:
  - compact AI-focused operational dashboard for token usage, chunk flow, and retrieval quality
- dashboard title:
  - `Runtime Content & Retrieval`
- dashboard file:
  - `Measurement/observability/grafana/dashboards/ai_overview.json`
- layout:
  - dashboard is organized as one row with exactly three panels
- required panels:
  - `Token Totals`
    - panel type: time series
    - required series:
      - `query_tokens`: `sum(rag_query_token_count_sum)`
      - `prompt_tokens`: `sum(rag_generation_prompt_tokens_sum)`
      - `completion_tokens`: `sum(rag_generation_completion_tokens_sum)`
      - `total_tokens`: `sum(rag_generation_total_tokens_sum)`
  - `Chunk Totals`
    - panel type: time series
    - required series:
      - `retrieved_chunks`: `sum(rag_retrieved_chunks_count_sum)`
      - `generation_input_chunks`: `sum(rag_generation_input_chunks_count_sum)`
  - `Retrieval Score Averages`
    - panel type: time series
    - required series:
      - `top1_avg <retriever_kind>`: `sum by (retriever_kind) (rag_retrieval_top1_score_sum) / clamp_min(sum by (retriever_kind) (rag_retrieval_top1_score_count), 1)`
      - `topk_mean_avg <retriever_kind>`: `sum by (retriever_kind) (rag_retrieval_topk_mean_score_sum) / clamp_min(sum by (retriever_kind) (rag_retrieval_topk_mean_score_count), 1)`

Dashboard simplification rule is fixed:
- generation must not recreate the legacy split runtime dashboard set once the compact two-dashboard layout is in use;
- `request_overview.json` and `ai_overview.json` are the only required runtime Grafana dashboards for `rag_runtime`.

========================
4) Artifact Placement
========================

Generated Grafana dashboard artifacts belong in:
- `Measurement/observability/grafana/dashboards/`
- `Measurement/observability/grafana/provisioning/dashboards/`
- `Measurement/observability/grafana/provisioning/datasources/`

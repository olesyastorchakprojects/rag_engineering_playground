========================
1) Purpose / Scope
========================

This document defines the metric contract for `rag_runtime`.

It defines:
- metric set;
- metric type and unit;
- metric label rules;
- metric emission sources;
- metric record points.

========================
2) Metric Label Rules
========================

Metric labels are low-cardinality.

High-cardinality values must not be used as metric labels.

The following values must not be used as metric labels:
- raw query text;
- raw prompt text;
- raw retrieved document text;
- raw model output text;
- error message text;
- unbounded identifiers.

Allowed `module` label values are fixed:
- `orchestration`
- `input_validation`
- `retrieval`
- `reranking`
- `generation`

Allowed `stage` label values are fixed:
- `request`
- `input_validation`
- `retrieval`
- `reranking`
- `generation`

Allowed `status` label values are fixed:
- `ok`
- `error`

Allowed `dependency` label values are fixed:
- `embedding`
- `vector_search`
- `chat`

Allowed `retriever_kind` label values are fixed:
- `dense`
- `hybrid`

Only fields listed under `labels` become metric labels.

Fields listed under `source` and `record point` are specification metadata and must not be emitted as metric labels.

Owner mapping and dependency label mapping are generation rules, not metric labels.

Dependency label mapping is fixed:
- `dependency = embedding` -> `module = retrieval`, `stage = retrieval`
- `dependency = vector_search` -> `module = retrieval`, `stage = retrieval`
- `dependency = chat` -> `module = generation`, `stage = generation`

Retriever-kind label mapping is fixed:
- for `retrieval.embedding` and `retrieval.vector_search`, `retriever_kind = Settings.retrieval.kind`
- for `generation.chat`, no `retriever_kind` label is emitted

========================
3) Metric Set
========================

The required metric set is:

`rag_requests_total`
- type: counter
- unit: requests
- labels:
  - `module`
  - `stage`
- source:
  - root span close
- record point:
  - increment once when `rag.request` closes

`rag_requests_failed_total`
- type: counter
- unit: requests
- labels:
  - `module`
  - `stage`
- source:
  - root span close
- record point:
  - increment once when `rag.request` closes with `status = error`

`rag_request_duration_ms`
- type: histogram
- unit: milliseconds
- labels:
  - `module`
  - `stage`
  - `status`
- source:
  - root span close
- record point:
  - record once when `rag.request` closes

`rag_stage_duration_ms`
- type: histogram
- unit: milliseconds
- labels:
  - `module`
  - `stage`
  - `status`
- source:
  - stage span close
- record point:
  - record once when `input_validation`, `retrieval`, `reranking`, or `generation` closes

`rag_dependency_duration_ms`
- type: histogram
- unit: milliseconds
- labels:
  - `module`
  - `stage`
  - `dependency`
  - `retriever_kind`
  - `status`
- source:
  - dependency span close
- record point:
  - record once when `retrieval.embedding`, `retrieval.vector_search`, or `generation.chat` closes

Duration histogram boundary rule is fixed for:
- `rag_request_duration_ms`
- `rag_stage_duration_ms`
- `rag_dependency_duration_ms`

Those three histograms must use explicit bucket boundaries in milliseconds that cover both:
- sub-millisecond and millisecond-scale validation/retrieval work;
- long-running generation/chat/request paths that may reach multiple minutes in local CPU-only execution.

The required upper coverage must reach at least `180000 ms`.

`rag_retrieval_empty_total`
- type: counter
- unit: requests
- labels:
  - `module`
  - `stage`
- source:
  - orchestration branch after retrieval
- record point:
  - increment once when retrieval output is empty and orchestration terminates the request

`rag_query_token_count`
- type: histogram
- unit: tokens
- labels:
  - `module`
  - `stage`
- source:
  - `input_validation.token_count`
- record point:
  - record once when normalized query token count is computed

`rag_retrieved_chunks_count`
- type: histogram
- unit: chunks
- labels:
  - `module`
  - `stage`
- source:
  - `payloads_mapped` event in `retrieval.payload_mapping`
- record point:
  - record once when `payloads_mapped` is emitted

`rag_generation_input_chunks_count`
- type: histogram
- unit: chunks
- labels:
  - `module`
  - `stage`
- source:
  - `prompt_assembled` event in `generation.prompt_assembly`
- record point:
  - record once when `prompt_assembled` is emitted

`rag_generation_prompt_tokens`
- type: histogram
- unit: tokens
- labels:
  - `module`
  - `stage`
- source:
  - `prompt_assembled` event in `generation.prompt_assembly`
- record point:
  - record once when `prompt_assembled` is emitted

`rag_generation_completion_tokens`
- type: histogram
- unit: tokens
- labels:
  - `module`
  - `stage`
- source:
  - `generation_response_validated` event in `generation.response_validation`
- record point:
  - record once when `generation_response_validated` is emitted

`rag_generation_total_tokens`
- type: histogram
- unit: tokens
- labels:
  - `module`
  - `stage`
- source:
  - `generation_response_validated` event in `generation.response_validation`
- record point:
  - record once when `generation_response_validated` is emitted

`rag_dependency_failures_total`
- type: counter
- unit: failures
- labels:
  - `module`
  - `stage`
  - `dependency`
  - `retriever_kind`
- source:
  - dependency span close
- record point:
  - increment once when a dependency span ends with `status = error`

`rag_retry_attempts_total`
- type: counter
- unit: attempts
- labels:
  - `module`
  - `stage`
  - `dependency`
  - `retriever_kind`
- source:
  - retry loop inside dependency-owning module
- record point:
  - increment once for each retry attempt after the initial failed attempt

========================
4) Metric Emission Rules
========================

Metrics are emitted through OTLP.

Metric emission rules:
- metrics are initialized during observability startup;
- metric record points follow the contract in section `3) Metric Set`.

Implicit metric creation is forbidden.

========================
5) Metric Semantics
========================

Metric semantics are fixed:

- counters count events and only increase;
- histograms record one observed value at one explicit record point;
- metric units are part of the contract;
- metric labels are part of the contract.

Phoenix/OpenInference semantic metrics are defined only in:

- `Specification/codegen/rag_runtime/observability/openinference_metrics.md`

`metrics.md` must not redefine Phoenix/OpenInference semantic metric names or Phoenix-specific semantic metric record points.

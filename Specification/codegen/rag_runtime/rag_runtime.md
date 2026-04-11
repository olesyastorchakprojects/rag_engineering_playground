## 1) Purpose / Scope of rag_runtime

`rag_runtime` is the unified Rust crate for end-to-end RAG execution.

Its purpose is to implement the full request flow:
- receive a user query;
- retrieve relevant chunks for that query;
- pass the retrieved chunks to the LLM as context;
- generate an answer with the LLM;
- return the final answer to the user.

`rag_runtime` is responsible for coordinating all RAG stages inside one crate boundary:
- request intake;
- input validation;
- retrieval;
- context assembly;
- answer generation;
- response return.
- observability emission for traces and metrics.

All services run locally, including inside Docker containers.
This specification defines the crate-level behavior and boundaries of `rag_runtime`.
Detailed behavior of individual stages is described in the dedicated module specifications located in the same `Specification/codegen/rag_runtime/` folder.

The crate-level specification for retrieval-quality helper behavior is defined in:
- `Specification/codegen/rag_runtime/retrieval_metrics.md`

The retrieval-quality helper must be implemented as a dedicated internal module of the generated crate.
Its implementation and unit tests are not part of the public crate API, but they are part of the required generated internal crate structure defined by the relevant artifact and unit-test contracts.

The required generated artifact set for `rag_runtime` is defined in:
- `Specification/codegen/rag_runtime/generated_artifacts.md`

## 2) Modules

`rag_runtime` contains the following main modules:

- `orchestration`
- `input_validation`
- `retrieval`
- `reranking`
- `generation`
- `request_capture_store`

Module responsibilities:

- `orchestration` is the entrypoint and coordinator of the full pipeline.
- `input_validation` is responsible for validating and normalizing the incoming user request before retrieval and generation stages run.
- `retrieval` is responsible for query embedding, vector search, and returning candidate chunks.
- `reranking` is responsible for optional post-retrieval candidate ordering and final rerank-score computation.
- `generation` is responsible for chat-model request construction and answer generation.
- `request_capture_store` is responsible for persisting `RequestCapture` values into request-capture storage.

Module boundary rules:

- `orchestration` owns pipeline sequencing.
- `input_validation` does not perform retrieval or generation.
- `retrieval` does not call `generation`.
- `retrieval` does not perform reranking.
- `retrieval` receives only validated input.
- `reranking` does not call retrieval dependencies or generation.
- `generation` does not call `retrieval`.
- `generation` consumes final reranked candidates when reranking is enabled.
- `request_capture_store` does not assemble `RequestCapture` and does not perform retrieval or generation.
- modules must interact through explicit request and response types.

## 3) High-Level Data Flow

High-level request flow in `rag_runtime`:

1. `orchestration` receives the user request and creates the runtime request context.
2. `orchestration` passes the incoming request to `input_validation`.
3. `input_validation` validates and normalizes the request and returns validated runtime input.
4. `orchestration` calls `retrieval` with the validated user query and retrieval parameters.
5. `retrieval` performs dense or hybrid retrieval according to `Settings.retrieval`, then returns retrieved chunks.
6. `orchestration` selects and constructs the concrete reranker from `Settings.reranking.reranker`.
7. `orchestration` calls the selected reranker with the validated request and retrieval output.
8. The selected reranker returns the full reranked candidate set without truncation.
9. If the final reranked candidate set is empty, `orchestration` returns an error and does not call `generation`.
10. Otherwise, `orchestration` builds `GenerationRequest` from `ValidatedUserRequest.query` and the first `Settings.reranking.final_k` final reranked chunks.
11. `orchestration` calls `generation` with `GenerationRequest`.
12. `generation` sends the request to the LLM and returns the generated answer.
13. `orchestration` builds `RequestCapture` from the successful completed request state, including rerank scores.
14. `orchestration` calls `request_capture_store` with `RequestCapture` and `Settings.request_capture`.
15. `orchestration` builds the final runtime response and returns it to the caller.

Data flow rules:

- the output of each stage becomes explicit input for the next stage;
- no stage reads hidden context from another stage outside the declared request flow.
- `pass_through` reranking is still represented as an explicit reranking stage, not as a pipeline bypass.

## 4) Required Observability Integration

Observability is a required part of the `rag_runtime` crate contract.

`rag_runtime` generation must not omit observability.

The generated crate must implement the observability contract defined in:
- `Specification/codegen/rag_runtime/observability/observability.md`
- `Specification/codegen/rag_runtime/observability/spans.md`
- `Specification/codegen/rag_runtime/observability/metrics.md`
- `Specification/codegen/rag_runtime/observability/openinference_spans.md`
- `Specification/codegen/rag_runtime/observability/openinference_metrics.md`
- `Specification/codegen/rag_runtime/observability/grafana_dashboards.md`
- `Specification/codegen/rag_runtime/observability/implementation.md`

Required observability integration rules:

- `rag_runtime` must initialize observability during process startup;
- `rag_runtime` must emit the required traces and metrics during request execution;
- `rag_runtime` must use `Settings.observability` as part of the crate-wide `Settings` type;
- `rag_runtime` must implement the required root span, mandatory stage spans, and required span events;
- `rag_runtime` must implement the required metric set and metric record points;
- `rag_runtime` must generate observability artifacts under `Measurement/observability/` according to the observability specification;
- `rag_runtime` generation is incomplete until the full required generated artifact set defined in `Specification/codegen/rag_runtime/generated_artifacts.md` has been produced;
- `rag_runtime` business logic is incomplete if it implements request execution without the required observability contract.

Required final observability validation rules:

- successful generation is not established by unit tests and coverage alone;
- the repository-owned Docker files for the local observability and eval-storage stack live under `Execution/docker/`;
- those `Execution/docker/` local observability and eval-storage stack files are the confirmed working operational reference for final validation;
- generation and validation must reuse the existing `Execution/docker/` stack definition rather than inventing a parallel compose layout elsewhere in the repository;
- generation must not rewrite, relocate, or replace the confirmed working `Execution/docker/` stack files unless a separate specification explicitly requires such a change;
- before generation is declared complete, the validating agent must perform a final end-to-end CLI validation run against live observability backends;
- because generation changes Grafana provisioning files and dashboards during normal operation, the validating agent must always recreate the Grafana container before final observability validation so that the generated artifacts are reloaded from disk;
- before the final CLI validation run, the validating agent must start or restart the required local observability and eval-storage stack in this dependency order:
  - PostgreSQL
  - Phoenix
  - Tempo
  - OTEL collector
  - Prometheus
  - Grafana
- Tempo startup may legitimately take about `15` seconds before the readiness API begins returning `ready`, and the validating agent must allow for that startup delay before concluding that Tempo is unhealthy;
- the required backend set for final validation is:
  - PostgreSQL
  - Grafana
  - Tempo
  - Phoenix
  - OTEL collector
  - Prometheus
- the validating agent must not treat a merely started container as healthy without checking successful service-specific readiness behavior;
- successful backend startup for final validation means all of the following are true:
  - PostgreSQL container is running and `pg_isready -U postgres -d rag_eval` reports that the server is accepting connections
  - Phoenix container is running and its HTTP API base responds at `http://localhost:6006/`
  - Tempo container is running and the Tempo readiness API `http://localhost:3200/ready` returns `ready`
  - OTEL collector container is running and the collector metrics endpoint `http://localhost:9464/metrics` returns HTTP `200`
  - Prometheus container is running and the Prometheus readiness API `http://localhost:9090/-/ready` returns `Prometheus Server is Ready.`
  - Grafana container is running and the Grafana health API `http://localhost:3001/api/health` reports `database: ok`
- after the observability stack is confirmed healthy, the validating agent must launch the `rag_runtime` CLI through its normal user-facing entrypoint, submit at least one real request, and wait for the answer;
- final trace correlation to the just-completed CLI run may be established by time window;
- the validating agent may treat a trace as belonging to that CLI run when it appears within the post-request validation window immediately after the answer is returned and matches the expected `rag_runtime` service and root-span shape;
- after that CLI run, final observability validation must confirm through backend APIs that one trace from that run is present in both Tempo and Phoenix and that this trace contains the required spans from:
  - `Specification/codegen/rag_runtime/observability/spans.md`
  - `Specification/codegen/rag_runtime/observability/openinference_spans.md`
- after that CLI run, final observability validation must also confirm through Prometheus query APIs that the run caused emission of at least one required metric family defined in:
  - `Specification/codegen/rag_runtime/observability/metrics.md`
  - `Specification/codegen/rag_runtime/observability/openinference_metrics.md`
- final observability validation requires both:
  - at least one valid trace from the CLI run confirmed through Tempo trace-search or trace-read APIs and Phoenix trace APIs
  - confirmation through Prometheus query APIs that the CLI run produced writes for at least one required metric family
- if container restart, backend verification, CLI execution, or telemetry verification require elevated privileges beyond the initial sandbox, those privileges must be requested explicitly and the final validation must still be completed.

## 5) Error Model

`rag_runtime` must use the `thiserror` crate for error definitions.

Error model structure:

- each main module must define its own error enum;
- module error enums must contain error variants that are specific to that module;
- module error enums encapsulate errors returned by external libraries, transport layers, parsers, or service clients when those errors belong to the module failure domain;
- `rag_runtime` must define one crate-level error enum that encapsulates module-level errors.

Required module-level error enums:

- `InputValidationError`
- `RetrievalError`
- `RerankingError`
- `GenerationError`
- `OrchestrationError`
- `RequestCaptureStoreError`

`OrchestrationError` includes orchestration-owned failures such as empty retrieval output.

Required crate-level error enum:

- `RagRuntimeError`

`RagRuntimeError` is the single public error type at crate boundary.
It must encapsulate module-level errors through dedicated variants.

Example crate-level structure:

- `RagRuntimeError::InputValidation(InputValidationError)`
- `RagRuntimeError::Retrieval(RetrievalError)`
- `RagRuntimeError::Reranking(RerankingError)`
- `RagRuntimeError::Generation(GenerationError)`
- `RagRuntimeError::Orchestration(OrchestrationError)`
- `RagRuntimeError::RequestCaptureStore(RequestCaptureStoreError)`

Interface rule:

- all public methods in module interfaces must return `Result<..., RagRuntimeError>`;
- module-internal logic uses module-specific error enums before converting them into `RagRuntimeError` at the module boundary.

Encapsulation rules:

- a module must not leak raw third-party error types through its public interface;
- third-party and service-specific errors must be wrapped into the corresponding module error enum;
- cross-module propagation must happen only through `RagRuntimeError`.
- error variants must preserve all available error information that can be obtained at the failure point, including underlying source errors, service responses, transport context, invalid values, and other relevant diagnostic fields when available.

Design goals:

- error ownership must match module ownership;
- error messages must be explicit enough for debugging and logging;
- error variants must be stable enough to support future branching and observability;
- the crate boundary must expose one unambiguous error type.

## 6) Shared Types

This section defines the types that move between `rag_runtime` modules.
Only cross-module types belong here.
Types that are private to a single module are defined in that module specification instead.

Required cross-module types:

- user request
- validated user request
- retrieval output
- reranked retrieval output
- reranker kind
- reranker config
- generation request
- generation response
- user response
- retrieval result item
- request capture

Chunk contract:

- retrieved chunks must use the chunk contract defined in `Specification/contracts/chunk/spec.md`;
- the machine-readable schema for the same chunk payload is `Execution/schemas/chunk.schema.json`;
- `rag_runtime` must not define an alternative chunk payload contract that duplicates or diverges from that schema.

Required shared type contracts:

1. `UserRequest`
   - `UserRequest` is the raw request received by `rag_runtime` from the caller;
   - `UserRequest` must contain exactly one field:
     - `query: String`
   - `query` is the raw user-provided request text before validation and normalization;
   - `UserRequest` must not contain validated fields, config values, derived fields, or module-private processing metadata.

2. `ValidatedUserRequest`
   - `ValidatedUserRequest` is returned by `input_validation`;
   - `ValidatedUserRequest` must contain exactly two fields:
     - `query: String`
     - `input_token_count: usize`
   - `query` is the validated and normalized form of `UserRequest.query`;
   - `input_token_count` is the token count computed for `ValidatedUserRequest.query` using the embedding-model-aligned tokenizer defined by the input-validation contract;
   - downstream stages must consume `ValidatedUserRequest` instead of raw `UserRequest`;
   - `retrieval`, `generation`, and later pipeline stages must not consume raw `UserRequest`;
   - `ValidatedUserRequest` must not contain raw input copies, config values, or module-private processing metadata.
   - `retrieval` and `reranking` must consume `ValidatedUserRequest` instead of raw `UserRequest`.

3. `GoldenRetrievalTargets`
   - `GoldenRetrievalTargets` is the per-question golden retrieval record passed from orchestration into retrieval and reranking during evaluated batch execution;
   - `GoldenRetrievalTargets` must contain exactly three fields:
     - `soft_positive_chunk_ids: Vec<Uuid>`
     - `strict_positive_chunk_ids: Vec<Uuid>`
     - `graded_relevance: Vec<GradedChunkRelevance>`
   - `soft_positive_chunk_ids` comes from `questions[<query>].soft_positive_chunk_ids` in the golden retrieval companion file;
   - `strict_positive_chunk_ids` comes from `questions[<query>].strict_positive_chunk_ids` in the golden retrieval companion file;
   - `graded_relevance` comes from `questions[<query>].graded_relevance` in the golden retrieval companion file;
   - `GoldenRetrievalTargets` is populated from the companion file passed through the `--golden-retrievals-file` CLI parameter and defined by:
     - `Specification/contracts/rag_runtime/golden_retrieval_companion.md`
   - the machine-readable schema for that companion file is:
     - `Specification/contracts/rag_runtime/golden_retrieval_companion.schema.json`

4. `GradedChunkRelevance`
   - `GradedChunkRelevance` is the graded-relevance item used inside `GoldenRetrievalTargets`;
   - `GradedChunkRelevance` must contain exactly two fields:
     - `chunk_id: Uuid`
     - `score: f32`
   - `chunk_id` identifies the graded chunk for one question;
   - `score` is the graded relevance label for that chunk as loaded from the golden retrieval companion file.

5. `RetrievalQualityMetrics`
   - `RetrievalQualityMetrics` is the per-request retrieval-quality metric bundle returned by retrieval and reranking during evaluated batch execution;
   - `RetrievalQualityMetrics` must contain exactly the following fields:
     - `evaluated_k: usize`
     - `recall_soft: f32`
     - `recall_strict: f32`
     - `rr_soft: f32`
     - `rr_strict: f32`
     - `ndcg: f32`
     - `first_relevant_rank_soft: Option<usize>`
     - `first_relevant_rank_strict: Option<usize>`
     - `num_relevant_soft: usize`
     - `num_relevant_strict: usize`
   - `evaluated_k` is the effective top-k cutoff used when computing this metric bundle;
   - when `RetrievalQualityMetrics` is returned inside `RetrievalOutput`, `evaluated_k` comes from `Settings.retrieval.top_k`;
   - when `RetrievalQualityMetrics` is returned inside `RerankedRetrievalOutput`, `evaluated_k` comes from `Settings.reranking.final_k`;
   - `RetrievalQualityMetrics` is request-local and must not represent dataset-level aggregates;
   - `RetrievalQualityMetrics` must not hardcode fixed values such as `12` or `4` in the shared type shape.

6. `RetrievalOutput`
   - `RetrievalOutput` is returned by `retrieval`;
   - `RetrievalOutput` must contain exactly three fields:
     - `chunks: Vec<RetrievedChunk>`
     - `metrics: Option<RetrievalQualityMetrics>`
     - `chunking_strategy: String`
   - `chunks` contains the retrieved chunks in retrieval output order;
   - `metrics` contains retrieval-stage retrieval-quality metrics when `GoldenRetrievalTargets` is provided for the current request;
   - `metrics` must be `None` when no golden retrieval targets are provided for the current request;
   - `chunking_strategy` is read from Qdrant collection metadata (`result.config.metadata.chunking_strategy`) on first retrieval call and cached for the lifetime of the retriever instance;
   - `RetrievedChunk` must contain exactly two fields:
     - `chunk: Chunk`
     - `score: f32`
   - `Chunk` must follow the contract from `Specification/contracts/chunk/spec.md`;
   - `score` is the retrieval score returned for the chunk by the retrieval stage;
   - `RetrievalOutput` must not expose raw Qdrant response objects, vector DB transport types, or provider-specific response wrappers.

7. `RerankedRetrievalOutput`
   - `RerankedRetrievalOutput` is returned by `reranking`;
   - `RerankedRetrievalOutput` must contain exactly three fields:
     - `chunks: Vec<RerankedChunk>`
     - `metrics: Option<RetrievalQualityMetrics>`
     - `total_tokens: Option<usize>`
   - `RerankedChunk` must contain exactly three fields:
     - `chunk: Chunk`
     - `retrieval_score: f32`
     - `rerank_score: f32`
   - `retrieval_score` is the score produced by retrieval;
   - `rerank_score` is the final score produced by reranking;
   - `metrics` contains reranking-stage retrieval-quality metrics when `GoldenRetrievalTargets` is provided for the current request;
   - `metrics` must be `None` when no golden retrieval targets are provided for the current request;
   - `total_tokens` is the reranking-stage token count aggregated across all transport calls for the current request;
   - `total_tokens` is provider-reported for transports that return token usage and transport-estimated for transports that do not;
   - `RerankedRetrievalOutput.chunks` must preserve the full reranked candidate set and must not be truncated to generation-context size;
   - configured weights and implementation-specific feature contributions must not be part of this shared type.

8. `RerankerKind`
   - `RerankerKind` is the closed-set shared type that identifies the selected reranker implementation;
   - `RerankerKind` must be a Rust enum;
   - for the current version, `RerankerKind` must contain exactly:
     - `PassThrough`
     - `Heuristic`
     - `CrossEncoder`
   - `RerankerKind` is used by orchestration and request-capture output;
   - in typed runtime settings, reranker selection is expressed by the active `RerankerSettings` enum variant rather than by storing a separate `RerankerKind` field;
   - when `RerankerKind` is needed for orchestration branching, observability, or request-capture output, it must be derived from the active `RerankerSettings` variant;
   - `RerankerKind` must not be represented as an unchecked string in the typed runtime model.

9. `RerankerConfig`
   - `RerankerConfig` is the shared request-capture-facing snapshot of the effective reranker configuration;
   - `RerankerConfig` must be a Rust enum;
   - for the current version, `RerankerConfig` must contain exactly:
     - `PassThrough { final_k: usize }`
     - `Heuristic { final_k: usize, weights: HeuristicWeights }`
     - `CrossEncoder { final_k: usize, cross_encoder: CrossEncoderConfig }`
   - `final_k` is included in all variants because it determines how many chunks are passed to generation and is essential for reproducing evaluation results;
   - `RerankerConfig` must not duplicate `candidate_k` or other retrieval-stage sizing values.

10. `CrossEncoderConfig`
   - `CrossEncoderConfig` is the shared request-capture-facing config snapshot for the cross-encoder reranker;
   - `CrossEncoderConfig` must contain exactly four fields:
     - `model_name: String`
     - `url: String`
     - `total_tokens: Option<usize>`
     - `cost_per_million_tokens: f64`
   - `CrossEncoderConfig` must not duplicate timeout, batch size, retry policy, tokenizer source, or `candidate_k`.
   - provider-specific transport execution behavior is defined in:
     - `Specification/codegen/rag_runtime/reranking/transport_integration.md`

11. `RetrieverKind`
   - `RetrieverKind` is the closed-set shared type that identifies the selected retriever implementation;
   - `RetrieverKind` must be a Rust enum;
   - for the current version, `RetrieverKind` must contain exactly:
     - `Dense`
     - `Hybrid`
   - `RetrieverKind` is used by request-capture output;
   - `RetrieverKind` must not be represented as an unchecked string in the typed runtime model.

12. `RetrieverConfig`
   - `RetrieverConfig` is the shared request-capture-facing snapshot of the effective retriever configuration;
   - `RetrieverConfig` must be a Rust enum;
   - for the current version, `RetrieverConfig` must contain exactly:
     - `Dense(DenseRetrievalIngest)`
     - `Hybrid(HybridRetrievalIngest)`
   - `RetrieverConfig` must capture retrieval identity and strategy-defining fields only;
   - `RetrieverConfig` must include `score_threshold: f32` because it affects which candidates are returned and is essential for reproducing retrieval results;
   - `RetrieverConfig` must include `embedding_endpoint: String` (from `Settings.retrieval.ollama_url`) because it identifies the embedding service, which changes when switching from local to remote models;
   - `RetrieverConfig` must include `chunking_strategy: String` (from `RetrievalOutput.chunking_strategy`) because it identifies how the corpus was chunked, which affects retrieval quality comparisons;
   - `RetrieverConfig` must not duplicate retry policy or `top_k`.

13. `GenerationConfig`
   - `GenerationConfig` is the shared request-capture-facing snapshot of the effective generation configuration;
   - `GenerationConfig` must be a Rust struct;
   - `GenerationConfig` must contain exactly:
     - `model: String`
     - `model_endpoint: String`
     - `temperature: f32`
     - `max_context_chunks: usize`
     - `input_cost_per_million_tokens: f64`
     - `output_cost_per_million_tokens: f64`
   - `model` comes from the active transport settings by pattern-matching `Settings.generation.transport`: `TransportSettings::Ollama(s) => s.model_name` or `TransportSettings::OpenAi(s) => s.model_name`;
   - `model_endpoint` comes from the active transport settings by pattern-matching `Settings.generation.transport`: `TransportSettings::Ollama(s) => s.url` or `TransportSettings::OpenAi(s) => s.url`, and identifies the generation service endpoint;
   - `temperature` comes from `Settings.generation.temperature`;
   - `max_context_chunks` comes from `Settings.generation.max_context_chunks` and determines how many chunks are passed to the generation prompt;
   - `input_cost_per_million_tokens` comes from the active transport settings by pattern-matching `Settings.generation.transport`;
   - `output_cost_per_million_tokens` comes from the active transport settings by pattern-matching `Settings.generation.transport`;
   - `GenerationConfig` must not duplicate timeout, retry policy, tokenizer source, `max_prompt_tokens`, or request-level token counts.

14. `GenerationRequest`
   - `GenerationRequest` is passed from `orchestration` to `generation`;
   - `GenerationRequest` must contain exactly two fields:
     - `query: String`
     - `chunks: Vec<RerankedChunk>`
   - `query` is the validated user query passed into generation;
   - `chunks` are the first `Settings.reranking.final_k` items from `RerankedRetrievalOutput.chunks`, preserving final reranked order;
   - `RerankedChunk` must follow the shared type contract defined in this section;
   - `GenerationRequest` must not contain raw `UserRequest`, raw retrieval transport objects, config values, settings, or pre-rendered untyped JSON model payloads.

15. `GenerationResponse`
   - `GenerationResponse` is returned by `generation`;
   - `GenerationResponse` must contain exactly four fields:
     - `answer: String`
     - `prompt_tokens: usize`
     - `completion_tokens: usize`
     - `total_tokens: usize`
   - `answer` is the final text produced by the generation module for the current request;
   - `prompt_tokens` is the token count of the fully assembled prompt sent to the generation provider;
   - `completion_tokens` is the token count of the final generated answer;
   - `total_tokens` is the sum of `prompt_tokens` and `completion_tokens`;
   - `GenerationResponse` must not contain raw model provider responses, transport-layer metadata, config values, or settings.

16. `UserResponse`
   - `UserResponse` is the final response returned by `rag_runtime` to the caller;
   - `UserResponse` must contain exactly one field:
     - `answer: String`
   - `answer` is the final answer returned to the user after orchestration completes;
   - `UserResponse` must be distinct from `GenerationResponse` even if both currently contain the same field set;
   - `UserResponse` must not expose module-internal response types directly.

17. `RetrievalResultItem`
   - `RetrievalResultItem` is the shared compact retrieval item used inside `RequestCapture`;
   - `RetrievalResultItem` must contain exactly six fields:
     - `chunk_id: String`
     - `document_id: String`
     - `locator: String`
     - `retrieval_score: f32`
     - `rerank_score: f32`
     - `selected_for_generation: bool`
   - `chunk_id` identifies the retrieved chunk;
   - `document_id` identifies the source document that owns the chunk;
   - `locator` is a compact source locator string for the chunk;
   - `retrieval_score` is the original retrieval score returned by retrieval;
   - `rerank_score` is the final score returned by reranking;
   - `selected_for_generation` indicates whether this retrieved chunk was included in the final generation context;
   - `RetrievalResultItem` field source rules are:
     - `chunk_id` comes from `RerankedChunk.chunk.chunk_id`;
     - `document_id` comes from `RerankedChunk.chunk.doc_id`;
     - `locator` is derived from `RerankedChunk.chunk.page_start` and `RerankedChunk.chunk.page_end` using the compact page-label rule:
       - `page:<page_start>` when `page_start == page_end`
       - `pages:<page_start>-<page_end>` when `page_start != page_end`
     - `retrieval_score` comes from `RerankedChunk.retrieval_score`;
     - `rerank_score` comes from `RerankedChunk.rerank_score`;
     - `selected_for_generation` is `true` when the corresponding reranked chunk is included in the first `Settings.reranking.final_k` items passed into `GenerationRequest.chunks`;
   - `RetrievalResultItem` must not contain raw chunk text, raw provider responses, or unbounded debug payloads.

18. `RequestCapture`
   - `RequestCapture` is the canonical shared request-level capture type for one successfully completed request;
   - `RequestCapture` exists to provide stable structured input to downstream eval processing;
   - `RequestCapture` is a composite shared type assembled from:
     - orchestration-owned request-entry values
     - `UserRequest`
     - `ValidatedUserRequest`
     - `RetrievalOutput`
     - `RerankedRetrievalOutput`
     - `GenerationResponse`
     - selected values from `Settings.pipeline`
     - selected values from `Settings.retrieval`
     - selected values from `Settings.generation`
   - `RequestCapture` is not the output type of one single business module in the same sense as `ValidatedUserRequest`, `RetrievalOutput`, or `GenerationResponse`;
   - `RequestCapture` must contain exactly the following top-level fields:
     - `request_id: String`
     - `trace_id: String`
     - `received_at: DateTime<Utc>` or semantically equivalent UTC timestamp type
     - `raw_query: String`
     - `normalized_query: String`
     - `input_token_count: usize`
     - `pipeline_config_version: String`
     - `corpus_version: String`
     - `retriever_version: String`
     - `retriever_kind: RetrieverKind`
     - `retriever_config: RetrieverConfig`
     - `embedding_model: String`
     - `prompt_template_id: String`
     - `prompt_template_version: String`
     - `generation_model: String`
     - `generation_config: GenerationConfig`
     - `reranker_kind: RerankerKind`
     - `reranker_config: Option<RerankerConfig>`
     - `top_k_requested: usize`
     - `retrieval_results: Vec<RetrievalResultItem>`
     - `final_answer: String`
     - `prompt_tokens: usize`
     - `completion_tokens: usize`
     - `total_tokens: usize`
     - `retrieval_stage_metrics: Option<RetrievalQualityMetrics>`
     - `reranking_stage_metrics: Option<RetrievalQualityMetrics>`
   - `RequestCapture` field source rules are:
     - `request_id` is one UUID v4 generated by orchestration for the current request before root span creation;
     - `trace_id` is extracted from the active OpenTelemetry trace context for the current request, using the current span context, and serialized into its canonical string form;
     - when no active trace context is available, `trace_id` must be the sentinel string `NA`;
     - `received_at` is the UTC timestamp recorded by orchestration once at request entry before any downstream stage execution begins;
     - `raw_query` comes from `UserRequest.query`;
     - `normalized_query` comes from `ValidatedUserRequest.query`;
     - `input_token_count` comes from `ValidatedUserRequest.input_token_count`;
     - `pipeline_config_version` comes from `Settings.pipeline.config_version`;
     - `corpus_version` comes from `Settings.retrieval.ingest.corpus_version`;
     - `retriever_version` comes from `Settings.retrieval.retriever_version`;
     - `retriever_kind` is `RetrieverKind::Dense` when `Settings.retrieval.ingest = RetrievalIngest::Dense(DenseRetrievalIngest)`;
     - `retriever_kind` is `RetrieverKind::Hybrid` when `Settings.retrieval.ingest = RetrievalIngest::Hybrid(HybridRetrievalIngest)`;
     - `retriever_config` is assembled from `Settings.retrieval` plus `RetrievalOutput.chunking_strategy` (fetched from Qdrant collection metadata by the retriever);
     - `retriever_config.chunking_strategy` comes from `RetrievalOutput.chunking_strategy`;
     - `embedding_model` comes from `Settings.retrieval.ingest.embedding_model_name`;
     - `prompt_template_id` comes from `prompt_template.id` defined in `Specification/codegen/rag_runtime/prompts.json` and copied into the generated code as a prompt-template constant;
     - `prompt_template_version` comes from `prompt_template.version` defined in `Specification/codegen/rag_runtime/prompts.json` and copied into the generated code as a prompt-template constant;
     - `generation_model` comes from the active transport settings by pattern-matching `Settings.generation.transport`;
     - `generation_config` is assembled from `Settings.generation` via `capture_generation_config`;
     - `reranker_kind` is derived by pattern-matching `Settings.reranking.reranker`;
     - `reranker_config` is `Some(RerankerConfig::PassThrough { final_k: Settings.reranking.final_k })` when `Settings.reranking.reranker = RerankerSettings::PassThrough`;
     - `reranker_config` is `Some(RerankerConfig::Heuristic { final_k: Settings.reranking.final_k, weights: settings.weights.clone() })` when `Settings.reranking.reranker = RerankerSettings::Heuristic(settings)`;
     - `reranker_config` is `Some(RerankerConfig::CrossEncoder { final_k: Settings.reranking.final_k, cross_encoder: CrossEncoderConfig { model_name, url, total_tokens: RerankedRetrievalOutput.total_tokens, cost_per_million_tokens } })` when `Settings.reranking.reranker = RerankerSettings::CrossEncoder(settings)`, where `model_name`, `url`, and `cost_per_million_tokens` come from the active `CrossEncoderTransportSettings` variant;
     - `top_k_requested` comes from `Settings.retrieval.top_k`;
     - `retrieval_results` comes from `RerankedRetrievalOutput.chunks` in final reranked order;
     - `final_answer` comes from `GenerationResponse.answer`;
     - `prompt_tokens` comes from `GenerationResponse.prompt_tokens`;
     - `completion_tokens` comes from `GenerationResponse.completion_tokens`;
     - `total_tokens` comes from `GenerationResponse.total_tokens`;
     - `retrieval_stage_metrics` comes from `RetrievalOutput.metrics`; `None` when no golden retrieval companion was provided for the current batch run;
     - `reranking_stage_metrics` comes from `RerankedRetrievalOutput.metrics`; `None` when no golden retrieval companion was provided for the current batch run.
   - `RequestCapture` field meaning and invariants are defined by:
     - `Specification/contracts/rag_runtime/request_capture.md`
   - the machine-readable schema for `RequestCapture` is:
     - `Execution/rag_runtime/schemas/request_capture.schema.json`
   - `RequestCapture` is created only for successfully completed requests;
   - `RequestCapture` must not model partial failed request states;
   - `RequestCapture.retrieval_results` must preserve final reranked order;
   - `RequestCapture.retrieval_results` must not be represented by parallel arrays;
   - `RequestCapture.total_tokens` must equal `RequestCapture.prompt_tokens + RequestCapture.completion_tokens`;
   - `RequestCapture.retrieval_results` must contain at least one item with `selected_for_generation = true`;
   - `RequestCapture.retrieval_stage_metrics` and `RequestCapture.reranking_stage_metrics` must be either both `Some` or both `None`.

Type design rules:

- `UserRequest` and `ValidatedUserRequest` must be separate types;
- raw input must not be passed directly from request intake to retrieval or generation;
- `GoldenRetrievalTargets`, `GradedChunkRelevance`, and `RetrievalQualityMetrics` are allowed interface types because they cross orchestration, retrieval, reranking, and request-capture boundaries during evaluated batch execution;
- `RetrievedChunk` must be a distinct shared type instead of exposing raw retrieval provider objects at module boundaries;
- `RetrievalOutput` must be a dedicated type instead of passing a naked vector across module boundaries;
- `RerankedRetrievalOutput` must be a dedicated type instead of overloading `RetrievalOutput` with final generation-facing rerank semantics;
- `RerankerKind`, `RerankerConfig`, `CrossEncoderConfig`, `RetrieverKind`, and `RetrieverConfig` are allowed shared types because they cross runtime-settings, orchestration, and request-capture boundaries;
- `GenerationConfig` is an allowed shared type because it crosses runtime-settings, orchestration, and request-capture boundaries;
- `GenerationRequest` and `GenerationResponse` must be explicit types;
- `UserResponse` must be distinct from `GenerationResponse`, because crate-level response semantics and generator-level response semantics are not the same boundary.
- `RequestCapture` must be a distinct shared type rather than a database-row type, untyped JSON object, or trace-derived map.

Minimality rules:

- do not introduce extra shared types unless they cross a module boundary;
- do not duplicate the chunk schema in `rag_runtime`;
- if retrieval-specific metadata is not needed outside `retrieval`, it stays in the retrieval module and is not promoted to a shared type.
- `RetrievalResultItem` and `RequestCapture` are allowed shared types because they cross the orchestration-to-request-capture boundary.

## 7) Configuration

`rag_runtime` must use a dedicated TOML runtime config file:

- `Execution/rag_runtime/rag_runtime.toml`

The machine-readable schema for this config is:

- `Execution/rag_runtime/schemas/rag_runtime_config.schema.json`

The human-readable contract for this config is:

- `Specification/contracts/rag_runtime/config.md`

`rag_runtime.toml` is the source of truth for `rag_runtime` behavior.
It must be validated against `Execution/rag_runtime/schemas/rag_runtime_config.schema.json` before runtime request processing starts.

Settings model rules:

- `rag_runtime` must define one internal resolved config type named `Settings`;
- `Settings` must represent the merged configuration state used by the crate after config loading;
- each config section must correspond to one field of `Settings`;
- each field of `Settings` must use its own typed section struct rather than an untyped map;
- `Settings` merges values from `rag_runtime.toml` and ingest config into one resolved object.
- `Settings` includes values loaded from environment variables when those values are part of the runtime contract;
- module section types must contain all settings required by their module interfaces, including values resolved from ingest config when those values are part of the module contract.
- required section field types are:
  - `PipelineSettings`
  - `InputValidationSettings`
  - `RetrievalSettings`
  - `RerankingSettings`
  - `GenerationSettings`
  - `ObservabilitySettings`
  - `RequestCaptureSettings`

Required `InputValidationSettings` fields:

- `max_query_tokens: usize` - loaded from `rag_runtime.toml`
- `tokenizer_source: String` - loaded from `rag_runtime.toml` as a Hugging Face repo id
- `reject_empty_query: bool` - loaded from `rag_runtime.toml`
- `trim_whitespace: bool` - loaded from `rag_runtime.toml`
- `collapse_internal_whitespace: bool` - loaded from `rag_runtime.toml`

Required `RetrievalSettings` fields:

- `ollama_url: String` - loaded from environment variable `OLLAMA_URL`
- `qdrant_url: String` - loaded from environment variable `QDRANT_URL`
- `retriever_version: String` - loaded from `rag_runtime.toml`
- `top_k: usize` - loaded from `rag_runtime.toml`
- `score_threshold: f32` - loaded from `rag_runtime.toml`
- `embedding_retry` - loaded from `rag_runtime.toml`
- `qdrant_retry` - loaded from `rag_runtime.toml`
- `ingest: RetrievalIngest` - loaded from the CLI-supplied ingest config according to `rag_runtime.toml retrieval.kind`

`RetrievalSettings` rules:

- `RetrievalSettings` remains the single typed retrieval settings section used by the retrieval stage;
- `RetrievalSettings` contains the runtime-owned retrieval fields plus one ingest-derived field named `ingest`;
- `ingest` must be typed as `RetrievalIngest`.

`RetrievalIngest` enum variants:

- `Dense(DenseRetrievalIngest)`
- `Hybrid(HybridRetrievalIngest)`

`RetrievalIngest` variant-selection rules:

- the concrete ingest variant is selected by `retrieval.kind` from `rag_runtime.toml`;
- when `retrieval.kind = "dense"`, the CLI-supplied ingest config must be deserialized into `RetrievalIngest::Dense(DenseRetrievalIngest)`;
- when `retrieval.kind = "hybrid"`, the CLI-supplied ingest config must be deserialized into `RetrievalIngest::Hybrid(HybridRetrievalIngest)`;
- if `retrieval.kind` and the CLI-supplied ingest config do not match, runtime startup must fail before request processing starts with a runtime error.

Required `DenseRetrievalIngest` fields:

- `embedding_model_name: String` - loaded from ingest config `embedding.model.name`
- `embedding_dimension: usize` - loaded from ingest config `embedding.model.dimension`
- `qdrant_collection_name: String` - loaded from ingest config `qdrant.collection.name`
- `qdrant_vector_name: String` - loaded from ingest config `qdrant.collection.vector_name`
- `corpus_version: String` - loaded from ingest config `pipeline.corpus_version`

Required `HybridRetrievalIngest` fields:

- `embedding_model_name: String` - loaded from ingest config `embedding.model.name`
- `embedding_dimension: usize` - loaded from ingest config `embedding.model.dimension`
- `qdrant_collection_name: String` - loaded from ingest config `qdrant.collection.name` as the unsuffixed base collection name used to derive the effective hybrid retrieval collection name
- `dense_vector_name: String` - loaded from ingest config `qdrant.collection.dense_vector_name`
- `sparse_vector_name: String` - loaded from ingest config `qdrant.collection.sparse_vector_name`
- `corpus_version: String` - loaded from ingest config `pipeline.corpus_version`
- `tokenizer_library: String` - loaded from ingest config `sparse.tokenizer.library`
- `tokenizer_source: String` - loaded from ingest config `sparse.tokenizer.source`
- `tokenizer_revision: Option<String>` - loaded from ingest config `sparse.tokenizer.revision`, when present
- `preprocessing_kind: String` - loaded from ingest config `sparse.preprocessing.kind`
- `lowercase: bool` - loaded from ingest config `sparse.preprocessing.lowercase`
- `min_token_length: usize` - loaded from ingest config `sparse.preprocessing.min_token_length`
- `vocabulary_path: String` - loaded from the repository-root-relative vocabulary directory path used to derive the vocabulary artifact filename for ingest config `qdrant.collection.name`
- `strategy: RetrievalStrategy` - loaded from ingest config according to `sparse.strategy.kind`

`RetrievalStrategy` enum variants:

- `BagOfWords(BagOfWordsRetrievalStrategy)`
- `Bm25Like(Bm25LikeRetrievalStrategy)`

`RetrievalStrategy` variant-selection rules:

- the concrete strategy variant is selected by ingest config `sparse.strategy.kind`;
- when ingest config `sparse.strategy.kind = "bag_of_words"`, `HybridRetrievalIngest.strategy` must be deserialized into `RetrievalStrategy::BagOfWords(BagOfWordsRetrievalStrategy)`;
- when ingest config `sparse.strategy.kind = "bm25_like"`, `HybridRetrievalIngest.strategy` must be deserialized into `RetrievalStrategy::Bm25Like(Bm25LikeRetrievalStrategy)`;
- if ingest config `sparse.strategy.kind` and `HybridRetrievalIngest.strategy` do not match, runtime startup must fail before request processing starts with a runtime error.

Required `BagOfWordsRetrievalStrategy` fields:

- `kind: String` - loaded from ingest config `sparse.strategy.kind`
- `version: String` - loaded from ingest config `sparse.strategy.version`
- `query_weighting: String` - loaded from ingest config `sparse.bag_of_words.query`

Required `Bm25LikeRetrievalStrategy` fields:

- `kind: String` - loaded from ingest config `sparse.strategy.kind`
- `version: String` - loaded from ingest config `sparse.strategy.version`
- `query_weighting: String` - loaded from ingest config `sparse.bm25_like.query`
- `k1: f32` - loaded from ingest config `sparse.bm25_like.k1`
- `b: f32` - loaded from ingest config `sparse.bm25_like.b`
- `idf_smoothing: String` - loaded from ingest config `sparse.bm25_like.idf_smoothing`
- `term_stats_path: String` - loaded from the repository-root-relative term-stats directory path used to derive the BM25 term-stats artifact filename for the effective Qdrant collection name

Required `RetrievalSettings` field-mapping rules:

- `ollama_url` <- environment variable `OLLAMA_URL`
- `qdrant_url` <- environment variable `QDRANT_URL`
- `retriever_version` <- `rag_runtime.toml retrieval.retriever_version`
- `top_k` <- `rag_runtime.toml retrieval.top_k`
- `score_threshold` <- `rag_runtime.toml retrieval.score_threshold`
- `embedding_retry` <- `rag_runtime.toml retrieval.embedding_retry`
- `qdrant_retry` <- `rag_runtime.toml retrieval.qdrant_retry`
- `ingest` <- `RetrievalIngest::Dense(DenseRetrievalIngest)` when `rag_runtime.toml retrieval.kind = "dense"`
- `ingest` <- `RetrievalIngest::Hybrid(HybridRetrievalIngest)` when `rag_runtime.toml retrieval.kind = "hybrid"`

Required `DenseRetrievalIngest` field-mapping rules:

- `embedding_model_name` <- ingest config `embedding.model.name`
- `embedding_dimension` <- ingest config `embedding.model.dimension`
- `qdrant_collection_name` <- ingest config `qdrant.collection.name`
- `qdrant_vector_name` <- ingest config `qdrant.collection.vector_name`
- `corpus_version` <- ingest config `pipeline.corpus_version`

Required `HybridRetrievalIngest` field-mapping rules:

- `embedding_model_name` <- ingest config `embedding.model.name`
- `embedding_dimension` <- ingest config `embedding.model.dimension`
- `qdrant_collection_name` <- ingest config `qdrant.collection.name` as the unsuffixed base collection name used to derive the effective hybrid retrieval collection name
- `dense_vector_name` <- ingest config `qdrant.collection.dense_vector_name`
- `sparse_vector_name` <- ingest config `qdrant.collection.sparse_vector_name`
- `corpus_version` <- ingest config `pipeline.corpus_version`
- `tokenizer_library` <- ingest config `sparse.tokenizer.library`
- `tokenizer_source` <- ingest config `sparse.tokenizer.source`
- `tokenizer_revision` <- ingest config `sparse.tokenizer.revision`, when present
- `preprocessing_kind` <- ingest config `sparse.preprocessing.kind`
- `lowercase` <- ingest config `sparse.preprocessing.lowercase`
- `min_token_length` <- ingest config `sparse.preprocessing.min_token_length`
- `vocabulary_path` <- repository-root-relative vocabulary directory path used to derive the vocabulary artifact filename for ingest config `qdrant.collection.name`
- `strategy` <- `RetrievalStrategy::BagOfWords(BagOfWordsRetrievalStrategy)` when ingest config `sparse.strategy.kind = "bag_of_words"`
- `strategy` <- `RetrievalStrategy::Bm25Like(Bm25LikeRetrievalStrategy)` when ingest config `sparse.strategy.kind = "bm25_like"`

Required `BagOfWordsRetrievalStrategy` field-mapping rules:

- `kind` <- ingest config `sparse.strategy.kind`
- `version` <- ingest config `sparse.strategy.version`
- `query_weighting` <- ingest config `sparse.bag_of_words.query`

Required `Bm25LikeRetrievalStrategy` field-mapping rules:

- `kind` <- ingest config `sparse.strategy.kind`
- `version` <- ingest config `sparse.strategy.version`
- `query_weighting` <- ingest config `sparse.bm25_like.query`
- `k1` <- ingest config `sparse.bm25_like.k1`
- `b` <- ingest config `sparse.bm25_like.b`
- `idf_smoothing` <- ingest config `sparse.bm25_like.idf_smoothing`
- `term_stats_path` <- repository-root-relative term-stats directory path used to derive the BM25 term-stats artifact filename for the effective Qdrant collection name

Retry settings representation rules:

- retry settings must be deserialized into typed Rust config structures;
- strategy selection such as `backoff = "exponential"` must not remain an unchecked string in request execution logic;
- runtime execution must use a typed retry policy derived from `RetrievalSettings.embedding_retry` and `RetrievalSettings.qdrant_retry`.

Required `GenerationSettings` fields:

- `transport: TransportSettings` - loaded from `rag_runtime.toml` and env
- `tokenizer_source: String` - loaded from `rag_runtime.toml` as a Hugging Face repo id
- `temperature: f32` - loaded from `rag_runtime.toml`
- `max_context_chunks: usize` - loaded from `rag_runtime.toml`
- `max_prompt_tokens: usize` - loaded from `rag_runtime.toml`
- `retry` - loaded from `rag_runtime.toml`

`TransportSettings` enum variants:

- `Ollama(OllamaTransportSettings)`
- `OpenAi(OpenAiTransportSettings)`

Required `OllamaTransportSettings` fields:

- `url: String` - loaded from environment variable `OLLAMA_URL`
- `model_name: String` - loaded from `rag_runtime.toml [generation.ollama]`
- `timeout_sec: u64` - loaded from `rag_runtime.toml [generation.ollama]`
- `input_cost_per_million_tokens: f64` - loaded from `rag_runtime.toml [generation.ollama]`; default `0.0`
- `output_cost_per_million_tokens: f64` - loaded from `rag_runtime.toml [generation.ollama]`; default `0.0`

Required `OpenAiTransportSettings` fields:

- `url: String` - loaded from environment variable `OPENAI_COMPATIBLE_URL`
- `api_key: String` - loaded from environment variable `TOGETHER_API_KEY`
- `model_name: String` - loaded from `rag_runtime.toml [generation.openai]`; must be non-empty
- `timeout_sec: u64` - loaded from `rag_runtime.toml [generation.openai]`
- `input_cost_per_million_tokens: f64` - loaded from `rag_runtime.toml [generation.openai]`; default `0.0`
- `output_cost_per_million_tokens: f64` - loaded from `rag_runtime.toml [generation.openai]`; default `0.0`

Required `RerankingSettings` fields:

- `reranker: RerankerSettings` - loaded from `rag_runtime.toml` as the typed active reranker settings enum
- `candidate_k: usize` - derived from `Settings.retrieval.top_k`
- `final_k: usize` - derived from `Settings.generation.max_context_chunks`

`RerankingSettings` rules:

- `RerankingSettings` is the typed settings section used only by the reranking stage;
- `RerankingSettings` includes reranker-visible `candidate_k` and `final_k` fields in the typed runtime settings model;
- `candidate_k` is derived from `Settings.retrieval.top_k`;
- `final_k` is derived from `Settings.generation.max_context_chunks`;
- `candidate_k` and `final_k` must not be declared as separate fields inside the `[reranking]` TOML section;
- `reranker` must not remain an untyped TOML map after config loading;
- for the current version, `reranker` must deserialize into one crate-owned typed enum named `RerankerSettings`;

`RerankerSettings` enum variants:

- `PassThrough`
- `Heuristic(HeuristicRerankerSettings)`
- `CrossEncoder(CrossEncoderRerankerSettings)`

Required `HeuristicRerankerSettings` fields:

- `weights: HeuristicWeights` - loaded from `[reranking.weights]` in `rag_runtime.toml`

`HeuristicWeights` rules:

- `HeuristicWeights` must remain a crate-owned typed struct;
- `HeuristicWeights` must contain exactly:
  - `retrieval_score: f32`
  - `query_term_coverage: f32`
  - `phrase_match_bonus: f32`
  - `title_section_match_bonus: f32`

Required `CrossEncoderRerankerSettings` fields:

- `transport: CrossEncoderTransportSettings` - loaded from `rag_runtime.toml [reranking.cross_encoder].transport_kind`, the matching provider subtree, and provider-owned environment variables

`CrossEncoderTransportSettings` enum variants:

- `MixedbreadAi(MixedbreadAiCrossEncoderTransportSettings)`
- `VoyageAi(VoyageAiCrossEncoderTransportSettings)`

`CrossEncoderTransportSettings` rules:

- the active transport variant is selected by `rag_runtime.toml [reranking.cross_encoder].transport_kind`;
- `transport_kind = "mixedbread-ai"` must construct `CrossEncoderTransportSettings::MixedbreadAi(...)`;
- `transport_kind = "voyageai"` must construct `CrossEncoderTransportSettings::VoyageAi(...)`;

Required `MixedbreadAiCrossEncoderTransportSettings` fields:

- `url: String` - loaded from environment variable `RERANKER_ENDPOINT`
- `model_name: String` - loaded from `rag_runtime.toml [reranking.cross_encoder.mixedbread-ai]`
- `timeout_sec: u64` - loaded from `rag_runtime.toml [reranking.cross_encoder.mixedbread-ai]`
- `batch_size: usize` - loaded from `rag_runtime.toml [reranking.cross_encoder.mixedbread-ai]`
- `cost_per_million_tokens: f64` - loaded from `rag_runtime.toml [reranking.cross_encoder.mixedbread-ai]`; default `0.0`
- `tokenizer_source: String` - loaded from `rag_runtime.toml [reranking.cross_encoder.mixedbread-ai]` as a Hugging Face repo id
- `max_attempts: usize` - loaded from `rag_runtime.toml [reranking.cross_encoder.mixedbread-ai]`
- `backoff: RetryBackoff` - loaded from `rag_runtime.toml [reranking.cross_encoder.mixedbread-ai]`

Required `VoyageAiCrossEncoderTransportSettings` fields:

- `url: String` - loaded from environment variable `VOYAGEAI_RERANK_URL`
- `api_key: String` - loaded from environment variable `VOYAGEAI_API_KEY`
- `model_name: String` - loaded from `rag_runtime.toml [reranking.cross_encoder.voyageai]`
- `timeout_sec: u64` - loaded from `rag_runtime.toml [reranking.cross_encoder.voyageai]`
- `batch_size: usize` - loaded from `rag_runtime.toml [reranking.cross_encoder.voyageai]`
- `cost_per_million_tokens: f64` - loaded from `rag_runtime.toml [reranking.cross_encoder.voyageai]`; default `0.0`
- `max_attempts: usize` - loaded from `rag_runtime.toml [reranking.cross_encoder.voyageai]`
- `backoff: RetryBackoff` - loaded from `rag_runtime.toml [reranking.cross_encoder.voyageai]`

Required `ObservabilitySettings` fields:

- `tracing_enabled: bool` - loaded from `rag_runtime.toml`
- `metrics_enabled: bool` - loaded from `rag_runtime.toml`
- `tracing_endpoint: String` - loaded from environment variable `TRACING_ENDPOINT`
- `metrics_endpoint: String` - loaded from environment variable `METRICS_ENDPOINT`
- `trace_batch_scheduled_delay_ms: u64` - loaded from `rag_runtime.toml`
- `metrics_export_interval_ms: u64` - loaded from `rag_runtime.toml`

Required `RequestCaptureSettings` fields:

- `postgres_url: String` - loaded from environment variable `POSTGRES_URL`

`RequestCaptureSettings` rules:

- `RequestCaptureSettings` is the typed settings section used only by the request-capture persistence boundary;
- `RequestCaptureSettings` must not include request payload fields, eval fields, or settings that belong to retrieval, generation, or observability;
- for the current version, `RequestCaptureSettings` contains exactly one field:
  - `postgres_url`
- `postgres_url` is the PostgreSQL connection string used for writes to the `request_captures` table.

Config loading rules:

- config loading must use the Rust `config` crate: `https://docs.rs/config/latest/config/`;
- config sources must be deserialized into typed Rust structs;
- environment variables are included in `Settings` through `config::Environment`;
- if an env file is used, it must be loaded into process environment with the `dotenvy` crate before `config::Environment` is applied;
- if an env file is used, env loading must happen exactly once in the startup path;
- startup code must not duplicate dotenv loading across both the CLI entrypoint and config-construction path;
- for the current version, `OLLAMA_URL`, `QDRANT_URL`, `POSTGRES_URL`, `TRACING_ENDPOINT`, and `METRICS_ENDPOINT` must be loaded into `Settings` from environment variables;
- if any of those environment variables is missing, runtime initialization must fail;
- environment keys are validated by typed startup logic;
- `rag_runtime` must not validate a separate env file schema for those keys;
- ingest config must be validated against `Execution/ingest/schemas/dense_ingest_config.schema.json` before ingest-derived values are merged into `Settings`;
- explicit separate post-read validation logic is not required if config loading and deserialization already enforce the declared contract;
- startup validation must allow `RetrievalSettings.top_k > GenerationSettings.max_context_chunks`;
- `Settings.reranking.candidate_k` may be greater than `Settings.reranking.final_k`;
- failure to read, merge, or deserialize config sources into `Settings` is a startup error.

Configuration boundary rules:

- `rag_runtime` config defines runtime request-processing behavior;
- `rag_runtime` config must not duplicate collection compatibility fields that are already defined in ingest config;
- for the current version, ingest config is the source of truth for embedding model name, embedding vector dimension, Qdrant collection name, Qdrant vector name, and corpus version;
- for the current version, `rag_runtime.toml` is the source of truth for `input_validation.tokenizer_source`, `generation.tokenizer_source`, and `generation.max_prompt_tokens`;
- those values must be read from `Execution/ingest/dense/ingest.toml` according to `Execution/ingest/schemas/dense_ingest_config.schema.json` and `Specification/contracts/ingest/dense_config.md`;
- `rag_runtime` must not redefine ingest-owned fields in `rag_runtime.toml`.

Validation rules:

- invalid `rag_runtime.toml` is a whole-run error;
- if TOML parsing fails, schema validation fails, a required field is missing, or a config value violates contract semantics, `rag_runtime` must fail before request processing starts.

Runtime initialization rules:

- runtime initialization happens exactly once before request handling begins;
- startup must initialize runtime-owned tokenizer resources for `input_validation` from `Settings.input_validation.tokenizer_source`;
- startup must initialize runtime-owned tokenizer resources for `generation` from `Settings.generation.tokenizer_source`;
- one runtime-owned tokenizer instance per tokenizer-owning module is allowed;
- tokenizer instances are allowed to exist in multiple modules when they belong to different module-owned runtime resources;
- no module creates a tokenizer per request;
- module-owned tokenizer instances must be reused across all requests handled by the same owning runtime component;
- failure to load either tokenizer is a startup error;
- request handling must not lazily initialize either tokenizer on the first request.

Test-isolation rules for the current version:

- production request handling must persist request-capture rows through the real `RequestCaptureStore`;
- test execution must not write deterministic test traffic into a live `request_captures` table;
- if unit tests execute the real orchestration/runtime request path, the generated code must route request-capture persistence through an internal no-op or mocked boundary for test builds;
- this test-only request-capture boundary must remain internal and must not become part of the public `rag_runtime` API;
- production runtime behavior outside test builds must remain unchanged and must keep real request-capture persistence enabled.

## 8) Public API

`RagRuntime` is the only public crate-level type that must be exposed as the main entrypoint of the crate.

Required public API:

- `RagRuntime::from_config_paths(...)`
- `RagRuntime::handle_request(...)`

Required public method signatures:

```rust
impl RagRuntime {
    pub async fn from_config_paths(
        rag_runtime_config_path: impl AsRef<std::path::Path>,
        ingest_config_path: impl AsRef<std::path::Path>,
    ) -> Result<Self, RagRuntimeError>;

    pub async fn handle_request(
        &self,
        request: UserRequest,
    ) -> Result<UserResponse, RagRuntimeError>;
}
```

API rules:

- `RagRuntime::from_config_paths(...)` must be an async constructor;
- `RagRuntime::from_config_paths(...)` must read `rag_runtime` config and ingest config from explicit paths;
- `RagRuntime::from_config_paths(...)` must build the internal `Settings` object from those config sources;
- `RagRuntime::from_config_paths(...)` must fail if either config cannot be read or deserialized into `Settings`;
- `RagRuntime::handle_request(...)` must be an async request-processing method;
- `RagRuntime::handle_request(...)` must consume `UserRequest`;
- `RagRuntime::handle_request(...)` must return an owned `UserResponse`;
- all public crate API methods must return `RagRuntimeError` on failure.

Public boundary rules:

- no other module type is required to be public at crate boundary;
- internal modules define additional traits and structs only as internal implementation details unless those types are promoted explicitly later;
- module interfaces must use owned domain types, not raw JSON objects, maps, or untyped payloads.

## 9) CLI Contract

`rag_runtime` must provide a CLI entrypoint for interactive request processing.

Required CLI arguments:

- `--config`: path to `Execution/rag_runtime/rag_runtime.toml`
- `--ingest-config`: path to ingest config file used as the source of truth for embedding and Qdrant compatibility settings
- `--questions-file`: optional path to a newline-delimited batch query file for non-interactive sequential execution
- `--golden-retrievals-file`: optional path to a unified golden retrieval companion file used during evaluated batch execution

CLI rules:

- both `--config` and `--ingest-config` are required;
- default paths must not be assumed;
- invalid CLI arguments are a startup error;
- CLI startup must initialize `RagRuntime` through `RagRuntime::from_config_paths(...)`;
- after successful startup, the CLI must either enter interactive stdin mode or execute batch mode from `--questions-file`;
- `--golden-retrievals-file` must not be used in interactive mode;
- when `--golden-retrievals-file` is provided, `rag_runtime` must load and validate that file against:
  - `Specification/contracts/rag_runtime/golden_retrieval_companion.schema.json`
- in interactive mode, the CLI must wait for user input interactively;
- in interactive mode, each user input must be converted into `UserRequest` and processed through `RagRuntime::handle_request(...)`;
- in interactive mode, the CLI must continue accepting and processing requests until the user explicitly terminates the session;
- in batch mode, the CLI must read newline-delimited questions from `--questions-file`, ignore blank lines, and process the remaining queries sequentially through `RagRuntime::handle_request(...)`;
- in batch mode, one runtime initialization must be reused across the whole file rather than recreated per question;
- request processing must not require passing the query as a CLI argument.

Session boundary rules:

- runtime initialization happens once at CLI startup, not once per request;
- each request must be processed independently through the declared crate request flow;
- the reserved user command `exit` must terminate the interactive session explicitly;
- termination must be user-driven rather than implicit after one request.

## 10) Unit Test Generation Rules

Unit tests must be generated together with the current Rust implementation.

`Specification/codegen/rag_runtime/unit_tests.md` is the single source of truth for:

- required generated unit tests;
- required shared test helpers;
- required unit-test generation rules;
- required coverage tooling;
- required coverage interpretation rules;
- required coverage thresholds.

Required rules:

- the generated Rust source must include the required unit tests defined in `Specification/codegen/rag_runtime/unit_tests.md` in the same generation pass as the module implementation;
- code generation for `rag_runtime` is incomplete if the required unit tests defined in `Specification/codegen/rag_runtime/unit_tests.md` are missing;
- code generation for `rag_runtime` is incomplete if any required module test set exists only as comments, TODO markers, prose, pseudo-tests, placeholder test functions without assertions, or empty test modules;
- code generation for `rag_runtime` is incomplete if the generated crate does not satisfy the minimum executable test counts defined in `Specification/codegen/rag_runtime/unit_tests.md`;
- `rag_runtime.md` must not redefine module-specific unit-test cases, shared helper rules, HTTP test methodology, or coverage thresholds that are already defined in `Specification/codegen/rag_runtime/unit_tests.md`.

## 11) General Implementation Guidance

These rules apply to the full `rag_runtime` crate implementation.
They define crate-level implementation constraints and are intentionally broader than module-specific rules.

Implementation structure rules:

- do not keep strategy-like config fields as unchecked strings after deserialization when the runtime contract already restricts them to a closed set of behaviors;
- shared dependency behaviors such as retry/backoff must be implemented through reusable internal helpers or policy abstractions rather than duplicating handwritten retry loops in individual call sites;
- when the specification mandates a specific retry/backoff crate, runtime code must use that crate rather than a custom handwritten retry implementation.

- the implementation must be modular;
- each main module must own its own public interface, internal logic, and error type;
- cross-module interaction must happen through explicit shared types;
- business logic must not be collapsed into one large top-level function or one large file;
- module-specific logic stays in the corresponding module specification and implementation area.
- the crate must use an explicit Rust module layout under `Execution/rag_runtime/`.

Required code layout:

- `Execution/rag_runtime/src/lib.rs` - crate root
- `Execution/rag_runtime/src/main.rs` - CLI entrypoint
- `Execution/rag_runtime/src/config/` - config loading and `Settings` types
- `Execution/rag_runtime/src/input_validation/` - `input_validation` module
- `Execution/rag_runtime/src/retrieval/` - `retrieval` module
- `Execution/rag_runtime/src/reranking/` - `reranking` module
- `Execution/rag_runtime/src/generation/` - `generation` module
- `Execution/rag_runtime/src/orchestration/` - `orchestration` module
- `Execution/rag_runtime/src/models/` - shared domain types
- `Execution/rag_runtime/src/errors/` - crate-level and shared error definitions
- `Execution/rag_runtime/src/test_support.rs` - internal test-only shared helper module when required by `unit_tests.md`

Layout rules:

- `lib.rs` must expose the public crate API centered on `RagRuntime`;
- `main.rs` must implement the CLI contract and delegate request processing to `RagRuntime`;
- shared cross-module types are defined under `src/models/`;
- module-private types remain inside the corresponding module directories unless they are promoted explicitly to shared types.
- the `generation` module must use explicit internal decomposition under `Execution/rag_runtime/src/generation/` rather than one large implementation file;
- for the current version, `Execution/rag_runtime/src/generation/` must include:
  - `mod.rs`
  - `transport.rs`
  - `ollama.rs`
  - `openai.rs`
  - `tokenizer.rs`

Responsibility rules:

- `orchestration` must coordinate the pipeline but must not absorb retrieval, validation, or generation logic that belongs to other modules;
- `input_validation` must own request normalization and validation logic;
- `retrieval` must own query embedding and vector search logic;
- `reranking` must own post-retrieval candidate scoring and ordering logic;
- `generation` must own model request assembly at the model boundary and answer generation logic.

Determinism and hidden-behavior rules:

- the implementation must avoid hidden heuristics that are not described in the corresponding specifications;
- request transformations must be explicit and traceable to the module that owns them;
- configuration-driven behavior must come from declared config fields, not from hardcoded hidden policy;
- the generated crate must pass `cargo check`.
- the generated crate must pass `cargo test`.
- the generated crate must include exactly one end-to-end success-path test.
- the required end-to-end success-path test must be implemented as a Rust integration test under the generated crate and must use the public crate interface or the binary interface without calling module internals directly.
- the required success-path end-to-end test assumes that the configured Qdrant collection already exists and is populated with embeddings compatible with the configured embedding model.
- this required success-path end-to-end test is an environment-backed smoke test, not a self-contained fixture-setup test.
- the required success-path end-to-end smoke test must be generated as a normal non-ignored Rust integration test;
- if executing that required environment-backed smoke test needs elevated privileges or access beyond the initial sandbox, those privileges must be requested explicitly and the test must still be executed;
- the required end-to-end smoke test remains part of the required validation suite and must not be excluded from compliance by marking it `#[ignore]`;
- if behavior depends on upstream contracts, those contracts must be referenced explicitly rather than redefined implicitly in code.

Boundary rules:

- module boundaries must be preserved in code structure and in error ownership;
- modules must not reach into each other's private internals instead of using declared interfaces;
- shared types must be used consistently at module boundaries;
- `UserRequest` must not bypass `input_validation`;
- downstream stages must operate on validated input only.

Failure-domain rules:

- whole-run failures must remain separated from request-level failures;
- request validation failures must remain separated from retrieval and generation failures;
- a module must report failures through its own error domain before conversion to `RagRuntimeError`;
- fallback or recovery paths must not silently widen the scope of failure handling.

Config and contract rules:

- `rag_runtime` must validate its own config before request processing starts;
- `rag_runtime` must treat referenced contracts and schemas as source of truth for structures it does not own;
- the crate must not duplicate or fork the chunk payload contract;
- the crate must not duplicate ingest-owned compatibility settings in its own config.

Settings propagation rules:

- `Settings` must be available to all main modules;
- module interfaces must receive settings explicitly;
- each module must read only its own settings from the corresponding typed section of `Settings`;
- modules must not parse raw TOML, raw config values, or raw config maps by themselves after startup;
- config values must be converted into typed settings before they are passed into module logic.

Extensibility rules:

- the implementation is easy to extend with additional validation rules, retrieval strategies, generation options, or later pipeline stages;
- extensions must be added through explicit modules, types, config fields, and contracts rather than through ad hoc conditionals spread across the crate;
- additional future features must be added as explicit extensions, not as hidden special cases in existing modules.

## 12) Index Of Module Specifications

The `rag_runtime` specification set is split across the following module files:

- `Specification/codegen/rag_runtime/input_validation.md` - `input_validation` module
- `Specification/codegen/rag_runtime/retrieve/integration.md` - `retrieve` integration and shared contract
- `Specification/codegen/rag_runtime/retrieve/dense_retrieval.md` - dense retrieval implementation
- `Specification/codegen/rag_runtime/retrieve/hybrid_retrieval.md` - hybrid retrieval implementation
- `Specification/codegen/rag_runtime/reranking/integration.md` - `reranking` integration and shared contract
- `Specification/codegen/rag_runtime/reranking/heuristic.md` - heuristic reranker baseline implementation
- `Specification/codegen/rag_runtime/generation.md` - `generation` module
- `Specification/codegen/rag_runtime/orchestration.md` - `orchestration` module
- `Specification/codegen/rag_runtime/rag_runtime.md` - crate-level `rag_runtime` specification

## 13) Non-Goals / Out of Scope

The current `rag_runtime` specification does not include:

- hybrid retrieval;
- BM25 or keyword-only retrieval;
- prompt template management beyond the current generation contract;
- long-term conversation memory;
- SQL or non-vector secondary storage lookup as part of the main retrieval path;
- hidden fallback from one retrieval strategy to another;
- hidden fallback from retrieval to generation-only answering;
- duplication of chunk schema or ingest-owned compatibility settings inside `rag_runtime`;
- module implementations that bypass declared shared types, contracts, or validation boundaries.

If any of these capabilities are added later, they must be introduced explicitly through updated module specifications, config contracts, and crate-level scope updates.

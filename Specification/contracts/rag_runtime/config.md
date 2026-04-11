# RAG Runtime Config Contract

This document defines the contract for `rag_runtime.toml`.

## Format

`rag_runtime.toml` is a TOML config file for `rag_runtime`.
It is the source of truth for `rag_runtime` behavior.

Invalid `rag_runtime.toml`:
- `rag_runtime.toml` is invalid if TOML does not parse, if a required section or field is missing, if a value type does not match the contract, or if a value violates the constraints of this contract
- this is a whole-run error
- `rag_runtime` must fail immediately before request processing starts

## Expected Structure

`[pipeline]`
- `config_version`: version of the current `rag_runtime` configuration

`[input_validation]`
- `max_query_tokens`: maximum allowed user query length in tokens
- `tokenizer_source`: Hugging Face repo id for the tokenizer used by input validation
- `reject_empty_query`: whether empty query input is rejected
- `trim_whitespace`: whether leading and trailing whitespace is removed before validation
- `collapse_internal_whitespace`: whether repeated internal whitespace is collapsed before validation

`[retrieval]`
- `kind`: retrieval implementation kind
- `retriever_version`: version identifier of the retrieval strategy or retrieval implementation used by this runtime
- `top_k`: maximum number of chunks returned by retrieval
- `score_threshold`: minimum retrieval score required for a chunk to be returned

`[retrieval.embedding_retry]`
- `max_attempts`: maximum number of retry attempts for embedding requests made by retrieval
- `backoff`: backoff strategy type for embedding requests made by retrieval

`[retrieval.qdrant_retry]`
- `max_attempts`: maximum number of retry attempts for Qdrant requests made by retrieval
- `backoff`: backoff strategy type for Qdrant requests made by retrieval

`[generation]`
- `transport_kind`: selects which generation transport implementation to use
- `tokenizer_source`: Hugging Face repo id for the tokenizer used for generation token accounting
- `temperature`: sampling temperature for answer generation
- `max_context_chunks`: maximum number of retrieved chunks that may be included in generation context
- `max_prompt_tokens`: maximum number of tokens allowed in the fully assembled chat prompt

`[generation.retry]`
- `max_attempts`: maximum number of retry attempts for generation requests

`[generation.ollama]`
- `model_name`: generation model name for the Ollama transport
- `timeout_sec`: per-request HTTP timeout in seconds
- `input_cost_per_million_tokens`: input token cost in USD per 1M tokens; default `0.0`
- `output_cost_per_million_tokens`: output token cost in USD per 1M tokens; default `0.0`
- required when `generation.transport_kind = ollama`

`[generation.openai]`
- `model_name`: generation model name for the OpenAI-compatible transport
- `timeout_sec`: per-request HTTP timeout in seconds
- `input_cost_per_million_tokens`: input token cost in USD per 1M tokens; default `0.0`
- `output_cost_per_million_tokens`: output token cost in USD per 1M tokens; default `0.0`
- required when `generation.transport_kind = openai`

`[reranking]`
- `kind`: reranker implementation kind

`[reranking.weights]`
- implementation-specific heuristic weights used by the selected reranker
- for the current version, this subtree must contain:
  - `retrieval_score`
  - `query_term_coverage`
  - `phrase_match_bonus`
  - `title_section_match_bonus`

`[reranking.cross_encoder]`
- `model_name`: cross-encoder model name
- `timeout_sec`: per-request timeout in seconds for cross-encoder API calls
- `batch_size`: maximum number of candidate chunks sent in one cross-encoder API call

`[reranking.cross_encoder.retry]`
- `max_attempts`: maximum number of retry attempts for cross-encoder API calls
- `backoff`: backoff strategy type for cross-encoder API calls

`[observability]`
- `tracing_enabled`: whether OTEL tracing initialization is enabled
- `metrics_enabled`: whether OTEL metrics initialization is enabled
- `trace_batch_scheduled_delay_ms`: batch trace export delay in milliseconds
- `metrics_export_interval_ms`: periodic metrics export interval in milliseconds

## Separation Of Responsibility

`rag_runtime.toml` defines runtime behavior for request processing.
It must not duplicate collection compatibility fields that are already defined in ingest configuration.

For the current version, the ingest config is the source of truth for:
- embedding model name
- embedding vector dimension
- Qdrant collection name
- Qdrant vector name
- corpus version

For the current version, `rag_runtime` must read those values from:
- config file: `Execution/ingest/dense/ingest.toml`
- schema: `Execution/ingest/schemas/dense_ingest_config.schema.json`
- contract: `Specification/contracts/ingest/dense_config.md`

`rag_runtime.toml` must not redefine those fields.

## Semantics Of Config Values

`input_validation.max_query_tokens`
- maximum allowed token length of the incoming user query after normalization steps that are enabled by config
- if query length exceeds this value, request validation must fail

`input_validation.tokenizer_source`
- Hugging Face repo id for the tokenizer used by input validation
- `rag_runtime` must resolve it to `https://huggingface.co/<tokenizer_source>/resolve/main/tokenizer.json`
- the value must not be interpreted as a local file path or as a direct URL

`input_validation.reject_empty_query`
- `true` means:
  - empty query input must be rejected during input validation
- `false` would mean:
  - empty query input is allowed to continue into later stages

`input_validation.trim_whitespace`
- `true` means:
  - leading and trailing whitespace must be removed before validation and downstream processing

`input_validation.collapse_internal_whitespace`
- `true` means:
  - repeated internal whitespace must be collapsed before downstream processing

`retrieval.top_k`
- maximum number of chunks that retrieval may return
- `retrieval.top_k` may exceed `generation.max_context_chunks`
- when reranking is enabled, retrieval may return a larger candidate set than the final generation context size

`retrieval.kind`
- selects the retrieval implementation used by the runtime
- for the current version, valid values must include `dense` and `hybrid`

`retrieval.retriever_version`
- version identifier of the retrieval strategy or retrieval implementation used by this runtime
- this value is an explicit runtime-owned version label and must not be inferred from crate version, binary version, or dependency versions

`retrieval.score_threshold`
- minimum retrieval score accepted by the retrieval stage
- chunks below this score must not appear in retrieval output

`retrieval.embedding_retry.max_attempts`
- maximum number of retry attempts for embedding requests performed by retrieval

`retrieval.embedding_retry.backoff`
- retry backoff strategy for retrieval embedding requests
- runtime execution of this strategy must use the `backon` crate
- custom handwritten retry/backoff implementations are forbidden
- the strategy must be converted into a typed internal representation before request execution
- `exponential` means:
  - delay between retry attempts must grow exponentially
  - implementation may choose a specific formula, but growth must be exponential, not constant or linear
  - bounded jitter must be applied to retry delays
  - jitter must not remove the exponential growth property

`retrieval.qdrant_retry.max_attempts`
- maximum number of retry attempts for Qdrant requests performed by retrieval

`retrieval.qdrant_retry.backoff`
- retry backoff strategy for retrieval Qdrant requests
- runtime execution of this strategy must use the `backon` crate
- custom handwritten retry/backoff implementations are forbidden
- the strategy must be converted into a typed internal representation before request execution
- `exponential` means:
  - delay between retry attempts must grow exponentially
  - implementation may choose a specific formula, but growth must be exponential, not constant or linear
  - bounded jitter must be applied to retry delays
  - jitter must not remove the exponential growth property

`generation.transport_kind`
- selects the generation transport implementation used by the runtime
- for the current version, valid values are `ollama` and `openai`
- config deserialization must map:
  - `ollama` -> `TransportSettings::Ollama`
  - `openai` -> `TransportSettings::OpenAi`
- the orchestrator uses this value to instantiate the correct transport and pass it to `Generator::new`

`generation.ollama.model_name`
- model name passed to the Ollama API in the `model` request field
- required when `generation.transport_kind = ollama`

`generation.openai.model_name`
- model name passed to the OpenAI-compatible API in the `model` request field
- must be a non-empty string
- required when `generation.transport_kind = openai`

`generation.ollama.input_cost_per_million_tokens`
- input token cost in USD per 1 million tokens
- used for cost accounting in observability; does not affect request behavior
- defaults to `0.0` if not set

`generation.ollama.output_cost_per_million_tokens`
- output token cost in USD per 1 million tokens
- used for cost accounting in observability; does not affect request behavior
- defaults to `0.0` if not set

`generation.openai.input_cost_per_million_tokens`
- input token cost in USD per 1 million tokens
- used for cost accounting in observability; does not affect request behavior
- defaults to `0.0` if not set; cost metrics emit `0.0` when omitted

`generation.openai.output_cost_per_million_tokens`
- output token cost in USD per 1 million tokens
- used for cost accounting in observability; does not affect request behavior
- defaults to `0.0` if not set; cost metrics emit `0.0` when omitted

`generation.tokenizer_source`
- Hugging Face repo id for the tokenizer used for generation token accounting
- `rag_runtime` must resolve it to `https://huggingface.co/<tokenizer_source>/resolve/main/tokenizer.json`
- the value must not be interpreted as a local file path or as a direct URL
- generation tokenizer loading follows the same runtime-loading model as tokenizer loading for `input_validation`
- the generation tokenizer must be loaded once during runtime initialization
- the same generation tokenizer instance must be used for prompt-token counting and completion-token counting across all requests in the same runtime session
- failure to load the generation tokenizer is a startup error

`generation.temperature`
- sampling temperature passed to the generation model

`generation.max_context_chunks`
- upper bound on how many retrieved chunks may be included in the generation context
- orchestration must not pass more than this number of chunks to generation

`generation.max_prompt_tokens`
- maximum allowed token count of the fully assembled chat prompt
- token counting must use the generation tokenizer from `generation.tokenizer_source`
- if the assembled chat prompt exceeds this value, generation must fail before the provider request is sent

`generation.retry.max_attempts`
- maximum number of retry attempts for generation provider requests
- this value is passed to the active transport implementation

`generation.ollama.timeout_sec`
- per-request HTTP timeout in seconds for Ollama generation requests
- must be `>= 1`
- required when `generation.transport_kind = ollama`

`generation.openai.timeout_sec`
- per-request HTTP timeout in seconds for OpenAI-compatible generation requests
- must be `>= 1`
- required when `generation.transport_kind = openai`

`reranking.weights`
- typed config subtree used only by the heuristic reranker implementation
- these values belong to reranking behavior and must not be duplicated under retrieval or generation
- candidate count for reranking still comes from `retrieval.top_k`
- final generation context size still comes from `generation.max_context_chunks`
- the typed runtime `RerankingSettings` may still expose derived `candidate_k` and `final_k` fields populated from those existing sections
- `candidate_k` and `final_k` must not be declared inside `[reranking]`
- for the current version, `reranking.weights` must deserialize into one typed Rust struct with exactly:
  - `retrieval_score: f32`
  - `query_term_coverage: f32`
  - `phrase_match_bonus: f32`
  - `title_section_match_bonus: f32`

`reranking.cross_encoder.transport_kind`
- selects the concrete transport used by the cross-encoder reranker
- for the current version, valid values must include `mixedbread-ai` and `voyageai`
- config deserialization must map:
  - `mixedbread-ai` -> `CrossEncoderTransportSettings::MixedbreadAi(...)`
  - `voyageai` -> `CrossEncoderTransportSettings::VoyageAi(...)`

`reranking.cross_encoder.mixedbread-ai`
- provider-specific config subtree for the Mixedbread-backed cross-encoder transport
- must contain:
  - `model_name`
  - `timeout_sec`
  - `batch_size`
  - `cost_per_million_tokens`
  - `tokenizer_source`
  - `max_attempts`
  - `backoff`

`reranking.cross_encoder.voyageai`
- provider-specific config subtree for the VoyageAI-backed cross-encoder transport
- must contain:
  - `model_name`
  - `timeout_sec`
  - `batch_size`
  - `cost_per_million_tokens`
  - `max_attempts`
  - `backoff`

`reranking.cross_encoder`
- typed config subtree used by the cross-encoder reranker implementation
- for the current version, it must deserialize into one typed Rust struct with exactly:
  - `transport_kind: String`
- for the current version, that typed struct is named `RuntimeCrossEncoderSettings`

`reranking.kind`
- selects the reranker implementation used between retrieval and generation
- for the current version, valid values must include `pass_through`, `heuristic`, and `cross_encoder`
- config deserialization must map:
  - `pass_through` -> `RerankerSettings::PassThrough`
  - `heuristic` -> `RerankerSettings::Heuristic(...)`
  - `cross_encoder` -> `RerankerSettings::CrossEncoder(...)`
- `pass_through` means the reranking stage remains present but preserves retrieval order and copies retrieval scores into rerank scores

`reranking.cross_encoder.mixedbread-ai.batch_size`
- maximum number of candidate texts per Mixedbread transport call
- must be `>= 1`

`reranking.cross_encoder.mixedbread-ai.timeout_sec`
- per-request HTTP timeout in seconds for Mixedbread cross-encoder requests
- must be `>= 1`

`reranking.cross_encoder.mixedbread-ai.max_attempts`
- maximum number of retry attempts for Mixedbread cross-encoder requests

`reranking.cross_encoder.mixedbread-ai.backoff`
- retry backoff strategy for Mixedbread cross-encoder requests
- runtime execution of this strategy must use exponential backoff

`reranking.cross_encoder.voyageai.batch_size`
- maximum number of candidate texts per VoyageAI transport call
- must be `>= 1`

`reranking.cross_encoder.voyageai.timeout_sec`
- per-request HTTP timeout in seconds for VoyageAI cross-encoder requests
- must be `>= 1`

`reranking.cross_encoder.voyageai.max_attempts`
- maximum number of retry attempts for VoyageAI cross-encoder requests

`reranking.cross_encoder.voyageai.backoff`
- retry backoff strategy for VoyageAI cross-encoder requests
- runtime execution of this strategy must use exponential backoff
- `exponential` means:
  - delay between retry attempts must grow exponentially
  - bounded jitter must be applied to retry delays
  - jitter must not remove the exponential growth property

`reranking.cross_encoder.mixedbread-ai.tokenizer_source`
- Hugging Face repo id used to load the tokenizer for local token estimation
- required for the current Mixedbread transport implementation
- the value must not be interpreted as a direct URL or local filesystem path

`reranking.cross_encoder.mixedbread-ai.cost_per_million_tokens`
- non-negative reranking token price used for downstream cost calculation

`reranking.cross_encoder.voyageai.cost_per_million_tokens`
- non-negative reranking token price used for downstream cost calculation

`observability.tracing_enabled`
- `true` means:
  - tracing initialization must run during startup
- `false` means:
  - tracing initialization must not run during startup

`observability.metrics_enabled`
- `true` means:
  - metrics initialization must run during startup
- `false` means:
  - metrics initialization must not run during startup

`observability.trace_batch_scheduled_delay_ms`
- batch trace export delay in milliseconds
- this value must configure the batch span processor scheduled delay

`observability.metrics_export_interval_ms`
- metrics export interval in milliseconds
- this value must configure `PeriodicReader`

## Environment-backed Observability Settings

The following runtime settings are loaded from environment variables:

- `ObservabilitySettings.tracing_endpoint` <- `TRACING_ENDPOINT`
- `ObservabilitySettings.metrics_endpoint` <- `METRICS_ENDPOINT`

Both values are OTLP collector gRPC ingress URLs.

## Environment-backed Request Capture Settings

The following runtime settings are loaded from environment variables:

- `RequestCaptureSettings.postgres_url` <- `POSTGRES_URL`

`POSTGRES_URL` is the PostgreSQL connection string used by the request capture persistence module.

## Environment-backed Reranking Settings

The following reranking settings are loaded from environment variables:

- `MixedbreadAiCrossEncoderTransportSettings.url` <- `RERANKER_ENDPOINT`
- `VoyageAiCrossEncoderTransportSettings.url` <- `VOYAGEAI_RERANK_URL`
- `VoyageAiCrossEncoderTransportSettings.api_key` <- `VOYAGEAI_API_KEY`

`RERANKER_ENDPOINT` is the base HTTP endpoint for the Mixedbread-backed cross-encoder reranker service.

`VOYAGEAI_RERANK_URL` is the base HTTP endpoint for the VoyageAI reranking API.

`VOYAGEAI_API_KEY` is the API key for the VoyageAI reranking API.

## Environment-backed Generation Settings

The following generation settings are loaded from environment variables:

- `OllamaSettings.url` <- `OLLAMA_URL`
- `OpenAiSettings.url` <- `OPENAI_COMPATIBLE_URL`
- `OpenAiSettings.api_key` <- `TOGETHER_API_KEY`

`OLLAMA_URL` is the base HTTP endpoint for the local Ollama inference server.

`OPENAI_COMPATIBLE_URL` is the base HTTP endpoint for the OpenAI-compatible generation endpoint
(e.g. `https://api.together.xyz`).

`TOGETHER_API_KEY` is the API key for the Together OpenAI-compatible generation endpoint.

Only the env vars for the active `generation.transport_kind` are required at startup.
The runtime must not fail on startup due to a missing env var for an inactive transport.

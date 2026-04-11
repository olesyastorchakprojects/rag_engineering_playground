# Request Capture Contract

## Purpose

This document defines the data contract for `RequestCapture`.

`RequestCapture` is the canonical domain record for one successfully processed request.
It exists to provide stable, schema-driven input to the eval engine.

`RequestCapture` is not:

- a trace;
- a span payload contract;
- a database-specific row shape;
- a storage-specific JSON format.

This contract defines what `RequestCapture` means semantically.
Storage schemas and runtime serialization must follow this contract.

## Scope

This document defines:

- the semantic purpose of `RequestCapture`;
- when `RequestCapture` is created;
- required fields;
- retrieval item structure;
- field semantics;
- safety rules;
- invariants.

This document does not define:

- SQL table schema;
- JSON schema;
- exact Rust module layout;
- persistence backend implementation;
- ownership of runtime modules;
- observability instrumentation details.

## Creation Rule

`RequestCapture` is created only for a successfully completed request.

Rules:

- `RequestCapture` is produced only after the request has successfully passed through the pipeline and reached the request capture stage;
- failed or prematurely terminated requests do not produce `RequestCapture`;
- request failure history remains the responsibility of the observability stack and runtime error handling.

This contract intentionally does not model partial or failed request capture states.

## Required Top-Level Fields

`RequestCapture` contains the following required top-level fields.

### Identity

- `request_id`
- `trace_id`
- `received_at`

### Input

- `raw_query`
- `normalized_query`
- `input_token_count`

### Versions

- `pipeline_config_version`
- `corpus_version`
- `retriever_version`
- `retriever_kind`
- `retriever_config`
- `embedding_model`
- `prompt_template_id`
- `prompt_template_version`
- `generation_model`
- `reranker_kind`
- `reranker_config`

### Retrieval

- `top_k_requested`
- `retrieval_results`

### Generation

- `final_answer`
- `prompt_tokens`
- `completion_tokens`
- `total_tokens`

## Optional Top-Level Fields

`RequestCapture` contains the following optional top-level fields.

### Retrieval Quality Metrics

- `retrieval_stage_metrics`
- `reranking_stage_metrics`

## Retrieval Quality Metrics Structure

`retrieval_stage_metrics` and `reranking_stage_metrics` are both of type `Option<RetrievalQualityMetrics>`.

`RetrievalQualityMetrics` contains:

- `evaluated_k`
- `recall_soft`
- `recall_strict`
- `rr_soft`
- `rr_strict`
- `ndcg`
- `first_relevant_rank_soft`
- `first_relevant_rank_strict`
- `num_relevant_soft`
- `num_relevant_strict`

### Retrieval Quality Metrics Field Semantics

`evaluated_k`

- the effective top-k cutoff used when computing metrics for the current stage.

`recall_soft`

- soft Recall@k for the current stage; fraction of soft-positive golden chunk ids found in the top-k output.

`recall_strict`

- strict Recall@k for the current stage; fraction of strict-positive golden chunk ids found in the top-k output.

`rr_soft`

- soft Reciprocal Rank@k for the current stage; `1 / rank` of the first soft-positive chunk in the top-k output, or `0` if none found.

`rr_strict`

- strict Reciprocal Rank@k for the current stage; `1 / rank` of the first strict-positive chunk in the top-k output, or `0` if none found.

`ndcg`

- nDCG@k for the current stage; graded ranking quality score normalized against the ideal ranking from the golden dataset.

`first_relevant_rank_soft`

- 1-based rank of the first soft-positive chunk in the top-k output; `null` when no soft-positive chunk was found in the top-k output.

`first_relevant_rank_strict`

- 1-based rank of the first strict-positive chunk in the top-k output; `null` when no strict-positive chunk was found in the top-k output.

`num_relevant_soft`

- count of soft-positive golden chunk ids found in the top-k output.

`num_relevant_strict`

- count of strict-positive golden chunk ids found in the top-k output.

Metric formulas and deduplication rules are defined in:

- `Specification/codegen/rag_runtime/retrieval_metrics.md`

## Retrieval Result Structure

`retrieval_results` is an ordered list of compact retrieval records.

Parallel arrays are forbidden.

Each retrieval item contains:

- `chunk_id`
- `document_id`
- `locator`
- `retrieval_score`
- `rerank_score`
- `selected_for_generation`

### Retrieval Item Semantics

`chunk_id`

- identifier of the retrieved chunk.

`document_id`

- identifier of the source document that owns the chunk.

`locator`

- compact location descriptor for the chunk, suitable for later analysis and drill-down.

`retrieval_score`

- dense retrieval score returned for the chunk before reranking.

`rerank_score`

- final reranking score used to order candidates for generation and request capture output.

`selected_for_generation`

- `true` when the chunk was included in the generation context;
- `false` when the chunk was retrieved but not selected for the final generation context.

## Field Semantics

### `request_id`

- primary identifier for one processed request.

### `trace_id`

- required trace identifier associated with the same request;
- when an active OpenTelemetry trace context is available, `trace_id` uses its canonical string form;
- when no active trace context is available, `trace_id` must be the sentinel string `NA`.

### `received_at`

- timestamp representing when the request entered the runtime request path.

### `raw_query`

- original user query before normalization.

### `normalized_query`

- final normalized query used downstream after input validation and normalization.

### `input_token_count`

- token count computed for the normalized query.

### `pipeline_config_version`

- version of the active pipeline configuration.

### `corpus_version`

- version of the retrieval corpus used for this request.

### `retriever_version`

- version identifier for the retrieval strategy or retrieval implementation in use.

### `retriever_kind`

- typed identifier of the retriever implementation used for the request;
- semantically this field is the shared enum `RetrieverKind`, not an unchecked free-form string;
- for the current version, the allowed semantic values are:
  - `Dense`
  - `Hybrid`

### `retriever_config`

- structured snapshot of the effective retriever configuration used for the request;
- semantically this field is `RetrieverConfig`;
- `retriever_config` must capture retrieval identity and strategy-defining fields;
- `retriever_config` must not include service base URLs, retry settings, `top_k`, or `score_threshold`;
- for the current version, the allowed values are:
  - `RetrieverConfig::Dense(DenseRetrievalIngest)`
  - `RetrieverConfig::Hybrid(HybridRetrievalIngest)`
- when serialized as JSON, dense retrieval requires the shape:
  ```json
  {
    "kind": "Dense",
    "embedding_model_name": "qwen3-embedding:0.6b",
    "embedding_dimension": 1024,
    "qdrant_collection_name": "chunks_dense_qwen3",
    "qdrant_vector_name": "default",
    "corpus_version": "v1"
  }
  ```
- when serialized as JSON, hybrid retrieval requires the shape:
  ```json
  {
    "kind": "Hybrid",
    "embedding_model_name": "qwen3-embedding:0.6b",
    "embedding_dimension": 1024,
    "qdrant_collection_name": "chunks_hybrid_structural_qwen3_bow",
    "dense_vector_name": "dense",
    "sparse_vector_name": "sparse",
    "corpus_version": "v1",
    "tokenizer_library": "tokenizers",
    "tokenizer_source": "Qwen/Qwen3-Embedding-0.6B",
    "tokenizer_revision": null,
    "preprocessing_kind": "tokenized_text",
    "lowercase": true,
    "min_token_length": 2,
    "vocabulary_path": "Execution/ingest/hybrid/artifacts/vocabularies/chunks_hybrid_structural_qwen3__sparse_vocabulary.json",
    "strategy": {
      "...": "..."
    }
  }
  ```
- when `retriever_config.kind = "Hybrid"` and `strategy.kind = "bag_of_words"`, the required JSON shape for `strategy` is:
  ```json
  {
    "kind": "bag_of_words",
    "version": "v1",
    "query_weighting": "binary_presence"
  }
  ```
- when `retriever_config.kind = "Hybrid"` and `strategy.kind = "bm25_like"`, the required JSON shape for `strategy` is:
  ```json
  {
    "kind": "bm25_like",
    "version": "v1",
    "query_weighting": "string",
    "k1": 1.2,
    "b": 0.75,
    "idf_smoothing": "string",
    "term_stats_path": "Execution/ingest/hybrid/artifacts/term_stats/chunks_hybrid_structural_qwen3_bm25__term_stats.json"
  }
  ```

### `embedding_model`

- identifier of the embedding model used by retrieval.

### `prompt_template_id`

- identifier of the prompt template used for generation.

### `prompt_template_version`

- version of the prompt template used for generation.

### `generation_model`

- identifier of the generation model used for the request.

### `generation_config`

- structured snapshot of the effective generation configuration used for the request;
- always present; must not be absent or null;
- semantically this field is `GenerationConfig` as defined in `Specification/codegen/rag_runtime/rag_runtime.md`;
- when serialized as JSON, the required shape is:
  ```json
  {
    "model": "qwen2.5:1.5b-instruct-ctx32k",
    "model_endpoint": "http://ollama:11434",
    "temperature": 0.0,
    "max_context_chunks": 4,
    "input_cost_per_million_tokens": 0.0,
    "output_cost_per_million_tokens": 0.0
  }
  ```
- all six fields are required; no additional fields are allowed;
- `model` must be a non-empty string;
- `model_endpoint` must be a non-empty string;
- `temperature` must be a non-negative number;
- `max_context_chunks` must be a positive integer.
- `input_cost_per_million_tokens` must be a non-negative number.
- `output_cost_per_million_tokens` must be a non-negative number.

### `reranker_kind`

- typed identifier of the reranker implementation used for the request;
- semantically this field is the shared enum `RerankerKind`, not an unchecked free-form string;
- for the current version, the allowed semantic values are:
  - `PassThrough`
  - `Heuristic`
  - `CrossEncoder`

### `reranker_config`

- optional structured snapshot of the effective reranker configuration used for the request;
- for the current version, it is present for heuristic and cross-encoder reranking;
- for pass-through reranking it must be absent;
- semantically this field is `Option<RerankerConfig>`;
- for the current version, the allowed present values are:
  - `RerankerConfig::Heuristic { final_k, weights }`
  - `RerankerConfig::CrossEncoder { final_k, cross_encoder }`
- when serialized as JSON, the current required shape is:
  ```json
  {
    "kind": "Heuristic",
    "final_k": 4,
    "weights": {
      "retrieval_score": <number>,
      "query_term_coverage": <number>,
      "phrase_match_bonus": <number>,
      "title_section_match_bonus": <number>
    }
  }
  ```
- for cross-encoder reranking, the required JSON shape is:
  ```json
  {
    "kind": "CrossEncoder",
    "final_k": 4,
    "cross_encoder": {
      "model_name": "mixedbread-ai/mxbai-rerank-base-v2",
      "url": "http://mxbai-reranker:8000",
      "total_tokens": 321,
      "cost_per_million_tokens": 0.0
    }
  }
  ```
- `final_k` must be present in all non-null reranker config variants;
- for cross-encoder reranking, `cross_encoder.total_tokens` is the reranking-stage token count returned by the transport layer for the current request;
- for cross-encoder reranking, `cross_encoder.cost_per_million_tokens` is the configured token price carried forward for downstream eval-cost computation;
- `total_cost_usd` must not be stored in `RequestCapture`; downstream eval logic computes it from token count and price.

### `top_k_requested`

- retrieval top-k requested by the runtime for this request.

### `final_answer`

- final validated answer returned by the runtime.

### `prompt_tokens`

- token count of the final prompt sent to generation.

### `completion_tokens`

- token count of the final generated answer content.

### `total_tokens`

- total token count for generation, defined as prompt tokens plus completion tokens.

### `retrieval_stage_metrics`

- per-request retrieval-quality metric bundle computed after the retrieval stage, before reranking;
- present only when a golden retrieval companion file was provided for the current batch run;
- absent when no golden retrieval companion was provided.

### `reranking_stage_metrics`

- per-request retrieval-quality metric bundle computed after the reranking stage, using the final reranked output;
- present only when a golden retrieval companion file was provided for the current batch run;
- absent when no golden retrieval companion was provided.

## Safety Rules

`RequestCapture` must not contain:

- secrets;
- API keys;
- authorization headers;
- raw environment variable values;
- raw provider response bodies;
- raw prompt text;
- raw retrieved chunk text;
- arbitrary debug blobs.

`retrieval_stage_metrics` and `reranking_stage_metrics` must not contain:

- raw chunk text;
- raw query content;
- raw golden dataset entries;
- raw provider response data.

`RequestCapture` is an eval-ingestion record, not a forensic dump.

## Invariants

The following invariants are required.

### Success-only invariant

One `RequestCapture` corresponds to one successfully completed request.

### Identity invariant

`request_id` and `trace_id` are both required.
`trace_id` does not replace `request_id`.

### Token invariant

`total_tokens = prompt_tokens + completion_tokens`

### Retrieval ordering invariant

`retrieval_results` must preserve final reranked order.

### Retrieval structure invariant

`retrieval_results` must be represented as a list of retrieval items.
Parallel arrays are forbidden.

### Selection invariant

At least one retrieval item must have `selected_for_generation = true`.

### Retrieval quality metrics invariant

`retrieval_stage_metrics` and `reranking_stage_metrics` must be either both present or both absent.

Both fields are absent when no golden retrieval companion file was provided for the batch run.

Both fields are present when a golden retrieval companion file was provided and a matching golden entry existed for the current request.

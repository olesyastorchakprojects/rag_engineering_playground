# Request Captures Storage Contract

## Purpose

This document defines the database storage contract for `request_captures`.

This contract maps the semantic `RequestCapture` contract into a relational representation suitable for PostgreSQL.

The semantic source of truth remains:

- `Specification/contracts/rag_runtime/request_capture.md`

This document defines:

- the table shape for `request_captures`;
- column-level storage rules;
- storage-specific metadata columns;
- JSONB storage rules for nested request capture data;
- key, index, and constraint rules.

## Storage Model

The database representation of `RequestCapture` uses one table:

- `request_captures`

Nested retrieval data is stored in:

- `retrieval_results jsonb`

This contract intentionally does not normalize retrieval items into a child table.

Rationale:

- eval scripts are expected to read request-level records and process retrieval items outside SQL analytics;
- retrieval items are part of one compact request-level payload;
- JSONB keeps the storage model close to the semantic contract while avoiding premature relational decomposition.

## Table Shape

The `request_captures` table contains:

- semantic columns that directly represent `RequestCapture` fields;
- storage metadata columns used only by database storage.

### Semantic Columns

- `request_id text primary key`
- `trace_id text not null`
- `received_at timestamptz not null`
- `raw_query text not null`
- `normalized_query text not null`
- `input_token_count integer not null`
- `pipeline_config_version text not null`
- `corpus_version text not null`
- `retriever_version text not null`
- `embedding_model text not null`
- `prompt_template_id text not null`
- `prompt_template_version text not null`
- `generation_model text not null`
- `generation_config jsonb not null`
- `reranker_kind text not null`
- `reranker_config jsonb null`
- `top_k_requested integer not null`
- `retrieval_results jsonb not null`
- `final_answer text not null`
- `prompt_tokens integer not null`
- `completion_tokens integer not null`
- `total_tokens integer not null`
- `retrieval_stage_metrics jsonb null`
- `reranking_stage_metrics jsonb null`

### Storage Metadata Columns

The database table may contain storage metadata that is not part of the semantic `RequestCapture` contract.

The initial required storage metadata column is:

- `stored_at timestamptz not null default now()`

`stored_at` records when the row was persisted to the database.

## Column Mapping Rules

The semantic-to-storage mapping is one-to-one for scalar fields unless otherwise stated.

### Direct Scalar Mapping

The following semantic fields map directly to relational scalar columns:

- `request_id`
- `trace_id`
- `received_at`
- `raw_query`
- `normalized_query`
- `input_token_count`
- `pipeline_config_version`
- `corpus_version`
- `retriever_version`
- `embedding_model`
- `prompt_template_id`
- `prompt_template_version`
- `generation_model`
- `reranker_kind`
- `top_k_requested`
- `final_answer`
- `prompt_tokens`
- `completion_tokens`
- `total_tokens`

### JSONB Mapping

The following semantic fields map to JSONB columns:

- `generation_config -> generation_config jsonb`
- `reranker_config -> reranker_config jsonb`
- `retrieval_results -> retrieval_results jsonb`
- `retrieval_stage_metrics -> retrieval_stage_metrics jsonb`
- `reranking_stage_metrics -> reranking_stage_metrics jsonb`

`generation_config` storage rule:

- `generation_config` stores the serialized form of `GenerationConfig`;
- must never be `NULL`;
- the stored JSON object must contain exactly four keys: `model`, `model_endpoint`, `temperature`, `max_context_chunks`;
- no additional keys are allowed;
- `model` must be a non-empty string;
- `model_endpoint` must be a non-empty string;
- `temperature` must be a non-negative number;
- `max_context_chunks` must be a positive integer.

`reranker_kind` storage rule:

- `reranker_kind` is stored as the canonical serialized text form of the semantic enum `RerankerKind`;
- for the current version, the only allowed stored values are:
  - `PassThrough`
  - `Heuristic`
  - `CrossEncoder`

`reranker_config` storage rule:

- `reranker_config` stores the serialized form of `Option<RerankerConfig>`;
- for the current version, `NULL` represents pass-through reranking;
- for the current version, a non-null `reranker_config` value must represent either:
  - `RerankerConfig::Heuristic(HeuristicWeights)`
  - `RerankerConfig::CrossEncoder(CrossEncoderConfig)`
- for the current version, the only allowed JSON object shapes are:
  - heuristic:
    - `kind`
    - `final_k`
    - `weights`
  - cross-encoder:
    - `kind`
    - `final_k`
    - `cross_encoder`
- heuristic `kind` must equal `Heuristic`;
- heuristic `weights` must be a JSON object with exactly:
  - `retrieval_score`
  - `query_term_coverage`
  - `phrase_match_bonus`
  - `title_section_match_bonus`
- cross-encoder `kind` must equal `CrossEncoder`;
- cross-encoder config must contain exactly:
  - `model_name`
  - `url`
  - `total_tokens`
  - `cost_per_million_tokens`

## JSONB Rules

### `retrieval_results`

`retrieval_results` must be stored as a JSON array.

Rules:

- the array must preserve final reranked order;
- each array item represents one retrieval item from the semantic contract;
- parallel-array encodings are forbidden;
- the stored JSON shape must remain compatible with the `RequestCapture` schema and contract.

Each retrieval item must contain:

- `chunk_id`
- `document_id`
- `locator`
- `retrieval_score`
- `rerank_score`
- `selected_for_generation`

No additional retrieval item keys are allowed.

The array must contain at least one item.

The array must contain at least one item with:

- `selected_for_generation = true`

### `retrieval_stage_metrics` and `reranking_stage_metrics`

`retrieval_stage_metrics` and `reranking_stage_metrics` must each be stored as either a JSON object or SQL `NULL`.

Rules:

- `NULL` represents a request processed without a golden retrieval companion file;
- when present, each value must be a JSON object with the following fields:
  - `evaluated_k` — integer, minimum 1
  - `recall_soft` — number
  - `recall_strict` — number
  - `rr_soft` — number
  - `rr_strict` — number
  - `ndcg` — number
  - `first_relevant_rank_soft` — integer or null
  - `first_relevant_rank_strict` — integer or null
  - `num_relevant_soft` — integer, minimum 0
  - `num_relevant_strict` — integer, minimum 0
- the JSON shape must remain compatible with the `RetrievalQualityMetrics` definition in `Specification/contracts/rag_runtime/request_capture.md`;
- no SQL `CHECK` constraints are required for the internal structure of these columns;
- both columns must be `NULL` or both must be non-null within the same row; this invariant is enforced at the application layer, not at the storage layer.

## Constraint Rules

The table must enforce the following storage constraints.

### Identity and text constraints

- `request_id` is the primary key;
- all required text columns must be non-null;
- all required text columns must be non-empty after `btrim(...)`.

### Numeric constraints

- `input_token_count >= 1`
- `top_k_requested >= 1`
- `prompt_tokens >= 0`
- `completion_tokens >= 0`
- `total_tokens >= 0`
- `total_tokens = prompt_tokens + completion_tokens`

### JSONB structural constraints

- `jsonb_typeof(retrieval_results) = 'array'`
- `jsonb_array_length(retrieval_results) >= 1`

The storage contract must also enforce that `retrieval_results` contains at least one selected item.

The storage contract must also enforce that every retrieval item contains:

- `chunk_id` as a non-empty string;
- `document_id` as a non-empty string;
- `locator` as a non-empty string;
- `retrieval_score` as a numeric value;
- `rerank_score` as a numeric value;
- `selected_for_generation` as a boolean value.

The storage contract must also enforce that retrieval items do not contain keys outside the fixed retrieval item contract.

This may be implemented through SQL `CHECK` constraints using JSONPath or another PostgreSQL-compatible JSON inspection strategy.

## Index Rules

The initial required indexes are:

- primary key on `request_id`
- btree index on `received_at`
- btree index on `trace_id`

Additional indexes may be introduced later based on actual query patterns.

At the current phase, no GIN index on `retrieval_results` is required.

## Storage / Contract Boundary

This table is a storage representation of `RequestCapture`.

Rules:

- the semantic contract is owned by `Specification/contracts/rag_runtime/request_capture.md`;
- the database schema must conform to that semantic contract;
- storage-specific metadata such as `stored_at` may exist in the table without becoming part of the semantic contract;
- the storage schema must not silently redefine or weaken semantic invariants from the `RequestCapture` contract.

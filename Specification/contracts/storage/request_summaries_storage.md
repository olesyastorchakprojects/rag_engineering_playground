# Request Summaries Storage Contract

## Purpose

This document defines the database storage contract for `request_summaries`.

This contract maps derived request-level summary values into a relational representation suitable for PostgreSQL.

This document defines:

- the table shape for `request_summaries`;
- the derived-table semantics of request summaries;
- column-level storage rules;
- key, index, and constraint rules.

## Storage Model

The database representation of request-level summary values uses one table:

- `request_summaries`

This table stores one derived summary row per:

- `request_id`

## Derived Table Semantics

`request_summaries` is a derived request-level summary table.

Each row must be built from canonical upstream records, including:

- `request_captures`
- `judge_generation_results`
- `judge_retrieval_results`

This table is intended for:

- dashboarding;
- request-level filtering and inspection;
- downstream aggregate computation over request-level summary values.

This table must not become a second source of truth for:

- raw request capture data;
- raw judge outputs;
- run manifests.

## Table Shape

The `request_summaries` table contains:

- request identity and timestamps;
- request-level runtime facts copied from `request_captures`;
- derived generation summary values;
- derived retrieval summary values.

### Identity And Timestamps

- `request_id text primary key`
- `trace_id text not null`
- `source_received_at timestamptz not null`
- `summarized_at timestamptz not null default now()`

### Request-Level Runtime Facts

- `raw_query text not null`
- `normalized_query text not null`
- `input_token_count integer not null`
- `pipeline_config_version text not null`
- `corpus_version text not null`
- `retriever_version text not null`
- `embedding_model text not null`
- `reranker_kind text not null`
- `reranker_config jsonb null`
- `prompt_template_id text not null`
- `prompt_template_version text not null`
- `generation_model text not null`
- `top_k_requested integer not null`
- `final_answer text not null`
- `prompt_tokens integer not null`
- `completion_tokens integer not null`
- `total_tokens integer not null`

### Generation Summary Values

- `answer_completeness_score numeric(6,4)`
- `answer_completeness_label text`
- `groundedness_score numeric(6,4)`
- `groundedness_label text`
- `answer_relevance_score numeric(6,4)`
- `answer_relevance_label text`
- `correct_refusal_score numeric(6,4)`
- `correct_refusal_label text`

### Retrieval Summary Values

- `retrieval_relevance_mean numeric(6,4)`
- `retrieval_relevance_selected_mean numeric(6,4)`
- `retrieval_relevance_topk_mean numeric(6,4)`
- `retrieval_relevance_weighted_topk numeric(6,4)`
- `retrieval_relevance_relevant_count integer`
- `retrieval_relevance_selected_count integer`
- `retrieval_chunk_count integer`

### Retrieval Quality Metric Values

Retrieval stage (after vector search, before reranking):

- `retrieval_evaluated_k integer null`
- `retrieval_recall_soft numeric(6,4) null`
- `retrieval_recall_strict numeric(6,4) null`
- `retrieval_rr_soft numeric(6,4) null`
- `retrieval_rr_strict numeric(6,4) null`
- `retrieval_ndcg numeric(6,4) null`
- `retrieval_first_relevant_rank_soft integer null`
- `retrieval_first_relevant_rank_strict integer null`
- `retrieval_num_relevant_soft integer null`
- `retrieval_num_relevant_strict integer null`

Reranking stage (final ranked output):

- `reranking_evaluated_k integer null`
- `reranking_recall_soft numeric(6,4) null`
- `reranking_recall_strict numeric(6,4) null`
- `reranking_rr_soft numeric(6,4) null`
- `reranking_rr_strict numeric(6,4) null`
- `reranking_ndcg numeric(6,4) null`
- `reranking_first_relevant_rank_soft integer null`
- `reranking_first_relevant_rank_strict integer null`
- `reranking_num_relevant_soft integer null`
- `reranking_num_relevant_strict integer null`

Derived context loss (reranking effect on recall):

- `retrieval_context_loss_soft numeric(6,4) null`
- `retrieval_context_loss_strict numeric(6,4) null`

## Row Semantics

One row in `request_summaries` represents:

- one derived request-level summary
- for one `request_id`
- built from canonical upstream request capture and judge-result records

## Column Rules

### Required Text Columns

The following text columns are required:

- `request_id`
- `trace_id`
- `raw_query`
- `normalized_query`
- `pipeline_config_version`
- `corpus_version`
- `retriever_version`
- `embedding_model`
- `reranker_kind`
- `prompt_template_id`
- `prompt_template_version`
- `generation_model`
- `final_answer`

All required text columns must be:

- non-null;
- non-empty after `btrim(...)`.

### Required Numeric Runtime Columns

- `input_token_count >= 1`
- `top_k_requested >= 1`
- `prompt_tokens >= 0`
- `completion_tokens >= 0`
- `total_tokens >= 0`
- `total_tokens = prompt_tokens + completion_tokens`

### Optional Generation Summary Columns

The generation summary columns are nullable because:

- some generation suite outputs may be label-only or score-only.

For the current version, `request_summaries` must be written only for requests with complete upstream inputs.

Therefore the table must not be used to store intentionally partial request summaries for requests that are still missing required generation or retrieval judge rows.

If any `*_label` column is present, it must be non-empty after `btrim(...)`.

### Retrieval Summary Columns

The retrieval summary columns are derived from chunk-level retrieval judge rows.

Rules:

- `retrieval_chunk_count >= 0`
- `retrieval_relevance_relevant_count >= 0`
- `retrieval_relevance_selected_count >= 0`
- `retrieval_relevance_selected_count <= retrieval_chunk_count`
- `retrieval_relevance_relevant_count <= retrieval_chunk_count`

`retrieval_relevance_weighted_topk` is a derived request-level metric and is stored directly for dashboarding convenience.

The numeric range of retrieval summary scores is intentionally unconstrained at the storage layer because derivation semantics may evolve.

### Retrieval Quality Metric Columns

The retrieval quality metric columns are copied and flattened from `request_captures.retrieval_stage_metrics` and `request_captures.reranking_stage_metrics`.

Rules:

- all 22 retrieval quality metric columns are nullable;
- `NULL` in any of these columns means the request was processed without a golden retrieval companion file;
- when `request_captures.retrieval_stage_metrics` is non-null, all 10 `retrieval_*` metric columns must be populated from the corresponding fields of that object;
- when `request_captures.reranking_stage_metrics` is non-null, all 10 `reranking_*` metric columns must be populated from the corresponding fields of that object;
- `retrieval_context_loss_soft` must be computed as `retrieval_recall_soft - reranking_recall_soft` when both operands are non-null; `NULL` otherwise;
- `retrieval_context_loss_strict` must be computed as `retrieval_recall_strict - reranking_recall_strict` when both operands are non-null; `NULL` otherwise;
- a positive `retrieval_context_loss_*` value means the reranker discarded relevant chunks that were present in the retrieval output;
- these columns are sourced directly from `request_captures` and are not derived from `judge_*_results`.

### Reranking Metadata Columns

The reranking metadata columns are copied from the canonical request capture row so downstream analysis can compare runs without re-joining the raw capture table.

Rules:

- `reranker_kind` is required and must be copied from `request_captures.reranker_kind`;
- `reranker_config` is nullable and must be copied from `request_captures.reranker_config`;
- if `reranker_config` is present, it must be a JSON object;
- `reranker_config` must preserve the same semantic JSON shape as the request-capture contract when present.

## Key Rules

The required primary key is:

- `request_id`

Rationale:

- this table stores one summary row per request;
- it is not keyed by run because it is intended as the current derived request-level summary view.

## Index Rules

The initial required indexes are:

- btree index on `source_received_at`
- btree index on `trace_id`
- btree index on `reranker_kind`
- btree index on `pipeline_config_version`
- btree index on `retriever_version`
- btree index on `prompt_template_version`
- btree index on `generation_model`

Additional indexes may be introduced later based on actual query patterns.

## Storage Boundary

This table stores derived request-level summaries.

Rules:

- it is separate from `request_captures`;
- it is separate from raw `judge_*_results` tables;
- it is designed for convenience of inspection and dashboarding rather than as the primary raw source of truth.

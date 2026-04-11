# Request Run Summaries Storage Contract

## Purpose

This document defines the database storage contract for `request_run_summaries`.

This contract maps run-scoped derived request-level summary values into a relational representation suitable for PostgreSQL.

This document defines:

- the table shape for `request_run_summaries`;
- the distinction between `request_run_summaries` and `request_summaries`;
- column-level storage rules;
- key, index, and constraint rules.

## Storage Model

The database representation of run-scoped request-level summary values uses one table:

- `request_run_summaries`

This table stores one derived summary row per:

- `(request_id, run_id)`

## Distinction From `request_summaries`

`request_run_summaries` is a run-scoped historical table.

`request_summaries` is a live per-request derived view keyed only by `request_id`.

Differences:

- `request_run_summaries` is keyed by `(request_id, run_id)` and retains one row per request per run;
- `request_summaries` is keyed by `request_id` and always represents the most recent derived state for that request;
- `request_run_summaries` allows comparing the same request across different runs;
- `request_run_summaries` additionally stores run-scoped judge metadata columns that are not part of `request_summaries`.

Rules:

- `request_run_summaries` must not be used as a live per-request view;
- `request_summaries` must not be used for run-scoped historical comparison;
- both tables must be written by `build_request_summary` in the same stage invocation.

## Table Shape

The `request_run_summaries` table contains:

- run identity and request identity columns;
- request-level runtime facts copied from `request_captures`;
- derived generation summary values;
- derived retrieval summary values;
- retrieval quality metric values flattened from `request_captures`;
- run-scoped judge metadata.

### Identity And Timestamps

- `request_id text not null`
- `run_id text not null`
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
- `retriever_kind text not null`
- `embedding_model text not null`
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

### Run-Scoped Judge Metadata

- `judge_generation_model text`
- `judge_generation_prompt_version text`
- `judge_retrieval_model text`
- `judge_retrieval_prompt_version text`

## Row Semantics

One row in `request_run_summaries` represents:

- one derived request-level summary
- for one `(request_id, run_id)` combination
- built from canonical upstream request capture and judge-result records for that run

## Column Rules

### Required Text Columns

The following text columns are required:

- `request_id`
- `run_id`
- `trace_id`
- `raw_query`
- `normalized_query`
- `pipeline_config_version`
- `corpus_version`
- `retriever_version`
- `retriever_kind`
- `embedding_model`
- `prompt_template_id`
- `prompt_template_version`
- `generation_model`
- `final_answer`

All required text columns must be:

- non-null;
- non-empty after `btrim(...)`.

`retriever_kind` must be one of the allowed `RetrieverKind` values:

- `Dense`
- `Hybrid`

### Required Numeric Runtime Columns

- `input_token_count >= 1`
- `top_k_requested >= 1`
- `prompt_tokens >= 0`
- `completion_tokens >= 0`
- `total_tokens >= 0`
- `total_tokens = prompt_tokens + completion_tokens`

### Optional Generation Summary Columns

The generation summary columns are nullable.

If any `*_label` column is present, it must be non-empty after `btrim(...)`.

### Retrieval Summary Columns

Rules:

- `retrieval_chunk_count >= 0` when non-null
- `retrieval_relevance_relevant_count >= 0` when non-null
- `retrieval_relevance_selected_count >= 0` when non-null
- `retrieval_relevance_selected_count <= retrieval_chunk_count` when both non-null
- `retrieval_relevance_relevant_count <= retrieval_chunk_count` when both non-null

### Retrieval Quality Metric Columns

The retrieval quality metric columns are copied and flattened from `request_captures.retrieval_stage_metrics` and `request_captures.reranking_stage_metrics`.

Rules:

- all 22 retrieval quality metric columns are nullable;
- `NULL` means the request was processed without a golden retrieval companion file;
- when `request_captures.retrieval_stage_metrics` is non-null, all 10 `retrieval_*` metric columns must be populated;
- when `request_captures.reranking_stage_metrics` is non-null, all 10 `reranking_*` metric columns must be populated;
- `retrieval_context_loss_soft` = `retrieval_recall_soft - reranking_recall_soft` when both are non-null; `NULL` otherwise;
- `retrieval_context_loss_strict` = `retrieval_recall_strict - reranking_recall_strict` when both are non-null; `NULL` otherwise;
- these columns are sourced directly from `request_captures` and are not derived from `judge_*_results`.

### Run-Scoped Judge Metadata Columns

The judge metadata columns are nullable.

Rules:

- `judge_generation_model` and `judge_generation_prompt_version` must be copied from `run_manifest.json` for the current `run_id`;
- `judge_retrieval_model` and `judge_retrieval_prompt_version` must be copied from `run_manifest.json` for the current `run_id`;
- if present, all judge metadata text values must be non-empty after `btrim(...)`.

## Key Rules

The required primary key is:

- `(request_id, run_id)`

Rationale:

- this table retains one summary row per request per run;
- multiple rows for the same `request_id` are expected and valid across different runs.

## Upsert Semantics

The stage must upsert rows using `on conflict (request_id, run_id) do update`.

On conflict the row must be fully overwritten with current derived values.

This allows safe reprocessing when a run is resumed.

## Index Rules

The initial required indexes are:

- primary key on `(request_id, run_id)`
- btree index on `run_id`
- btree index on `source_received_at`
- btree index on `trace_id`
- btree index on `pipeline_config_version`
- btree index on `retriever_version`
- btree index on `retriever_kind`
- btree index on `prompt_template_version`
- btree index on `generation_model`
- btree index on `(run_id, source_received_at)` — for run-scoped time-ordered queries
- btree index on `(run_id, generation_model)` — for run-scoped model comparison
- btree index on `(run_id, retriever_version)` — for run-scoped retriever comparison
- btree index on `(run_id, retriever_kind)` — for run-scoped retriever kind comparison

## Storage Boundary

This table stores run-scoped derived request-level summaries.

Rules:

- it is separate from `request_captures`;
- it is separate from raw `judge_*_results` tables;
- it is separate from `request_summaries` which stores the live per-request view;
- it is designed for run-scoped analysis, dashboarding, and cross-run comparison.

The semantic source of truth for `RequestCapture` remains:

- `Specification/contracts/rag_runtime/request_capture.md`

The semantic source of truth for `request_summaries` remains:

- `Specification/contracts/storage/request_summaries_storage.md`

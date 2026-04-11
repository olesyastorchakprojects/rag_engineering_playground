# Judge LLM Calls Storage Contract

## Purpose

This document defines the database storage contract for `judge_llm_calls`.

This contract maps one factual judge-model invocation into a relational record suitable for PostgreSQL.

This document defines:

- the table shape for `judge_llm_calls`;
- row semantics for eval-stage LLM calls;
- token and cost storage rules;
- key, index, and constraint rules.

## Storage Model

The database representation of eval judge-model usage uses one table:

- `judge_llm_calls`

This table stores one row per factual judge-model call.

One row is written for:

- one `request_id`
- one `run_id`
- one eval-stage LLM invocation

This row is separate from:

- `judge_generation_results`
- `judge_retrieval_results`

Rationale:

- token usage and cost represent factual model activity;
- normalized judge verdicts represent successfully parsed business outputs;
- a judge-model call may consume tokens and cost even when downstream response parsing fails.

## Table Shape

The `judge_llm_calls` table contains:

- identity and linkage columns;
- judge provenance columns;
- token accounting columns;
- pricing columns.

### Identity And Linkage Columns

- `call_id text not null`
- `request_id text not null`
- `run_id text not null`
- `trace_id text not null`
- `created_at timestamptz not null default now()`

### Judge Provenance Columns

- `stage_name text not null`
- `suite_name text`
- `chunk_id text`
- `judge_provider text not null`
- `judge_model text not null`
- `judge_prompt_version text not null`
- `token_count_source text not null`

### Token Accounting Columns

- `prompt_tokens integer not null`
- `completion_tokens integer not null`
- `total_tokens integer not null`

### Pricing Columns

- `input_cost_per_million_tokens numeric(12,6) not null`
- `output_cost_per_million_tokens numeric(12,6) not null`
- `total_cost_usd numeric(12,8) not null`

## Row Semantics

One row in `judge_llm_calls` represents:

- one factual LLM call issued by an eval judge stage
- for one `request_id`
- in one `run_id`
- for one stage-local evaluation unit

For `judge_generation`:

- one row corresponds to one generation suite call for one request
- `suite_name` is required in practice
- `chunk_id` is null

For `judge_retrieval`:

- one row corresponds to one retrieval chunk-evaluation call for one request
- `suite_name` is `retrieval_relevance`
- `chunk_id` identifies the evaluated chunk

This table may contain rows for calls whose raw model responses were received successfully but whose downstream business parsing later failed.

This table therefore represents:

- factual token and cost consumption

and not:

- only successfully normalized judge verdicts

## Column Rules

### Required Text Columns

The following text columns are required:

- `call_id`
- `request_id`
- `run_id`
- `trace_id`
- `stage_name`
- `judge_provider`
- `judge_model`
- `judge_prompt_version`
- `token_count_source`

All required text columns must be:

- non-null;
- non-empty after `btrim(...)`.

If `suite_name` is present, it must be non-empty after `btrim(...)`.

If `chunk_id` is present, it must be non-empty after `btrim(...)`.

### Stage Rules

`stage_name` must be one of:

- `judge_generation`
- `judge_retrieval`

### Token Count Source Rules

`token_count_source` must be one of:

- `provider_usage`
- `ollama_native_usage`
- `local_estimate`

### Token Count Rules

- `prompt_tokens >= 0`
- `completion_tokens >= 0`
- `total_tokens >= 0`
- `total_tokens = prompt_tokens + completion_tokens`

### Pricing Rules

- `input_cost_per_million_tokens >= 0`
- `output_cost_per_million_tokens >= 0`
- `total_cost_usd >= 0`

`total_cost_usd` must be computed as:

- `prompt_tokens * input_cost_per_million_tokens / 1_000_000`
- plus
- `completion_tokens * output_cost_per_million_tokens / 1_000_000`

## Key Rules

The required primary key is:

- `(call_id)`

Rationale:

- retries and resume may issue multiple factual judge calls for the same logical eval unit;
- token-usage storage must preserve every factual call rather than collapsing them by logical key.

## Index Rules

The initial required indexes are:

- btree index on `run_id`
- btree index on `request_id`
- btree index on `(run_id, stage_name)`
- btree index on `created_at`

Additional indexes may be introduced later based on actual report-query patterns.

## Storage Boundary

This table stores factual eval judge-model usage and cost.

Rules:

- it is separate from normalized judge-result tables;
- it is separate from `run_manifest.json`;
- it is the canonical future source for eval token-usage and cost aggregation by `run_id`.

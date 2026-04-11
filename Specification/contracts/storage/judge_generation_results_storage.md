# Judge Generation Results Storage Contract

## Purpose

This document defines the database storage contract for `judge_generation_results`.

This contract maps normalized generation-judge outputs into a relational representation suitable for PostgreSQL.

This document defines:

- the table shape for `judge_generation_results`;
- the typed suite identifier used by generation judge results;
- column-level storage rules;
- key, index, and constraint rules.

## Storage Model

The database representation of normalized generation judge outputs uses one table:

- `judge_generation_results`

This table stores one normalized judge result per:

- `request_id`
- `run_id`
- `suite_name`

## Typed Suite Identifier

Generation judge categories must use a typed SQL enum:

- `judge_generation_suite`

The initial required enum values are:

- `answer_completeness`
- `groundedness`
- `answer_relevance`
- `correct_refusal`

`suite_name` must use this enum type rather than an untyped text field.

Rationale:

- aggregates and summaries must group by a stable semantic category;
- untyped free-form suite names would allow semantic drift in stored judge results.

## Table Shape

The `judge_generation_results` table contains:

- identity and linkage columns;
- judge provenance columns;
- normalized judge output columns.

### Identity And Linkage Columns

- `request_id text not null`
- `run_id text not null`
- `trace_id text not null`
- `created_at timestamptz not null default now()`

### Judge Provenance Columns

- `suite_name judge_generation_suite not null`
- `judge_model text not null`
- `judge_prompt_version text not null`

### Normalized Judge Output Columns

- `score numeric(6,4)`
- `label text`
- `explanation text`
- `raw_response jsonb not null`

## Row Semantics

One row in `judge_generation_results` represents:

- one normalized generation-judge verdict
- for one `request_id`
- in one `run_id`
- for one generation judge suite identified by `suite_name`

This table does not store:

- run-level aggregates;
- request capture source data;
- retrieval or citation judge results.

## Column Rules

### Required Text Columns

The following text columns are required:

- `request_id`
- `run_id`
- `trace_id`
- `judge_model`
- `judge_prompt_version`

All required text columns must be:

- non-null;
- non-empty after `btrim(...)`.

### Optional Normalized Output Columns

- `score` is optional because some generation judge suites may be label-only;
- `label` is optional because some generation judge suites may be score-only;
- `explanation` is optional because some normalized judge outputs may omit a textual explanation.

`score` range is suite-specific and intentionally unconstrained at the storage layer.

If `label` is present, it must be non-empty after `btrim(...)`.

If `explanation` is present, it must be non-empty after `btrim(...)`.

### Raw Judge Output

`raw_response` stores the raw structured judge output associated with the normalized result.

Rules:

- `raw_response` must be stored as `jsonb`;
- `raw_response` must be a JSON object;
- `raw_response` must not be null.

## Key Rules

The required primary key is:

- `(request_id, run_id, suite_name)`

Rationale:

- one request may be judged by multiple generation suites in the same run;
- one request may also appear in multiple runs;
- the combination of request, run, and semantic judge category must be unique.

## Index Rules

The initial required indexes are:

- btree index on `run_id`
- btree index on `suite_name`
- btree index on `request_id`
- btree index on `created_at`

Additional indexes may be introduced later based on actual query patterns.

## Constraint Rules

The table must enforce the following storage constraints.

### Identity And Text Constraints

- `request_id`, `run_id`, `trace_id`, `judge_model`, and `judge_prompt_version` must be non-empty after `btrim(...)`;
- if `label` is not null, it must be non-empty after `btrim(...)`;
- if `explanation` is not null, it must be non-empty after `btrim(...)`.

### JSONB Constraint

- `jsonb_typeof(raw_response) = 'object'`

## Storage Boundary

This table stores normalized generation-judge outputs.

Rules:

- it is separate from `request_captures`;
- it is separate from run-level manifests and aggregates;
- it must not redefine generation judge suite semantics outside the typed enum contract.

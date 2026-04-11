# Judge Retrieval Results Storage Contract

## Purpose

This document defines the database storage contract for `judge_retrieval_results`.

This contract maps normalized retrieval-judge outputs into a relational representation suitable for PostgreSQL.

This document defines:

- the table shape for `judge_retrieval_results`;
- the typed suite identifier used by retrieval judge results;
- chunk-level row semantics;
- column-level storage rules;
- key, index, and constraint rules.

## Storage Model

The database representation of normalized retrieval judge outputs uses one table:

- `judge_retrieval_results`

This table stores one normalized retrieval judge result per:

- `request_id`
- `run_id`
- `suite_name`
- `chunk_id`

The storage granularity is chunk-level rather than request-level.

Rationale:

- many retrieval aggregates are naturally computed over judged chunks;
- chunk-level judged outputs are needed for request-level and run-level retrieval summaries;
- request-level retrieval summaries can be derived later from chunk-level judged rows.

## Typed Suite Identifier

Retrieval judge categories must use a typed SQL enum:

- `judge_retrieval_suite`

The initial required enum values are:

- `retrieval_relevance`

`suite_name` must use this enum type rather than an untyped text field.

## Table Shape

The `judge_retrieval_results` table contains:

- identity and linkage columns;
- chunk context columns;
- judge provenance columns;
- normalized judge output columns.

### Identity And Linkage Columns

- `request_id text not null`
- `run_id text not null`
- `trace_id text not null`
- `chunk_id text not null`
- `created_at timestamptz not null default now()`

### Chunk Context Columns

- `document_id text not null`
- `retrieval_rank integer not null`
- `retrieval_score numeric(12,6) not null`
- `selected_for_generation boolean not null`

### Judge Provenance Columns

- `suite_name judge_retrieval_suite not null`
- `judge_model text not null`
- `judge_prompt_version text not null`

### Normalized Judge Output Columns

- `score numeric(6,4)`
- `label text`
- `explanation text`
- `raw_response jsonb not null`

## Row Semantics

One row in `judge_retrieval_results` represents:

- one normalized retrieval-judge verdict
- for one retrieved chunk
- for one `request_id`
- in one `run_id`
- for one retrieval judge suite identified by `suite_name`

This table does not store:

- request-level retrieval summaries;
- run-level aggregates;
- generation or citation judge results.

`chunk_id` is the stable identity of the retrieved chunk within the request context represented by the row key.

## Column Rules

### Required Text Columns

The following text columns are required:

- `request_id`
- `run_id`
- `trace_id`
- `chunk_id`
- `document_id`
- `judge_model`
- `judge_prompt_version`

All required text columns must be:

- non-null;
- non-empty after `btrim(...)`.

### Numeric And Boolean Context Columns

- `retrieval_rank` must be `>= 1`
- `retrieval_score` is required for every stored judged chunk row
- `retrieval_score` range is retrieval-system-specific and intentionally unconstrained at the storage layer
- `selected_for_generation` is required and must be stored as a boolean value

### Optional Normalized Output Columns

- `score` is optional because some retrieval judge suites may be label-only;
- `label` is optional because some retrieval judge suites may be score-only;
- `explanation` is optional because some normalized judge outputs may omit a textual explanation.

`score` range is suite-specific and intentionally unconstrained at the storage layer.

If `label` is present, it must be non-empty after `btrim(...)`.

If `explanation` is present, it must be non-empty after `btrim(...)`.

### Raw Judge Output

`raw_response` stores the raw structured judge output associated with the normalized retrieval result.

Rules:

- `raw_response` must be stored as `jsonb`;
- `raw_response` must be a JSON object;
- `raw_response` must not be null.

## Key Rules

The required primary key is:

- `(request_id, run_id, suite_name, chunk_id)`

Rationale:

- one request contains multiple judged chunks;
- the same request may appear in multiple runs;
- retrieval suites may expand later;
- the combination of request, run, suite, and chunk must be unique.

## Index Rules

The initial required indexes are:

- btree index on `run_id`
- btree index on `suite_name`
- btree index on `request_id`
- btree index on `chunk_id`
- btree index on `created_at`
- btree index on `(request_id, retrieval_rank)`
- btree index on `(request_id, selected_for_generation)`

Additional indexes may be introduced later based on actual query patterns.

## Constraint Rules

The table must enforce the following storage constraints.

### Identity And Text Constraints

- `request_id`, `run_id`, `trace_id`, `chunk_id`, `document_id`, `judge_model`, and `judge_prompt_version` must be non-empty after `btrim(...)`;
- if `label` is not null, it must be non-empty after `btrim(...)`;
- if `explanation` is not null, it must be non-empty after `btrim(...)`.

### Numeric Constraints

- `retrieval_rank >= 1`

### JSONB Constraint

- `jsonb_typeof(raw_response) = 'object'`

## Storage Boundary

This table stores chunk-level normalized retrieval-judge outputs.

Rules:

- it is separate from `request_captures`;
- it is separate from request-level retrieval summaries and run-level aggregates;
- it must not redefine retrieval judge suite semantics outside the typed enum contract.

# Eval Processing State Storage Contract

## Purpose

This document defines the database storage contract for `eval_processing_state`.

This contract defines the request-level processing state machine used by the eval ingestion pipeline.

This document defines:

- the table shape for `eval_processing_state`;
- the typed stage and status identifiers;
- FIFO scheduling semantics;
- key, index, and constraint rules.

## Storage Model

The processing-state representation uses one table:

- `eval_processing_state`

This table stores one processing-state row per:

- `request_id`

The storage model is intentionally request-level and state-machine-oriented.

## State Machine Model

Each row in `eval_processing_state` represents the current eval-processing state of one request.

The table is used to track strictly sequential processing through the following stages:

- `judge_generation`
- `judge_retrieval`
- `build_request_summary`

For each row, the current stage has one status:

- `pending`
- `running`
- `completed`
- `failed`

The pipeline is strictly sequential for the current version.

This means:

- a request starts in `judge_generation`;
- after successful completion of `judge_generation`, it advances to `judge_retrieval`;
- after successful completion of `judge_retrieval`, it advances to `build_request_summary`;
- after successful completion of `build_request_summary`, the whole request state becomes `completed`.

For the completed terminal state in the current version:

- `current_stage = build_request_summary`
- `status = completed`

## Typed Stage And Status Identifiers

Processing stages must use a typed SQL enum:

- `eval_processing_stage`

The initial required enum values are:

- `judge_generation`
- `judge_retrieval`
- `build_request_summary`

Processing status must use a typed SQL enum:

- `eval_processing_status`

The initial required enum values are:

- `pending`
- `running`
- `completed`
- `failed`

## Table Shape

The `eval_processing_state` table contains:

- request identity and ordering columns;
- state-machine columns;
- operational tracking columns.

### Identity And Ordering Columns

- `request_id text primary key`
- `request_received_at timestamptz not null`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

### State-Machine Columns

- `current_stage eval_processing_stage not null`
- `status eval_processing_status not null`

### Operational Tracking Columns

- `attempt_count integer not null default 0`
- `started_at timestamptz`
- `completed_at timestamptz`
- `last_error text`

`updated_at` is application-maintained and must be refreshed on every state transition.

## Row Semantics

One row in `eval_processing_state` represents:

- one request-level eval-processing state
- for one `request_id`
- ordered according to the original request arrival time

`request_received_at` mirrors `request_captures.received_at`.

It exists to support FIFO scheduling without requiring a join to `request_captures` during work selection.

## FIFO Scheduling Semantics

For the current version, work selection must use strict FIFO ordering.

The canonical ordering key is:

- `request_received_at ASC`
- `request_id ASC`

Worker selection of the next pending request must follow this ordering.

## Column Rules

### Required Text Columns

The following text columns are required:

- `request_id`

All required text columns must be:

- non-null;
- non-empty after `btrim(...)`.

### Numeric Constraints

- `attempt_count >= 0`

### Optional Error Column

`last_error` is optional.

If `last_error` is present, it must be non-empty after `btrim(...)`.

## Key Rules

The required primary key is:

- `request_id`

Rationale:

- there is exactly one current processing-state row per request in the current sequential pipeline model.

## Index Rules

The initial required indexes are:

- btree index on `(status, request_received_at, request_id)`
- btree index on `current_stage`
- btree index on `updated_at`

Additional indexes may be introduced later based on actual query patterns.

## Constraint Rules

The table must enforce the following storage constraints.

### Identity And Text Constraints

- `request_id` must be non-empty after `btrim(...)`;
- if `last_error` is not null, it must be non-empty after `btrim(...)`.

### Numeric Constraint

- `attempt_count >= 0`

## Storage Boundary

This table stores processing state only.

Rules:

- it is separate from `request_captures`;
- it is separate from `judge_*_results`;
- it is separate from `request_summaries`;
- it must not store raw judge results or request payloads beyond the minimal scheduling and tracking fields defined here.

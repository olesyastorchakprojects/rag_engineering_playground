# Eval Run Manifest Contract

## Purpose

This document defines the semantic contract for `run_manifest.json`.

`run_manifest.json` is the canonical run-level metadata record for one complete eval pipeline run.

It exists to:

- identify one eval run unambiguously;
- record run provenance and status;
- provide a small machine-readable source of truth for run metadata.

## Scope

This document defines:

- the semantics of `run_id`;
- the semantic shape of `run_manifest.json`;
- required run-level metadata fields.

This document does not define:

- eval pipeline architecture;
- detailed stage behavior;
- file-based report structure;
- SQL table schemas for request- or judge-level data;
- dashboard queries;
- request-level summary aggregation formulas;
- judge prompt contents.

## `run_id` Semantics

`run_id` is the canonical identifier of one complete eval run.

Rules:

- one eval run has exactly one `run_id`;
- the same `run_id` must be used across all judge results produced by that run;
- the same `run_id` must be written into `run_manifest.json`;
- `run_id` must not be inferred from database state after the run starts.

For the current version:

- `run_id` must be generated once at run bootstrap;
- `run_id` must remain stable for the entire run lifetime;
- `run_id` must be treated as opaque stable text by downstream code.

## Required Top-Level Fields

`run_manifest.json` must contain the following required top-level fields.

### Identity

- `run_id`
- `run_type`
- `status`

### Timestamps

- `started_at`

### Pipeline Scope

- `stages`

### Storage And Inputs

- `postgres_url`
- `chunks_path`
- `tracing_endpoint`

### Judge Runtime

- `judge_provider`
- `judge_base_url`
- `judge_model`

### Prompt Provenance

- `generation_suite_versions`
- `retrieval_suite_versions`

### Request Scope

- `request_count`
- `run_scope_request_ids`

## Optional Top-Level Fields

The following top-level fields are optional for the current version:

- `completed_at`
- `last_error`
- `retriever_kind`, when the run scope is homogeneous
- `reranker_kind`, when the run scope is homogeneous
- `notes`

## Field Semantics

### `run_id`

- stable identifier of the run.

### `run_type`

- category of the run.

Allowed values for the current version:

- `continuous`
- `nightly`
- `experiment`

### `status`

- terminal or current run status.

Allowed values for the current version:

- `running`
- `completed`
- `failed`

### `started_at`

- UTC timestamp recorded when the run is created.

### `completed_at`

- UTC timestamp recorded only when the run reaches a terminal state.

### `stages`

- ordered list of stage names included in the run.

For the current version, allowed stage names are:

- `judge_generation`
- `judge_retrieval`
- `build_request_summary`

### `postgres_url`

- PostgreSQL connection target used by the run.

For the current version, this field exists for operational reproducibility.

### `chunks_path`

- canonical path to the `chunks.jsonl` corpus artifact used for chunk text resolution during the run.

### `tracing_endpoint`

- OTLP trace collector endpoint used by the eval run.

### `judge_provider`

- effective judge provider used for the run.

Allowed values for the current version:

- `ollama`
- `together`

### `judge_base_url`

- OpenAI-compatible judge endpoint used for the run.

### `judge_model`

- judge model identifier used for the run.

### `generation_suite_versions`

- object that maps each enabled generation suite name to its prompt version.

### `retrieval_suite_versions`

- object that maps each enabled retrieval suite name to its prompt version.

### `request_count`

- number of requests included in the run scope.

### `retriever_kind`

- retriever kind used by the run scope, when all requests in the run use the same retriever.
- if the run scope is heterogeneous, the orchestrator must treat that as a run bootstrap error.
- allowed values for the current version:
  - `Dense`
  - `Hybrid`

### `reranker_kind`

- reranker kind used by the run scope, when all requests in the run use the same reranker.
- if the run scope is heterogeneous, the orchestrator must treat that as a run bootstrap error.
- allowed values for the current version:
  - `PassThrough`
  - `Heuristic`
  - `CrossEncoder`

### `run_scope_request_ids`

- frozen ordered set of `request_id` values included in the run scope.

### `last_error`

- non-empty summary of the last terminal run-level failure, when present.

### `notes`

- free-form operator note about the run.

## Structural Rules

`generation_suite_versions` must contain one entry for each enabled generation suite.

For the current version, expected generation suite keys are:

- `answer_completeness`
- `groundedness`
- `answer_relevance`
- `correct_refusal`

`retrieval_suite_versions` must contain one entry for each enabled retrieval suite.

For the current version, expected retrieval suite keys are:

- `retrieval_relevance`

All suite-version values must be non-empty strings.

## Invariants

The following invariants are required.

### Single-run identity invariant

One `run_manifest.json` corresponds to exactly one `run_id`.

### Status/timestamp invariant

- `started_at` is always required;
- `completed_at` must be present when `status` is `completed` or `failed`;
- `completed_at` must be absent when `status` is `running`.

### Request-count invariant

`request_count` must equal the number of requests included in the frozen run scope at bootstrap time.

### Run-scope immutability invariant

- `run_scope_request_ids` must be fixed once the run starts;
- a resumed run must reuse the same `run_scope_request_ids`;
- new requests captured after the run starts must not be appended to `run_scope_request_ids`;
- `request_count` must equal the length of `run_scope_request_ids`.

## Machine-Readable Schema

The machine-readable schema for this contract is:

- `Execution/schemas/evals/run_manifest.schema.json`

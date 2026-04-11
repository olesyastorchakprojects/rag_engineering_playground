# Evals Architecture

## Purpose

This document defines the current architecture of the eval engine.

It describes:

- what the eval engine does end-to-end;
- core eval tables and run artifacts;
- canonical identifiers;
- pipeline stages;
- stage inputs and outputs;
- FIFO processing order;
- state transitions in `eval_processing_state`;
- ownership boundaries between orchestrator logic and stage workers;
- failure and retry behavior at the stage level;
- repository placement rules for eval specs, contracts, and artifacts.

This document does not define:

- judge prompt contents;
- model-specific evaluator prompts;
- SQL schema details already owned by storage contracts;
- runtime request-capture serialization details;
- detailed eval observability span contracts.

## System Summary

At the highest level, the current eval system works as follows:

1. the runtime CLI writes request-level source data into PostgreSQL through the `request_captures` table;
2. the eval engine reads that request data from PostgreSQL, runs eval stages, writes judge results plus derived aggregates and metrics back into PostgreSQL, emits traces to Tempo plus progress logs to the CLI, and produces one run report;
3. Grafana reads the derived aggregates and metrics from PostgreSQL and builds dashboards on top of them.

In this system:

- the runtime is responsible for capturing request data;
- the eval engine is responsible for judging, aggregation, and run-level reporting;
- Grafana is responsible for dashboard visualization, not for producing the underlying eval data.

## Eval Engine Overview

The eval engine is a sequential request-level pipeline that evaluates completed runtime requests after they have been captured in storage.

At a high level, it works as follows:

1. the runtime writes one canonical source row into `request_captures`;
2. the eval orchestrator creates one `run_id` and one `run_manifest.json` for the eval run;
3. the orchestrator bootstraps only new requests into `eval_processing_state`;
4. if a run fails, the orchestrator must resume the same `run_id` and the same frozen run scope rather than creating a new run that absorbs those in-progress requests;
5. the orchestrator invokes three worker stages in order:
   - `judge_generation`
   - `judge_retrieval`
   - `build_request_summary`
6. worker stages write judge-result rows and update only their own stage-local state;
7. the orchestrator promotes completed requests into the next stage;
8. after all requests in run scope finish the terminal summary stage, the orchestrator writes `run_report.md`.

This architecture separates concerns deliberately:

- the `request_captures` table is the stable source record for one processed runtime request;
- the `judge_*_results` tables are run-scoped evaluation outputs;
- the `request_summaries` table is the current per-request derived analysis layer;
- the `eval_processing_state` table is the workflow state machine;
- `run_manifest.json` and `run_report.md` are run-level artifacts.

## Main Components

The current eval engine has four main component types.

### Runtime Capture Layer

The runtime capture layer writes canonical request rows into `request_captures`.

This layer defines the source data that the eval engine consumes.

### Eval Orchestrator

The orchestrator owns run-level workflow.

For the current version:

- the orchestrator is the only top-level Python CLI entrypoint for the eval engine;
- worker stages are in-process Python modules with explicit callable entrypoints.

Its responsibilities are:

- generating `run_id`;
- creating and updating `run_manifest.json`;
- discovering run scope;
- freezing `run_scope_request_ids` for the run;
- bootstrapping `eval_processing_state`;
- invoking worker stages in pipeline order;
- promoting completed requests into the next stage;
- detecting terminal run completion;
- building `run_report.md`.

### Worker Stages

Worker stages own stage-local processing only.

The current stages are:

1. `judge_generation`
2. `judge_retrieval`
3. `build_request_summary`

Each worker:

- selects the next eligible request for its own stage;
- processes at most one request per invocation;
- writes only its own downstream outputs;
- updates only the current request row in `eval_processing_state`;
- performs stage-local recovery by inspecting existing downstream rows and writing only what is still missing.

## Core Tables And Run Artifacts

The current eval subsystem uses six primary database tables and two required run artifacts.

### 1. `request_captures` table

The `request_captures` table is the canonical request-level source table written by the runtime.

Its purpose is:

- to provide stable input to the eval pipeline;
- to avoid making Phoenix traces the only source of eval ingestion;
- to keep eval ingestion schema-driven and reproducible.

### 2. `eval_processing_state` table

The `eval_processing_state` table is the canonical request-level workflow-state table for eval processing.

Its purpose is:

- to track the current stage of each request;
- to preserve FIFO scheduling inputs;
- to separate workflow state from source data and result tables.

### 3. `judge_generation_results` table

The `judge_generation_results` table stores normalized generation-judge outputs for one `(request_id, run_id, suite_name)`.

This table contains request-level generation judgments.

It is not the request-level summary layer.

### 4. `judge_retrieval_results` table

The `judge_retrieval_results` table stores normalized retrieval-judge outputs for one `(request_id, run_id, suite_name, chunk_id)`.

This table contains chunk-level retrieval judgments.

It is not the request-level summary layer.

### 5. `request_summaries` table

The `request_summaries` table stores the current derived request-level summary row.

Its purpose is:

- to keep request-level aggregates and useful derived values together;
- to support dashboards and operational analysis;
- to avoid rebuilding the same joins and summary calculations repeatedly.

The `request_summaries` table is not a per-run historical table.

### 6. `request_run_summaries` table

The `request_run_summaries` table stores run-scoped derived request-level summary rows.

Its purpose is:

- to retain one summary row per `(request_id, run_id)` combination;
- to allow cross-run comparison of the same requests;
- to support run-scoped dashboards and experiment analysis.

The `request_run_summaries` table is the run-scoped historical counterpart to `request_summaries`.

It is written by `build_request_summary` in the same stage invocation that writes `request_summaries`.

### 7. `run_manifest.json` artifact

`run_manifest.json` is the canonical structured metadata artifact for one eval run.

### 7. `run_report.md` artifact

`run_report.md` is the canonical human-readable summary artifact for one completed eval run.

## Canonical Keys

The eval subsystem uses the following canonical identifiers.

### `request_id`

Primary identifier for one processed request.

Rules:

- request-level records are keyed by `request_id`;
- chunk-level retrieval rows remain linkable back to `request_id`.

### `trace_id`

Identifier used to connect request-level records to runtime traces.

Rules:

- `trace_id` is the drill-down link into trace inspection;
- `trace_id` does not replace `request_id`.

### `run_id`

Identifier for one eval run.

Rules:

- every eval run has exactly one `run_id`;
- `run_id` links run-level artifacts to judge-result rows;
- `request_summaries` remains current per-request state and is not keyed by `run_id`.

### `suite_name`

Identifier of the eval suite that produced a result.

Current examples:

- `answer_completeness`
- `groundedness`
- `answer_relevance`
- `correct_refusal`
- `retrieval_relevance`

### `run_type`

Identifier of the run category.

Allowed values in the current version:

- `continuous`
- `nightly`
- `experiment`

## Pipeline Scope

The initial eval-ingestion pipeline contains three strictly sequential stages:

1. `judge_generation`
2. `judge_retrieval`
3. `build_request_summary`

The current version does not include a citation-judge stage.

The stage granularity pattern is:

- `judge_generation` is request-level
- `judge_retrieval` is request-level for scheduling, but chunk-level for produced judge rows
- `build_request_summary` is request-level and aggregates chunk-level retrieval outputs back into one request-level summary row

## Operational Preconditions

Before the current eval engine can be executed successfully:

- the PostgreSQL eval schema must already exist;
- the required eval tables must already be created by the SQL init files in `Execution/docker/postgres/init/`;
- the Python runtime used for eval execution must have the required dependencies installed.

For the current Python implementation, the required runtime dependencies include:

- `psycopg`
- `openai`
- `jsonschema`

## Source And Sink Tables

### Source Tables

- the `request_captures` table
- the `eval_processing_state` table

### Intermediate Result Tables

- the `judge_generation_results` table
- the `judge_retrieval_results` table

### Final Derived Tables

- the `request_summaries` table
- the `request_run_summaries` table

## Bootstrap Rule

A request becomes eligible for eval processing after:

- the runtime has written a completed row into `request_captures`

The eval orchestrator bootstrap step must then create one row in `eval_processing_state` with:

- `request_id` copied from `request_captures`
- `request_received_at` copied from `request_captures.received_at`
- `current_stage = judge_generation`
- `status = pending`
- `attempt_count = 0`

There is exactly one processing-state row per request in the current pipeline model.

## Ownership Boundary

The eval pipeline uses two layers of responsibility:

- eval orchestrator logic
- stage workers

Eval orchestrator logic owns:

- bootstrapping new rows into `eval_processing_state`;
- promoting `completed` rows into the next stage's `pending` state;
- creating run-level artifacts such as `run_manifest.json` and `run_report.md`.

Stage workers own:

- FIFO work selection within their current stage;
- stage-local state changes to `running`, `completed`, and `failed`;
- stage-local recovery for incomplete or resumable work;
- writes into their own downstream result tables.

## FIFO Processing Rule

The pipeline uses strict FIFO ordering.

The canonical work-selection ordering key is:

1. `request_received_at ASC`
2. `request_id ASC`

Each stage worker must claim its own work in this ordering.

The current pipeline assumes:

- one worker per stage
- no parallel workers for the same stage

For the current version, workers process one request at a time.

## Stage 1: `judge_generation`

### Input

`judge_generation` reads:

- the next `eval_processing_state` row where:
  - `current_stage = judge_generation`
  - `status != completed`
- the corresponding `request_captures` row for that `request_id`

### Processing

The stage must:

1. select the next FIFO-ordered row for `judge_generation` where the stage is not yet completed
2. inspect downstream `judge_generation_results` rows for the current `run_id`
3. determine which generation suites are still missing for that request
4. transition the selected state row to:
   - `current_stage = judge_generation`
   - `status = running`
5. evaluate only the missing generation suites for the request
6. write normalized generation judge rows into `judge_generation_results`
7. transition the state row to:
   - `current_stage = judge_generation`
   - `status = completed`

The worker must not rewrite existing generation-suite rows for the same `(request_id, run_id, suite_name)`.

The eval orchestrator later promotes:

- `judge_generation / completed -> judge_retrieval / pending`

### Output

`judge_generation` writes:

- `judge_generation_results`
- updated `eval_processing_state`

## Stage 2: `judge_retrieval`

### Input

`judge_retrieval` reads:

- the next `eval_processing_state` row where:
  - `current_stage = judge_retrieval`
  - `status != completed`
- the corresponding `request_captures` row for that `request_id`

### Processing

The stage must:

1. select the next FIFO-ordered row for `judge_retrieval` where the stage is not yet completed
2. inspect downstream `judge_retrieval_results` rows for the current `run_id`
3. determine which chunk-level retrieval judgments are still missing for that request
4. transition the selected state row to:
   - `current_stage = judge_retrieval`
   - `status = running`
5. evaluate only the missing chunk-level retrieval judgments for the request
6. write normalized chunk-level retrieval judge rows into `judge_retrieval_results`
7. transition the state row to:
   - `current_stage = judge_retrieval`
   - `status = completed`

The worker must not rewrite existing retrieval rows for the same `(request_id, run_id, suite_name, chunk_id)`.

The eval orchestrator later promotes:

- `judge_retrieval / completed -> build_request_summary / pending`

### Output

`judge_retrieval` writes:

- `judge_retrieval_results`
- updated `eval_processing_state`

`judge_retrieval` is a fan-out stage:

- it is scheduled per `request_id`
- it expands one request into multiple chunk-level judge rows
- the stage is considered complete only after all required chunk-level retrieval judge rows for that request have been written

## Stage 3: `build_request_summary`

### Input

`build_request_summary` reads:

- the next `eval_processing_state` row where:
  - `current_stage = build_request_summary`
  - `status != completed`
- the corresponding `request_captures` row for that `request_id`
- all `judge_generation_results` rows for the same `(request_id, run_id)`
- all `judge_retrieval_results` rows for the same `(request_id, run_id)`

### Processing

The stage must:

1. select the next FIFO-ordered row for `build_request_summary` where the stage is not yet completed
2. verify that all required upstream inputs for that request are fully available
3. transition the selected state row to:
   - `current_stage = build_request_summary`
   - `status = running`
4. derive one request-level summary record from:
   - `request_captures`
   - `judge_generation_results` for the same `(request_id, run_id)`
   - `judge_retrieval_results` for the same `(request_id, run_id)`
5. write or upsert one row into `request_summaries` and one row into `request_run_summaries`
6. transition the state row to:
   - `current_stage = build_request_summary`
   - `status = completed`

### Output

`build_request_summary` writes:

- `request_summaries`
- `request_run_summaries`
- updated `eval_processing_state`

`build_request_summary` is a fan-in stage:

- it reads chunk-level retrieval judge rows for one request
- it aggregates them into one request-level summary row

`request_summaries` is the current per-request derived summary table.

It is not a per-run historical summary table.

## Failure Behavior

Each stage follows the same failure pattern.

If a stage fails while processing a request:

1. the stage must update the corresponding `eval_processing_state` row to:
   - the same `current_stage`
   - `status = failed`
2. `last_error` must be updated with a non-empty failure description
3. `updated_at` must be refreshed

The stage must not silently skip a failed request.

## Recovery Behavior

Recovery is stage-local and owned by the worker for that stage.

For the current version:

- a worker may pick rows for its stage where `status = pending`, `status = running`, or `status = failed`;
- before issuing new judge calls or writes, the worker must inspect its downstream result table for the current `request_id` and `run_id`;
- the worker must write only missing stage outputs and must not overwrite existing completed outputs for the same logical key.

`running` therefore represents resumable incomplete work, not a permanently locked row.

## Retry Behavior

Retry semantics are stage-local and state-driven.

For the current version:

- `attempt_count` must be incremented whenever a stage begins a new processing attempt

Automatic retry policy is worker-defined, but reruns must remain logically idempotent.

## Idempotency Expectations

Each stage must be written to tolerate reruns safely for the same request and stage.

Expected behavior:

- `judge_generation` must not create semantically duplicate generation judge rows for the same request/run/suite combination
- `judge_retrieval` must not create semantically duplicate retrieval judge rows for the same request/run/suite/chunk combination
- `build_request_summary` must overwrite or upsert the current request summary for the same `request_id`

The exact DB-write strategy may differ by implementation, but the resulting stored state must remain logically idempotent.

## Implementation Shape

The current implementation shape is fixed as follows:

- `eval_orchestrator` is the only top-level Python CLI entrypoint for the eval pipeline;
- worker stages are in-process Python modules with explicit callable entrypoints;
- worker stages are invoked directly by the orchestrator, not through nested worker CLIs.

The architecture contract therefore fixes both:

- stage behavior and state-transition semantics;
- the top-level process boundary between orchestrator and worker modules.

## Placement Rules

### Architecture Specs

Architecture-level eval docs belong in:

- `Specification/architecture/`

### Eval Module Specs

Module-level eval implementation specs belong in:

- `Specification/codegen/evals/`

Examples:

- `Specification/codegen/evals/judge_generation.md`
- `Specification/codegen/evals/judge_retrieval.md`
- `Specification/codegen/evals/build_request_summary.md`
- `Specification/codegen/evals/eval_orchestrator.md`
- `Specification/codegen/evals/observability.md`

### Executable Eval Modules

Executable Python eval modules belong in:

- `Execution/evals/`

Examples:

- `Execution/evals/judge_generation.py`
- `Execution/evals/judge_retrieval.py`
- `Execution/evals/build_request_summary.py`
- `Execution/evals/eval_orchestrator.py`

For the current version:

- `Execution/evals/eval_orchestrator.py` is the canonical top-level CLI module;
- worker stages in `Execution/evals/` are in-process modules invoked by the orchestrator rather than standalone nested CLIs.

### Eval Contracts

Semantic contracts for eval artifacts belong in:

- `Specification/contracts/evals/`

Examples:

- `Specification/contracts/evals/run_manifest.md`
- `Specification/contracts/evals/run_report.md`

### Run Artifacts

Canonical run artifacts belong in:

- `Evidence/evals/runs/<run_started_at>_<run_id>/`

Required run artifacts for the current version:

- `Evidence/evals/runs/<run_started_at>_<run_id>/run_manifest.json`
- `Evidence/evals/runs/<run_started_at>_<run_id>/run_report.md`

For the current version:

- the timestamp prefix exists only to make artifact folders easier to identify in IDE and filesystem views;
- `run_id` remains the canonical run identity used inside storage tables, `run_manifest.json`, and `run_report.md`.
- `run_scope_request_ids` is immutable once the run starts.

# Hybrid Ingest Manifest Contract

This document defines the semantic contract for `run_manifest.json` produced by
`hybrid_ingest.py`.

## Purpose

`run_manifest.json` is the canonical run-level metadata record for one hybrid
ingest run.

It exists to:

- identify one ingest run
- record sparse-space provenance
- record vocabulary identity
- record collection compatibility inputs
- summarize run outcome

## Required Top-Level Fields

- `run_id`
- `status`
- `started_at`
- `pipeline`
- `embedding`
- `sparse`
- `qdrant`
- `artifacts`
- `counts`

## Optional Top-Level Fields

- `completed_at`
- `last_error`

## Field Semantics

### `run_id`

- stable UUID for one ingest run

### `status`

Allowed values for the current version:

- `running`
- `completed`
- `failed`

### `started_at`

- UTC timestamp recorded at run bootstrap

### `completed_at`

- UTC timestamp recorded only for terminal states

### `pipeline`

- object containing:
  - `name`
  - `ingest_config_version`
  - `corpus_version`

### `embedding`

- object containing:
  - `model_name`
  - `dimension`

### `sparse`

- object containing:
  - `strategy_kind`
  - `strategy_version`
  - `tokenizer_library`
  - `tokenizer_source`
  - `tokenizer_revision`, when present
  - `preprocessing_kind`
  - `lowercase`
  - `min_token_length`
  - `vocabulary_name`
  - `vocabulary_created_in_this_run`
  - `out_of_vocabulary_token_count`

### `qdrant`

- object containing:
  - `collection_name`
  - `dense_vector_name`
  - `sparse_vector_name`
  - `distance`

Rule:

- `collection_name` must be the derived effective Qdrant collection name used
  for runtime API calls, not the unsuffixed base collection name from config

### `artifacts`

- object containing:
  - `vocabulary_path`
  - `manifest_path`

### `counts`

- object containing:
  - `chunks_total`
  - `chunks_processed`
  - `chunks_failed`
  - `chunks_skipped`

## Naming Rule

For the current version:

- manifest filename must be `run_manifest.json`
- parent directory name must be `<started_at>_<run_id>`

## Invariants

- `chunks_total = chunks_processed + chunks_failed + chunks_skipped`
- if `status` is `completed` or `failed`, `completed_at` must be present
- if `status` is `running`, `completed_at` must be absent

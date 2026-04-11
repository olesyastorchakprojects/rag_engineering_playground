# Hybrid Ingest Layout

This directory contains runtime-facing config assets for the `hybrid` ingest
implementation variant.

## Canonical Files

- `ingest.toml`
  - canonical default runtime config for hybrid ingest

## `profiles/`

`profiles/` is reserved for chunk-source profiles consumed by the same hybrid
ingest implementation.

Current profiles:

- `fixed.toml`
- `structural.toml`

Use `profiles/` when the axis is:

- fixed vs structural chunk source
- or another input-profile distinction consumed by the same hybrid ingest engine

Do not use `profiles/` for sparse-strategy examples.

## `examples/`

`examples/` is reserved for strategy-oriented or otherwise non-canonical example
configs.

Current example:

- `bm25_like.toml`

Use `examples/` when the axis is:

- sparse strategy examples such as `bm25_like`
- exploratory or alternative config shapes that should not become the canonical
  default runtime config

## Naming Rule

- implementation variant lives in the path: `Execution/ingest/hybrid/`
- canonical runtime config uses role-based filename: `ingest.toml`
- chunk-source profiles use role-based filenames under `profiles/`
- strategy examples use descriptive filenames under `examples/`

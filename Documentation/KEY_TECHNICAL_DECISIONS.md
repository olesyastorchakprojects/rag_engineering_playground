# Key Technical Decisions

## Why There Is A Separate Documentation Layer

The repository already contains detailed contracts and code-generation specs.
This document captures the engineering rationale behind the most important
choices so that the project can be explained clearly to humans.

## 1. Rust For The Runtime, Python For The Pipelines

The project uses Rust for `rag_runtime` and Python for parsing, ingest, and
evaluation workflows.

Why this split was chosen:

- the online request path benefits from strong typing, explicit error handling,
  and controlled module boundaries
- pipeline tooling and orchestration benefit from Python's speed of iteration
  and good ecosystem support
- the repository can combine runtime rigor with experimental flexibility

This is a conscious hybrid architecture rather than an accident of incremental
growth.

## 2. Request Capture As The Canonical Eval Input

The system does not treat traces as the only source of truth for evaluation.
Instead, successful runtime requests are persisted as `RequestCapture` records
in PostgreSQL.

Why this matters:

- evaluation becomes schema-driven and reproducible
- downstream workers do not need to reconstruct runtime state from traces
- request-level provenance is stable across dashboards, summaries, and reports

This decision turns evaluation into a data pipeline rather than an observability
afterthought.

## 3. Separate Retrieval, Reranking, And Generation Boundaries

The runtime deliberately models:

- retrieval
- reranking
- generation

as separate stages with separate contracts.

Why this matters:

- each stage can be measured independently
- metrics and failure modes stay attributable
- experimentation is easier because components can be swapped without changing
  the whole pipeline model

This is especially important for comparing pass-through, heuristic, and
cross-encoder reranking.

## 4. Transport Abstraction For Cross-Encoder Reranking

Cross-encoder reranking is implemented through a transport interface instead of
binding provider-specific logic directly into the reranker.

Why this was chosen:

- batching and retry behavior belong near provider transport logic
- token counting can be handled per provider
- provider-specific request and response mapping stays isolated
- the orchestration layer can construct concrete transports without leaking
  provider details into the reranker core

This makes the cross-encoder path extensible and operationally cleaner.

## 5. Dense And Hybrid Retrieval As First-Class Variants

Dense retrieval and hybrid retrieval are not hidden behind vague configuration.
They are modeled explicitly in ingest, runtime, and eval artifacts.

Why this matters:

- retrieval strategy is an experimental variable that should be visible
- storage compatibility and collection semantics differ between strategies
- downstream reporting is more meaningful when retrieval family is explicit

The system is designed to compare retrieval strategies, not just run one.

## 6. Frozen Run Scope And Resume Semantics In Eval Runs

Eval runs use a fixed `run_id` and a frozen `run_scope_request_ids`.

Why this matters:

- a resumed run does not silently absorb new requests
- run artifacts remain semantically stable
- cross-run comparison becomes trustworthy
- failed runs can be resumed without corrupting the experiment boundary

This is one of the most important evaluation integrity decisions in the project.

## 7. Observability Is A Required Contract, Not Optional Instrumentation

The runtime and eval system are built with mandatory traces and metrics.

Why this matters:

- latency, dependency behavior, retries, and token usage are inspectable
- regressions are easier to detect
- engineering review can rely on real signals rather than guesswork
- dashboards become part of the operating model

The repository is intentionally built so that “it works” is not enough unless it
is also observable.

## 8. Schema-Driven Artifacts And Companion Files

The project uses explicit schemas and contracts for runtime configs, request
captures, eval manifests, and golden retrieval datasets.

Why this matters:

- invalid artifacts can be rejected early
- tooling can evolve without relying on undocumented conventions
- runtime, eval engine, and dashboards can share stable assumptions

This reduces drift between components.

## 9. Evidence Is Separate From Execution

The repository keeps produced outputs under `Evidence/` instead of mixing them
into implementation directories.

Why this matters:

- real run artifacts remain inspectable without polluting code paths
- datasets, manifests, reports, and experiments become part of the engineering
  record
- the project preserves the distinction between code, contracts, measurement,
  and evidence

That separation is one of the strongest structural choices in the repository.

## 10. Local Docker Stack As The Reproducible Operating Environment

The project treats the local Docker stack as part of the system, not just a
developer convenience.

Why this matters:

- observability and storage backends can be reproduced reliably
- demos and debugging sessions run against the same local environment
- project behavior can be validated end to end

This supports both engineering iteration and presentation readiness.

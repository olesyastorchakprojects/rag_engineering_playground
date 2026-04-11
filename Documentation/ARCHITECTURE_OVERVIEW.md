# Architecture Overview

## System Shape

The project is built as a pipeline-oriented RAG platform with explicit
boundaries between:

- corpus preparation
- indexing
- runtime serving
- request capture
- evaluation
- observability

The current implementation uses:

- Python for parsing, ingest, and eval orchestration
- Rust for the `rag_runtime` execution path
- Dockerized infrastructure for local storage and observability

## End-To-End Flow

The full system flow is:

1. source documents are extracted and cleaned
2. chunkers create chunk artifacts
3. ingest pipelines index chunks into Qdrant
4. `rag_runtime` handles end-to-end online request execution
5. successful requests are persisted as `RequestCapture`
6. the eval engine consumes captured requests and writes run-scoped outputs
7. dashboards and traces expose system behavior for inspection

## Major Subsystems

### Parsing And Chunking

Parsing lives under `Execution/parsing/`.
Its job is to turn source documents into structured text artifacts that can be
chunked and indexed.

The project supports multiple chunking strategies because chunk structure is a
first-class experimental variable.

The current strategies are:

- fixed chunking
- structural chunking

### Ingest

Ingest lives under `Execution/ingest/`.
Its job is to convert chunk artifacts into searchable vector-store records.

The repository supports two retrieval families:

- dense ingest
- hybrid ingest

Dense ingest builds one dense vector per chunk.
Hybrid ingest builds dense plus sparse representations for the same chunk set.

Qdrant is used as the retrieval store.

### RAG Runtime

The online runtime lives under `Execution/rag_runtime/` and is implemented as a
Rust crate.

The runtime pipeline is:

1. input validation
2. retrieval
3. optional reranking
4. generation
5. request capture

This runtime is intentionally structured as one coordinated crate with explicit
module boundaries rather than a set of loosely coupled scripts.

### Reranking

Reranking is a distinct stage between retrieval and generation.

The project currently supports:

- pass-through reranking
- heuristic reranking
- cross-encoder reranking

Cross-encoder reranking uses a transport abstraction, which allows the runtime
to support multiple provider-specific implementations behind a single internal
interface.

### Request Capture

Every successful request produces a canonical `RequestCapture`.

This capture includes:

- query inputs
- retrieval outputs
- reranking outputs
- generation token usage
- configuration snapshots
- retrieval and reranking quality metrics, when available

`RequestCapture` is the stable source record for downstream evaluation.

### Eval Engine

The eval engine lives under `Execution/evals/`.
It is a run-oriented sequential pipeline built around frozen run scope and
resume semantics.

The current worker stages are:

- `judge_generation`
- `judge_retrieval`
- `build_request_summary`

Eval outputs are written both to storage tables and to run artifacts such as:

- `run_manifest.json`
- `run_report.md`

### Observability And Dashboards

Observability uses:

- OpenTelemetry
- Tempo
- Phoenix
- Prometheus
- Grafana

The system emits:

- request spans
- stage spans
- dependency metrics
- latency histograms
- token and cost metrics

This allows the project to be analyzed from both an application view and an
experiment view.

## Storage Model

The architecture uses multiple storage layers with different responsibilities:

- Qdrant
  - retrieval index and chunk search backend
- PostgreSQL
  - request captures, eval state, judge outputs, summaries, run-level data
- filesystem artifacts in `Evidence/`
  - datasets, manifests, reports, and run artifacts

This separation is deliberate:
vector retrieval, structured evaluation state, and produced evidence are not
collapsed into a single storage system.

## Local Runtime Stack

The project runs locally through Docker compose files under `Execution/docker/`.

The local stack includes:

- PostgreSQL
- Tempo
- Phoenix
- OpenTelemetry Collector
- Prometheus
- Grafana
- Qdrant
- Ollama
- cross-encoder reranker service

This makes the system reproducible for development, debugging, evaluation, and
presentation.

## Architectural Character

The most important architectural property of the project is that it treats a
RAG system as an observable, evaluable, and reproducible pipeline rather than
just an answer generator.

That orientation drives nearly every subsystem boundary in the repository.

# Project Overview

## What This Project Is

This project is a fully instrumented retrieval-augmented generation platform
for experimentation, evaluation, and engineering iteration.

It is not only a question-answering runtime.
It also includes:

- offline parsing and chunking pipelines
- dense and hybrid ingest pipelines
- a modular RAG runtime
- request capture and evaluation storage
- an eval engine with resumable runs
- dashboards, traces, and operational observability

The repository is designed so that the same system can be:

- run locally end to end
- evaluated reproducibly
- inspected at the request, run, and trace level
- evolved through explicit contracts and schemas

## What Problem It Solves

Many RAG projects can answer a question, but they are difficult to inspect,
compare, and improve systematically.

This project focuses on the harder engineering problem:

- how to build a RAG system whose retrieval, reranking, generation, costs,
  traces, and evaluation outputs can all be observed and compared reliably

The result is a repository that supports both product behavior and engineering
discipline.

## What The System Does End To End

At a high level, the system works like this:

1. a source corpus is parsed into structured pages and chunks
2. chunks are indexed through dense or hybrid ingest
3. the runtime receives a query, validates it, retrieves candidate chunks,
   optionally reranks them, and generates an answer
4. the runtime persists one canonical `RequestCapture` for each successful
   request
5. the eval engine reads captured requests, runs judge stages, writes derived
   outputs, and produces run artifacts such as `run_manifest.json` and
   `run_report.md`
6. Grafana, Tempo, Phoenix, and PostgreSQL make the behavior inspectable across
   runtime and eval workflows

## Why The Repository Is Valuable

The project combines several strengths that are often built separately:

- retrieval experimentation
- modular reranking
- reproducible evaluation
- request-level provenance
- cost and token tracking
- end-to-end observability

That makes it useful not only as a prototype RAG application, but as an
engineering platform for answering questions such as:

- which retrieval strategy performs better on this corpus?
- does reranking improve retrieval quality enough to justify its cost?
- how do latency and cost change across runs?
- can a failed eval run be resumed safely without changing the run scope?
- which concrete runtime settings produced a given result?

## Current Scope

The current repository already supports:

- fixed and structural chunking strategies
- dense and hybrid retrieval
- pass-through, heuristic, and cross-encoder reranking
- multiple transport-backed generation and reranking providers
- request capture into PostgreSQL
- request-level retrieval and reranking metrics
- resumable evaluation runs
- Grafana dashboards for runtime and eval inspection
- OTEL traces and Prometheus metrics

## Repository Model

The repository is organized into four operational layers:

- `Execution/`
  - runnable code, configs, tests, and local stack definitions
- `Specification/`
  - contracts, architecture documents, and generation-oriented source of truth
- `Measurement/`
  - dashboards and measurement logic
- `Evidence/`
  - run artifacts, datasets, manifests, reports, and produced outputs

This separation is one of the core project ideas:
runtime logic, contracts, measurement, and evidence are treated as distinct
engineering concerns.

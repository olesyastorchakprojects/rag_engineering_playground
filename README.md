# RAG Engineering Playground

A specification-first RAG engineering playground focused on controlled experimentation, evaluation, and observability.

This repository is designed for building, inspecting, and comparing retrieval pipelines end to end. It emphasizes request-level evidence capture, offline evaluation, comparative reporting, and observability-driven diagnosis.

The project focuses on making RAG systems easier to inspect, compare, and improve.

---

## Why this project exists

In RAG systems answer quality depends on multiple upstream decisions: document preparation, chunking, retrieval, reranking, and generation.

This project exists to make those layers easier to study as a system.

It is built around four engineering goals:

- **Inspectability** — each request can be examined across retrieval, reranking, generation, and evaluation.
- **Comparability** — different pipeline variants can be evaluated on the same request set.
- **Reproducibility** — evaluation runs operate on persisted request evidence and produce stable artifacts.
- **Specification-first design** — interfaces, schemas, and boundaries are treated as core engineering assets.

---

## Project focus

This repository is focused on:

- controlled RAG experiments,
- request-level evidence capture,
- offline evaluation workflows,
- comparative analysis of pipeline variants,
- observability for diagnosis and iteration.

It is intended as an engineering playground for understanding system behavior, not only for producing answers.

---

## What is implemented

### Data preparation
- Structural chunking
- Fixed-size chunking
- Dense ingest
- Hybrid ingest (bag-of-words and bm25)

### Retrieval and ranking
- Dense retrieval
- Hybrid retrieval (bag-of-words and bm25)
- Heuristic reranker
- Cross-encoder reranker

### Evaluation
- Request capture for later offline evaluation
- Persisted evaluation runs
- Comparative reports across pipeline variants
- Retrieval and answer-level metrics

### Observability
- Traces for request-level inspection
- Metrics and dashboards for aggregate behavior


---

## What this project demonstrates

This repository is designed to support engineering questions such as:

- How does chunking strategy affect retrieval and downstream generation?
- Do retrieval gains translate into answer-quality gains?
- How much does reranking change final system behavior?
- Which metrics expose useful differences between pipeline variants?
- How can request-level evidence be preserved for later comparison and analysis?

The purpose of the project is to make those questions easier to answer with artifacts, runs, and system evidence.

### Current findings

Based on the current experiment reports, several patterns already stand out:

- chunking strategy changes retrieval behavior in meaningful ways;
- retrieval gains do not always propagate to answer-level gains;
- reranking effects are often easier to observe at ranking level than at final-answer level;
- comparative evaluation is necessary because intuition alone is not a reliable guide.

These are working findings rather than final claims, but they already make the project useful as an engineering learning and diagnosis environment.

---

## Core architectural idea

A central design choice in this repository is treating **request capture** as a first-class architectural boundary.

Instead of relying only on live pipeline replay, the system preserves request-level evidence that can later be reused for offline evaluation and comparison. This makes experiment runs easier to inspect, compare, and reason about over time.

That boundary helps separate:

- online execution,
- persisted evidence,
- offline evaluation,
- and aggregate reporting.

---

## Architecture at a glance

![alt text](Documentation/img/Architecture.svg)
### Language split

- **Python** is used for parsing, chunking, and ingest workflows.
- **Rust** is used for runtime structure, orchestration, and stronger system boundaries.

This split reflects the different engineering needs of document-processing workflows and runtime pipeline components.

---

## Engineering principles

The repository is organized around a small set of principles:

- **Explicit boundaries** over implicit coupling
- **Evidence preservation** over one-off inspection
- **Comparative evaluation** over isolated results
- **Observability as a system layer**
- **Specifications and schemas** as tools for keeping behavior explicit

---

## Current scope

This project is currently optimized for:

- local experimentation,
- pipeline diagnosis,
- retrieval and answer-quality comparison,
- evaluation workflow design,
- observability-driven analysis.

It is not currently positioned as a production-ready multi-tenant RAG platform.

---

## Why this repository may be useful

This repository may be useful if you are interested in:

- RAG system design beyond the happy path,
- evaluation-first AI engineering,
- observability-first pipeline iteration,
- comparing chunking, retrieval, and reranking strategies,
- building systems that are easier to diagnose and reason about.

---

## Repository reading path

If you are reviewing this repository, start here:

1. **[Architecture Overview](Documentation/ARCHITECTURE_OVERVIEW.md)**
   Pipeline shape, subsystem boundaries, and main architectural ideas.

2. **[Evaluation Story](Documentation/EVALUATION_STORY.md)**
   How request capture, evaluation runs, judge stages, and reports fit together.

3. **[Observability Story](Documentation/OBSERVABILITY_STORY.md)**
   How traces, metrics, dashboards, and local infrastructure support diagnosis.

4. **[Specification-First Approach](Documentation/SPECIFICATION_FIRST_APPROACH.md)**
   Why specs, schemas, and explicit contracts are central in this project.

5. **[Documentation README](Documentation/README.md)**
   Full documentation map and recommended reading order.

---

## Evidence surfaces

This repository includes several places where the system’s behavior and experiment outcomes can be inspected directly:

- **[Comparative experiment report](Documentation/EXPERIMENTS_20Q_COMPARATIVE_REPORT.md)** — side-by-side findings across evaluated pipeline variants
- **[Evaluation flow](Documentation/EVALUATION_STORY.md)** — request capture, run boundaries, judge stages, and reporting flow
- **[Observability documentation](Documentation/OBSERVABILITY_STORY.md)** — traces, dashboards, metrics, and diagnostic surfaces
- **[Architecture overview](Documentation/ARCHITECTURE_OVERVIEW.md)** — end-to-end system shape and subsystem boundaries
- **[Key technical decisions](Documentation/KEY_TECHNICAL_DECISIONS.md)** — the main engineering choices and their rationale

The repository is structured to support inspection, comparison, and iteration through evidence.

---

## Tech stack

- **Rust** — runtime and orchestration components
- **Python** — parsing, chunking, ingest, and experiment-support workflows
- **Qdrant** — vector search
- **Postgres** — request capture store
- **Grafana / Tempo / Phoenix / OTEL-based tooling** — observability and analysis

---

## Repository structure

The repository is organized around six top-level areas:

- `Execution/`: runnable code, configs, tests, launcher entrypoints, and local stack definitions
- `Specification/`: contracts, schemas, architecture docs, and codegen-oriented source of truth
- `Measurement/`: dashboards, observability assets, and evaluation measurement surfaces
- `Evidence/`: datasets, run artifacts, manifests, reports, and produced outputs
- `Documentation/`: human-oriented narrative docs for onboarding, architecture review, evaluation interpretation, observability, and project presentation
- `AgentContext/`: agent-operating rules, multi-agent workflow conventions, and repository-specific guidance for agent-driven work

This split is deliberate.
The project treats execution, specification, measurement, evidence, documentation, and agent context as separate engineering concerns.

---

## Running the project

See **[Run From Zero](Documentation/RUN_FROM_ZERO.md)** for environment setup and local execution.

---

## Future directions

Natural next directions for this repository include:

- stronger answer-level validation metrics,
- broader experiment matrices,
- richer comparison dashboards,
- larger evaluation sets,
- deeper reranker benchmarking,
- stronger citation and grounding validation.

---

## Documentation

See **[Documentation README](Documentation/README.md)** for the current documentation map and recommended reading path.

---

## Summary

This repository is an engineering playground for treating RAG as a system that can be:

- inspected,
- compared,
- evaluated,
- and improved with evidence.

Its purpose is not only to produce answers, but to make pipeline behavior easier to understand.

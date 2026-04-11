# Fully Instrumented RAG Engineering Playground

This repository is a specification-first RAG engineering playground for local experimentation, evaluation, and observability.

It is not just a question-answering runtime.
It also includes:

- parsing and chunking pipelines
- dense and hybrid ingest pipelines
- a modular RAG runtime
- reranking variants
- request capture and evaluation storage
- resumable eval runs with run artifacts
- traces, metrics, and local dashboards
- repository-aware MCP servers and agent-oriented workflow support

The project was built to answer a practical engineering question:
how do you make a RAG system inspectable enough to compare retrieval, reranking, generation, costs, and evaluation behavior with confidence?

## What This Project Already Proves

The repository already demonstrates that the system can be:

- specified through explicit contracts and schemas
- run locally end to end
- evaluated reproducibly on a fixed benchmark
- inspected at the request, run, and trace level
- compared across retrieval, chunking, and reranking strategies

The strongest evidence block in the repository is the 20-question comparative evaluation report:

- [20-question comparative report](Documentation/EXPERIMENTS_20Q_COMPARATIVE_REPORT.md)

That document is the best place to answer the question:
"What did this project actually prove?"

## Main Capabilities

- chunking: `fixed`, `structural`
- retrieval: `dense`, `hybrid` with `bag_of_words` and `bm25_like`
- reranking: `pass_through`, `heuristic`, `cross_encoder`
- generation: local Ollama models and OpenAI-compatible providers
- evaluation: request capture into PostgreSQL, judge-based eval stages, resumable runs, manifests, and reports
- observability: OpenTelemetry traces, Prometheus metrics, Grafana dashboards, Phoenix, and Tempo

## Start Here

If you are new to the repository, use this reading order:

1. [Project Overview](Documentation/PROJECT_OVERVIEW.md)
2. [Run From Zero](Documentation/RUN_FROM_ZERO.md)
3. [Architecture Overview](Documentation/ARCHITECTURE_OVERVIEW.md)
4. [20-question Comparative Report](Documentation/EXPERIMENTS_20Q_COMPARATIVE_REPORT.md)
5. [Evaluation Story](Documentation/EVALUATION_STORY.md)
6. [Observability Story](Documentation/OBSERVABILITY_STORY.md)
7. [MCP Servers And Tools](Documentation/MCP_SERVERS_AND_TOOLS.md)
8. [Agent Workflow Story](Documentation/AGENT_WORKFLOW_STORY.md)

For a fuller document index, see [Documentation/README.md](Documentation/README.md).

## Repository Shape

The repository is organized into four operational layers:

- `Execution/`: runnable code, configs, tests, launcher entrypoints, and local stack definitions
- `Specification/`: contracts, schemas, architecture docs, and codegen-oriented source of truth
- `Measurement/`: dashboards, observability assets, and evaluation measurement surfaces
- `Evidence/`: datasets, run artifacts, manifests, reports, and produced outputs

This split is deliberate.
The project treats runtime logic, specifications, measurement, and evidence as separate engineering concerns.

Two additional top-level areas are also first-class parts of the repository model:

- `Documentation/`: human-oriented narrative docs for onboarding, architecture review, evaluation interpretation, observability, and project presentation
- `AgentContext/`: agent-operating rules, multi-agent workflow conventions, and repository-specific guidance for agent-driven work

These are not incidental supporting folders.
They document how humans and agents are expected to understand, navigate, and operate the system.

## Local Reproduction

The canonical repository-native onboarding path is [Run From Zero](Documentation/RUN_FROM_ZERO.md).

That guide is designed for local engineering reproduction.
It is not a polished deployment surface and does not claim to guarantee a frictionless bring-up on every clean machine.
Instead, it gives a concrete path, real commands, real configs, and expected system surfaces so the project can be brought up and debugged locally.

## Evaluation And Evidence

The repository keeps the evidence used to support its conclusions:

- benchmark datasets under `Evidence/evals/datasets/`
- recorded eval runs under `Evidence/evals/runs/`
- the synthesized comparative report in [Documentation/EXPERIMENTS_20Q_COMPARATIVE_REPORT.md](Documentation/EXPERIMENTS_20Q_COMPARATIVE_REPORT.md)

The main current findings are:

- structural chunking is promising but not universally dominant
- hybrid BM25 is the stronger sparse default
- pass-through is a stronger baseline than expected
- dense retrieval remains competitive
- retrieval quality and answer quality do not move together linearly

## Agent And MCP Story

This project also documents how repository-aware agents were used during development:
[MCP Servers And Tools](Documentation/MCP_SERVERS_AND_TOOLS.md) and
[Agent Workflow Story](Documentation/AGENT_WORKFLOW_STORY.md).

These documents explain how project-specific MCP servers, specifications, and workflow structure were used to support implementation and analysis work.

## Current Boundaries

This repository is already a mature experimental RAG platform, but it is intentionally not everything.

Notable boundaries:

- the local engineering path is stronger than the deployment story
- some future hardening work is intentionally deferred into backlog instead of being stretched into the current scope

See [BACKLOG.md](BACKLOG.md) for consciously deferred work.

# Repository Map

## Purpose

This document explains the repository layout in human terms.

It is especially useful for presentation, onboarding, and architecture review
because the repository intentionally separates implementation, contracts,
measurement, and produced evidence.

That separation is one of the strongest expressions of the project's
specification-first approach.

## Top-Level Areas

The repository is organized around several top-level directories, each with a
clear role.

### `Execution/`

`Execution/` contains runnable code and the files needed to operate the system.

This includes:

- runtime code
- eval engine code
- ingest pipelines
- tests
- local launchers
- Docker compose files
- runtime configuration
- runtime schemas

If something is executed, tested, or started, it usually belongs here.

### `Specification/`

`Specification/` contains the written source of truth for how the system is
supposed to behave.

This includes:

- architecture documents
- code-generation specs
- storage contracts
- runtime contracts
- test matrices
- schema ownership documents

This is the repository's contract layer.

### `Measurement/`

`Measurement/` contains the logic and assets used to measure and visualize
system behavior.

This includes:

- Grafana dashboards
- observability artifacts
- evaluation measurement surfaces

This layer is about how behavior is observed and compared.

### `Evidence/`

`Evidence/` contains produced artifacts from actual runs and experiments.

This includes:

- datasets
- chunk artifacts
- golden retrieval companions
- run manifests
- run reports
- experimental outputs

This layer answers the question:
what actually happened when the system ran?

### `Documentation/`

`Documentation/` contains narrative documentation for humans.

This is where presentation-oriented and explanatory documents live.

It is not the same as `Specification/`.
`Documentation/` explains the project; `Specification/` constrains it.

### `Tools/`

`Tools/` contains repository-owned helper tooling.

The most important subtree is:

- `Tools/mcp/`

This is where the project-specific MCP servers, their routing policies, their
schemas, and their tests live.

The MCP layer is part of the repository's public engineering story because it
lets agents inspect repository context, runtime truth, and workflow state
through explicit tools instead of ad hoc scripts.

### `AgentContext/`

`AgentContext/` is reserved for repository conventions and agent-oriented
working context.

It is part of how the repository supports structured development workflows.

## Why This Structure Matters

This layout is not cosmetic.

It prevents several common repository problems:

- executable code mixed with produced artifacts
- contracts hidden inside implementation details
- dashboards drifting without clear ownership
- experiment outputs scattered across source directories

The structure makes the project easier to:

- navigate
- explain
- validate
- extend

## A Simple Mental Model

One useful way to remember the repository is:

- `Execution/` = what runs
- `Specification/` = what must be true
- `Measurement/` = how we observe and compare
- `Evidence/` = what happened in reality
- `Documentation/` = how we explain it to humans

That mental model is one of the clearest ways to understand the project.

## Subsystem Hints

If you want to inspect a specific concern, use this shortcut map.

### Runtime request path

Start in:

- `Execution/rag_runtime/`

Then see:

- `Specification/codegen/rag_runtime/`
- `Specification/contracts/rag_runtime/`

### Eval engine

Start in:

- `Execution/evals/`

Then see:

- `Specification/architecture/evals_architecture.md`
- `Specification/contracts/evals/`
- `Specification/contracts/storage/`

### Ingest and retrieval indexing

Start in:

- `Execution/ingest/dense/`
- `Execution/ingest/hybrid/`

Then see:

- `Specification/codegen/ingest/`
- `Specification/contracts/ingest/`

### Dashboards and observability

Start in:

- `Measurement/`
- `Execution/docker/`

Then see:

- `Specification/codegen/rag_runtime/observability/`
- `Documentation/OBSERVABILITY_STORY.md`

### Datasets and experimental artifacts

Start in:

- `Evidence/`

Especially:

- `Evidence/evals/`
- `Evidence/parsing/`

## Why This Is Good For Presentation

When presenting the project, this structure lets you explain the repository as
an engineered system instead of a pile of scripts.

That is one of the reasons the project feels larger and more deliberate than a
typical prototype:
the repository shape itself communicates its priorities.

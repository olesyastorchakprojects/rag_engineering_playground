# Documentation Index

This folder contains the human-oriented documentation for the project.

These documents explain the repository as an engineering system: what it is for, how it is structured, how it is evaluated, how it is observed, and how its main design decisions fit together.

They complement the repository’s implementation, contracts, schemas, and generated artifacts, but they do not replace them.

---

## Recommended reading path

If you want the fastest high-level understanding of the project, read the documents in this order:

1. **[Architecture Overview](ARCHITECTURE_OVERVIEW.md)**
   High-level system shape, repository framing, and the main architectural idea.

2. **[Evaluation Story](EVALUATION_STORY.md)**
   How request capture, evaluation runs, judge stages, and reports fit together.

3. **[Observability Story](OBSERVABILITY_STORY.md)**
   How traces, metrics, dashboards, and local infrastructure support diagnosis.

4. **[Specification-First Approach](SPECIFICATION_FIRST_APPROACH.md)**
   Why specs, schemas, and explicit contracts are central in this project.

5. **[Key Technical Decisions](KEY_TECHNICAL_DECISIONS.md)**
   The main design choices in the repository and the reasoning behind them.

6. **[Run From Zero](RUN_FROM_ZERO.md)**
   Canonical setup and local execution path from a clean machine.

---

## Core project narrative

These documents form the main narrative of the repository:

### [Architecture Overview](ARCHITECTURE_OVERVIEW.md)
The end-to-end system shape, the major subsystem boundaries, and the role of request capture in the overall design.

### [Evaluation Story](EVALUATION_STORY.md)
How the project turns request-level evidence into reusable evaluation runs, comparison artifacts, and engineering conclusions.

### [Golden Datasets](GOLDEN_DATASETS.md)
How fixed question sets and golden retrieval companions support controlled runtime evaluation and comparable runs.

### [Observability Story](OBSERVABILITY_STORY.md)
How traces, metrics, dashboards support request-level inspection and aggregate diagnosis.

### [Specification-First Approach](SPECIFICATION_FIRST_APPROACH.md)
How specifications, schemas, and explicit contracts are used to keep behavior, interfaces, and repository structure clear.

---

## Supporting engineering documents

These documents provide additional detail once the main project shape is clear:

### [Run From Zero](RUN_FROM_ZERO.md)
The canonical onboarding and local bring-up path.

### [Key Technical Decisions](KEY_TECHNICAL_DECISIONS.md)
The main design choices in the repository and the reasoning behind them.

### [Repository Map](REPOSITORY_MAP.md)
How the main repository areas reflect the split between execution, specification, measurement, evidence, and documentation.

---

## Agent and tooling documents

These documents explain the parts of the repository that support agent-driven work and project-aware tooling:

### [MCP Servers and Tools](MCP_SERVERS_AND_TOOLS.md)
How project-specific MCP servers expose repository-aware capabilities.

### [Agent Workflow Story](AGENT_WORKFLOW_STORY.md)
How the repository supports structured multi-agent work, control, and coordination.

### [Agent Role In Project](AGENT_ROLE_IN_PROJECT.md)
How coding agents practically accelerated work in this repository, where MCP mattered, and where human judgment remained essential.

---

## Experiment evidence

For direct experiment outcomes and comparative findings, see:

### [Experiments: 20Q Comparative Report](EXPERIMENTS_20Q_COMPARATIVE_REPORT.md)
A comparative report across evaluated pipeline variants, including current findings and open questions.

### [Tagged Question Metrics Report](TAGGED_QUESTION_METRICS_REPORT.md)
A follow-up analysis that recomputes key metrics by question type to separate retrieval-sensitive slices from generation-limited slices.

---

## Images and diagrams

### [img/](img/)
Supporting diagrams and visual assets used by the documentation.

---

## How to use this folder

A practical way to navigate this documentation is:

- start with the project-level story,
- move to architecture,
- then read evaluation and observability together,
- and only after that go deeper into setup, repository layout, and supporting engineering documents.

If you are reviewing the repository from the top-level `README.md`, this index is the next entry point once you want more detail.

---

## Related repository areas

This folder is only one part of the repository model.

For implementation, contracts, measurement assets, and produced evidence, see the top-level repository areas referenced throughout the docs and the main README.

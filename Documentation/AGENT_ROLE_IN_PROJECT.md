# Agent Role In Project

## What this document covers

This document explains the practical role that coding agents played in this repository.

It is not a policy document and not a replacement for `AGENT_WORKFLOW_STORY.md`.
Its goal is narrower:

- to describe which kinds of work agents actually accelerated;
- to show where MCP servers were important rather than optional;
- to explain the typical workflow around agent-assisted work;
- to make clear where human judgment remained necessary.

In other words, this document focuses on the agent as an engineering accelerator inside this project, not as an abstract automation concept.

---

## Why agent assistance mattered in this repository

This repository is not a small single-layer application.
It combines:

- runnable execution code;
- explicit specifications and contracts;
- evaluation pipelines and run artifacts;
- observability assets and dashboards;
- MCP-backed inspection surfaces;
- human-oriented documentation.

That structure creates a lot of cross-file and cross-layer work.

Many tasks in the project are not difficult because one file is complex.
They are difficult because correctness depends on keeping multiple surfaces aligned:

- code and contracts;
- eval artifacts and storage truth;
- runtime behavior and observability surfaces;
- README-level framing and deeper architecture docs.

This is exactly the kind of environment where an agent can create leverage.

---

## What the agent actually accelerated

The strongest value did not come from "writing code faster" in isolation.
It came from reducing the cost of repository-wide engineering tasks that would otherwise require a lot of manual traversal, checking, and synthesis.

### 1. Repository navigation and source-of-truth lookup

The repository contains runnable code, specs, generated artifacts, dashboards, eval artifacts, and agent tooling spread across multiple top-level areas.

Agents were useful for quickly answering questions like:

- where the authoritative contract for a feature lives;
- whether a behavior is defined in code, in spec, or in both;
- which files are relevant to one concept across execution, specification, and documentation layers.

This reduced the overhead of re-orienting before each change.

### 2. Cross-file consistency work

A large share of the practical value came from checking whether multiple documents or components still agreed with one another.

Examples of that kind of work include:

- checking whether `README.md` and narrative docs describe the same architecture;
- finding broken or stale documentation links;
- comparing architectural descriptions against actual repository structure;
- spotting drift between report docs, eval artifacts, and run-level contracts.

This kind of work is tedious manually and well suited to agent-assisted inspection.

### 3. Spec-to-code and spec-to-doc alignment

Because the repository is specification-first, many engineering tasks depend on locating the right contract before changing anything.

Agents helped accelerate:

- tracing implementation back to source-of-truth specs;
- checking whether current code shape still matches the declared contract;
- surfacing mismatches between docs, specs, and implementation before they become larger drift.

### 4. Evaluation-run inspection and artifact interpretation

The project contains persisted eval runs, manifests, reports, and run-scoped summaries.

Agents were useful for:

- locating the relevant run artifact quickly;
- checking whether a run report, manifest, and storage-backed interpretation are consistent;
- comparing what a narrative document claims against the actual checked-in eval evidence.

This was especially helpful in a repository where "what happened in a run" matters as much as "what the code is supposed to do."

### 5. Observability-oriented debugging and inspection

The observability layer is rich enough that manual debugging can become expensive.

Agents helped by:

- locating the right observability contracts;
- relating runtime stages to traces, metrics, and dashboards;
- identifying where a question should be answered through code inspection versus observability surfaces.

### 6. Documentation production and repair

Agents also accelerated writing and revising documentation when the task required:

- synthesizing information from multiple source files;
- preserving consistent terminology;
- aligning high-level narrative with lower-level project structure;
- checking that docs were not overselling unsupported capabilities.

This did not remove the need for editorial judgment, but it reduced the mechanical burden substantially.

---

## Where MCP servers were necessary

The agent was most effective when it did not have to treat the repository and local system as opaque.

The project-specific MCP layer mattered because many useful questions were not "search the codebase" questions.
They were questions about system truth, run truth, storage truth, or source-of-truth documents.

### `spec`

The `spec` server was important whenever the task depended on the formal source of truth.

Typical use:

- find the canonical contract for a topic;
- locate validation context before changing code;
- resolve whether a behavior is intended or merely present in implementation.

### `spec_conformance`

This server mattered when the question was not just "what does the spec say?" but "where has implementation drifted from it?"

Typical use:

- compare curated requirements against current code capability;
- identify uncovered requirements;
- understand which touched files affect conformance checks.

### `project_context`

This server helped orient the agent to repository boundaries and operational ownership.

Typical use:

- determine which subsystem owns a concept;
- understand storage ownership;
- avoid reasoning about the repository as one undifferentiated codebase.

### `postgres`

This server was important for evaluation and request-capture truth.

Typical use:

- inspect `request_captures`;
- check eval stage state;
- verify what one run actually materialized in storage;
- compare documentation claims against stored run/eval reality.

### `qdrant`

This server mattered whenever retrieval truth lived in the vector store rather than in static code or docs.

Typical use:

- inspect collections;
- check payload shape;
- validate ingest / retrieval compatibility assumptions.

### `observability`

This server was important when correctness or diagnosis depended on the live observability surface rather than on static files alone.

Typical use:

- inspect dashboard definitions;
- check collector wiring and stack health;
- locate traces and verify what runtime telemetry actually exposes.

### `eval_experiments`

This server mattered when the task was run-oriented rather than row-oriented.

Typical use:

- summarize runs;
- compare runs;
- inspect run artifact health;
- reason from manifests and reports without manually traversing all artifacts.

### `agent_orchestrator`

This server was important for structured multi-agent work on larger tasks.

Typical use:

- plan a task as staged work;
- preserve workflow state;
- separate planning, implementation, verification, and review roles.

Without these MCP servers, the agent could still search files, but it would lose much of its advantage on repository-aware engineering work.

---

## Typical workflow

The most effective agent-assisted work in this project followed a fairly stable pattern.

### 1. Orient to the task

Before making changes, the agent first identified:

- the subsystem involved;
- the likely source-of-truth documents;
- the relevant runtime, eval, or observability surfaces.

This mattered because the repository rewards correct orientation more than premature editing.

### 2. Gather source-of-truth context

The next step was usually to read:

- the relevant spec or contract;
- the architectural document for that subsystem;
- the current implementation or artifact shape.

For many tasks, this was the difference between a grounded change and an improvized one.

### 3. Check live or stored truth when needed

If the task depended on current run state, request evidence, retrieval truth, or observability behavior, the agent used the relevant MCP server instead of relying only on static files.

This was especially important for:

- eval runs;
- request-capture interpretation;
- observability diagnostics;
- retrieval-store inspection.

### 4. Implement or review

Once context was assembled, the agent either:

- made a bounded change;
- produced findings from a consistency review;
- or prepared a smaller scoped fix.

### 5. Verify

After implementation or analysis, the agent checked:

- tests;
- conformance surfaces;
- file-level consistency;
- artifact and link integrity;
- residual risk.

### 6. Hand back a summary with remaining uncertainty

The final step was not just "done."
It was a compact explanation of:

- what changed or what was found;
- what was verified;
- what still required human interpretation or decision.

---

## What multi-agent workflow added on harder tasks

For simple work, a single agent loop was often enough.

For more complex work, the repository's multi-agent workflow added value by keeping roles explicit.

The useful pattern was not "many agents for everything."
It was more structured:

1. one coordinator or orchestrator preserves scope and sequencing;
2. implementation work is narrowed to a bounded area;
3. tests or conformance checks are treated as their own responsibility;
4. runtime verification or review remains explicit instead of assumed.

This mattered because the project is spec-heavy and cross-layer.
A large change can look locally correct while still drifting from:

- contracts;
- storage expectations;
- run artifacts;
- dashboard assumptions;
- documentation framing.

The workflow architecture helped reduce that risk by preserving separation between writing, checking, and interpreting.

---

## Where human judgment still mattered

Agent assistance was useful, but it did not replace the role of the engineer.

There were several places where human judgment remained essential.

### 1. Deciding design intent

The agent could trace current behavior and compare it to specs, but it could not authoritatively decide which competing interpretation the project should adopt.

That remained a human decision, especially when:

- code and docs disagreed;
- an implementation existed before the contract was fully stabilized;
- multiple valid abstractions were possible.

### 2. Interpreting experiment significance

The agent could summarize metrics, compare runs, and surface patterns.
But deciding whether a result actually mattered remained human work.

That included questions like:

- is this difference meaningful or noise;
- does a retrieval gain justify additional complexity;
- is a benchmark result presentation-worthy or still too preliminary.

### 3. Choosing trade-offs

The repository includes many trade-offs:

- readability vs completeness in docs;
- simplicity vs flexibility in architecture;
- narrow fixes vs broader cleanup;
- local correctness vs stronger generality.

Agents could frame trade-offs, but the choice among them remained human-owned.

### 4. Accepting risk

An agent can report uncertainty and verification gaps.
It should not be the final authority on whether residual risk is acceptable.

That was especially true for:

- architecture changes;
- documentation claims about supported capabilities;
- changes that affect evaluation interpretation;
- changes that alter operational or observability assumptions.

### 5. Editorial and narrative quality

For docs, the agent could help with structure, consistency, and synthesis.
But the final decision about voice, emphasis, and project narrative remained human.

This matters in a repository that is not only functional, but also presentational and explanatory.

---

## Practical boundary

The agent worked best in this project as an accelerator, not as an authority.

Its strongest contributions were:

- reducing search and orientation cost;
- making cross-file consistency work cheaper;
- surfacing drift across code, specs, docs, and artifacts;
- using MCP-backed inspection surfaces to reduce blind spots;
- helping structure complex work into clearer stages.

The human role remained:

- deciding intent;
- judging significance;
- accepting trade-offs;
- and owning the final interpretation of the repository as a system.

That boundary was not a weakness of agent-assisted work.
It was part of what made the workflow reliable.

---

## Relationship To Other Documents

- `AGENT_WORKFLOW_STORY.md` explains the architecture and rationale of the multi-agent workflow itself.
- `MCP_SERVERS_AND_TOOLS.md` explains the repository-specific MCP surface that made agent work materially more effective.
- `SPECIFICATION_FIRST_APPROACH.md` explains why source-of-truth contracts mattered so much during agent-assisted work.

This document complements those by focusing on the practical engineering role the agent played inside the project.

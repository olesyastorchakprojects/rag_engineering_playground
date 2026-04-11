# Multi-Agent System

## Purpose

This document defines the recommended multi-agent workflow for this repository.

Use it when one task benefits from splitting responsibilities across:

- code writing
- spec conformance checking
- code review
- test writing
- coverage and gap analysis

This project is specification-first and already has strong MCP support.
Therefore the multi-agent system should be built around existing repository truth sources rather than around free-form agent judgment.

Primary truth sources:

- `Project Context MCP` for operational topology and ownership
- `Spec MCP` for source-of-truth documents
- `Spec Conformance MCP` for curated spec/code drift
- `Postgres MCP` for live eval storage truth
- `Observability MCP` for dashboards, provisioning, and runtime telemetry surfaces
- `Eval Experiments MCP` for run-oriented eval analysis

## Recommended Layout

Role prompts live in:

- `Specification/tasks/multi_agent/`

Use these files as the stable role definitions:

- `coordinator.md`
- `code_writer_agent.md`
- `spec_conformance_agent.md`
- `code_review_agent.md`
- `test_writer_agent.md`
- `coverage_gaps_agent.md`

## Roles

`Code Writer Agent`

- owns implementation changes
- reads spec and neighboring code before editing
- must not self-certify spec conformance or review quality as final authority

`Spec Conformance Agent`

- compares code against spec
- decides whether to update code, spec, or curated MCP metadata
- should use `Spec Conformance MCP` first when possible

`Code Review Agent`

- reviews behavior, architecture, risk, clarity, style consistency, and maintenance risk
- should focus on findings, not implementation

`Test Writer Agent`

- writes or updates tests based on the spec and the actual implementation change
- should use spec test contracts before inventing new testing behavior

`Coverage & Gaps Agent`

- maps implemented behavior to tests and uncovered spec requirements
- should separate "covered", "partially covered", and "not covered"

## Recommended Pipelines

### Feature Or Change

1. `Code Writer Agent`
2. `Test Writer Agent`
3. `Spec Conformance Agent`
4. `Code Review Agent`
5. `Coverage & Gaps Agent`

### Review Only

1. `Spec Conformance Agent`
2. `Code Review Agent`
3. `Coverage & Gaps Agent`

### Spec-Driven Build

1. `Spec Conformance Agent` on baseline
2. `Code Writer Agent`
3. `Test Writer Agent`
4. `Spec Conformance Agent` again
5. `Code Review Agent`
6. `Coverage & Gaps Agent`

## Project-Specific Recommendations

For `rag_runtime` work:

- always involve `Spec MCP` and `Spec Conformance MCP`
- include `Observability MCP` when spans, metrics, dashboards, or Grafana assets change
- include `Postgres MCP` when request-capture or eval-facing storage contracts change

For `eval_engine` work:

- use `Spec MCP`, `Project Context MCP`, `Postgres MCP`, and `Eval Experiments MCP`
- explicitly distinguish `request_summaries` from `request_run_summaries`
- distinguish live eval dashboards from run comparison dashboards

For ingest and retrieval work:

- use `Spec MCP`, `Project Context MCP`, and `Qdrant MCP`
- prefer contract checking over ad hoc payload assumptions

## Handoff Contract

Every agent should return:

- `scope`
- `inputs consulted`
- `changes made` or `findings`
- `open risks`
- `recommended next agent`

When code is changed, also return:

- changed file paths
- commands run
- unverified assumptions

## Anti-Patterns

Do not let one role silently absorb another.

Avoid:

- `Code Writer Agent` acting as the final reviewer
- `Test Writer Agent` deciding spec intent without reading spec
- `Coverage & Gaps Agent` claiming conformance without `Spec Conformance MCP`
- `Code Review Agent` making large code edits instead of reporting findings

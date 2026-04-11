# Agent Workflow Policy

## Purpose

This file is the source of truth for:

- multi-agent role definitions;
- default sequencing for spec-first implementation work;
- non-takeover rules for the coordinator;
- escalation rules when a sub-agent stalls or returns partial results.

Use this document together with:

- `AgentContext/multi_agent_playbook.md`
- `AgentContext/AGENTS.md`
- `AgentContext/multi_agent_system.md`

`AgentContext/` explains how to operate the system.
This file fixes the architectural policy that agent workflows must follow.

## Core Principle

When a task is explicitly chosen as a multi-agent workflow, the main agent acts as coordinator by default, not as the primary writer.

The coordinator may inspect outputs, verify progress, and reassign scope, but should not take over implementation prematurely.

## Agent Roles

### `Contract Sync Agent`

Purpose:

- verify that specs, schemas, MCP truth layers, and conformance checks are aligned before implementation starts.

Expected outputs:

- ready / not-ready status;
- explicit blockers;
- list of stale or missing contracts.

This role is read-only.

### `Code Writer Agent`

Purpose:

- implement the feature in code within a clearly defined write scope.

Expected outputs:

- code changes only inside the assigned files or module slice;
- concise progress updates;
- exact blockers if implementation cannot continue.

This role does not own review, conformance, or runtime acceptance.

### `Test Writer Agent`

Purpose:

- write or repair executable tests for the new implementation;
- align test expectations with the current source of truth and public behavior.

Expected outputs:

- unit, integration, contract, or end-to-end test changes inside the assigned test scope;
- commands run and pass/fail status;
- exact blocker if tests cannot run because of environment limits.

This role does not modify production code unless explicitly reassigned.

### `Spec Conformance Agent`

Purpose:

- compare implementation and test outputs against the declared specs and conformance checks.

Expected outputs:

- only mismatches, drift, missing mappings, or unresolved spec obligations;
- explicit statement when no meaningful findings remain.

This role is read-only.
For spec-first tasks, this role is a mandatory gate.

### `Runtime Verification Agent`

Purpose:

- run acceptance checks against the live system or the closest valid runtime environment.

Expected outputs:

- commands executed;
- what was actually verified live;
- environment blockers such as missing services, sandbox socket restrictions, unavailable models, or missing credentials.

This role is read-only with respect to source files.

### `Code Review Agent`

Purpose:

- review behavioral risks, regressions, hidden coupling, and operational fragility after implementation exists.

Expected outputs:

- prioritized findings;
- residual risks;
- missing-test or missing-hardening observations.

This role is read-only.

### `Coverage & Gaps Agent`

Purpose:

- find untested branches, weak negative cases, and contract gaps after the main implementation cycle is green.

Expected outputs:

- missing coverage areas;
- weak assumptions in tests or specs;
- recommended next validation targets.

This role is optional and read-only.

## Default Sequences

### Implement A Change

Recommended order:

1. `Contract Sync Agent`
2. `Code Writer Agent`
3. `Test Writer Agent`
4. `Spec Conformance Agent`
5. `Code Review Agent`
6. `Runtime Verification Agent`
7. `Coverage & Gaps Agent` when needed

### Spec-First Implementation

Recommended order:

1. `Contract Sync Agent`
2. `Code Writer Agent`
3. `Test Writer Agent`
4. `Spec Conformance Agent`
5. repeat `Code Writer Agent` or `Test Writer Agent` only for concrete findings
6. `Code Review Agent`
7. `Runtime Verification Agent`
8. `Coverage & Gaps Agent` when needed

## Non-Takeover Rules

These rules are mandatory when a task is being run as a multi-agent workflow.

### 1. No Early Coordinator Takeover

The main agent must not take over implementation before at least one full agent cycle completes:

- `Code Writer Agent`
- `Test Writer Agent`
- `Spec Conformance Agent`

This prevents the coordinator from collapsing the workflow back into single-agent coding too early.

### 2. Partial Results Must Be Reused First

If a sub-agent returns a partial but useful result, the coordinator must first try one of:

- follow-up within the same role;
- narrower reassignment to the same role type;
- handoff to the next role using the partial result.

The coordinator should not immediately rewrite the work locally just because the result is incomplete.

### 3. Takeover Requires Explicit Escalation

If the coordinator does take over a role, it must first explicitly record:

- why the takeover is necessary;
- which role is being replaced;
- why follow-up or reassignment was insufficient.

Valid reasons include:

- the agent is stalled and no longer producing progress reports;
- the agent returned invalid or contradictory results after follow-up;
- the task is blocked on a critical-path defect that cannot be advanced by reassignment.

### 4. Runtime Verification Stays With Runtime Verification

If `Runtime Verification Agent` is planned, the coordinator should not silently replace it with manual acceptance work.

Exception:

- environment access is blocked and the coordinator must perform a minimal equivalent verification step.

When this exception is used, the coordinator should say so explicitly.

### 5. Spec Conformance Is Mandatory For Spec-First Work

For spec-first tasks, implementation is not complete until `Spec Conformance Agent` reports no meaningful drift or returns only consciously accepted residual risk.

### 6. The Coordinator May Verify Facts, Not Rewrite The Workflow

The coordinator may:

- confirm that a claimed file really exists;
- rerun a failing test to capture the exact error;
- inspect artifacts to localize a mismatch;
- check whether a blocker is environment-related.

These verification actions do not count as implementation takeover by themselves.

They are allowed when used to keep the workflow disciplined.

## Progress Reporting Rules

Long-running agents should not stay silent.

At minimum, agents assigned code or tests should report using a compact protocol such as:

- `STATUS: <current stage>`
- `BLOCKER: <exact blocker>`
- `DONE: <what changed>`
- `FILES: <changed files>`

The coordinator should request these short updates whenever a role is running long enough that lack of signal would make orchestration ambiguous.

## Practical Heuristics

- Use explorers or read-only agents first when the implementation task is large and still ambiguous.
- Give the `Code Writer Agent` a narrow write scope and an explicit implementation map whenever possible.
- Use `Test Writer Agent` for targeted repair loops rather than asking one agent to generate and debug an entire test layer at once.
- Treat environment blockers separately from logic blockers.
- Prefer one concrete failing trace over broad speculation when handing work back to a writer or test-writer.

## What Worked In Practice

For this repository, the most reliable pattern has been:

1. small read-only decomposition by focused agents;
2. one narrow `Code Writer Agent`;
3. one narrow `Test Writer Agent`;
4. mandatory `Spec Conformance Agent`;
5. read-only review and runtime verification after the first green cycle.

This pattern is preferred over assigning one large undivided task to a single writer.

## Repository-Proven Orchestration Pattern

This repository has already validated the following orchestration pattern in practice:

1. start with small read-only agents to reduce ambiguity and map the implementation surface;
2. assign one narrow `Code Writer Agent` with a strict write scope;
3. assign one narrow `Test Writer Agent` after the first implementation pass exists;
4. require a full `writer -> tests -> conformance` cycle before any coordinator takeover is considered;
5. run `Code Review Agent` and `Runtime Verification Agent` only after that first green cycle;
6. use coordinator takeover only for explicit blocker resolution, never as the default mode.

This pattern should be treated as the default multi-agent implementation workflow unless a task has a documented reason to require a different sequence.

## When A Delta Spec Is Ready For Sub-Agents

A delta spec is usually ready for sub-agent implementation when all of the following are true:

- a concrete baseline is named explicitly;
- unchanged inherited behavior is listed explicitly;
- delta-only additions are listed explicitly;
- delta-only overrides are listed explicitly;
- important terminology is fixed in contracts rather than left implicit;
- config and schema contracts already exist for the delta surface;
- test expectations or a test matrix already describe the intended behavior;
- conformance checks exist or the expected conformance gate is defined;
- the implementation target is concrete, for example one named file or one narrow module slice;
- the writer is not expected to invent new architecture while implementing the delta.

A delta spec is not yet ready for sub-agent implementation when one or more of the following are true:

- the baseline is only implied and not named directly;
- the real source of truth is spread across files with no clear inheritance rule;
- unresolved architectural choices still remain in the spec;
- runtime behavior has been agreed verbally but not written down;
- tests do not yet express the intended external behavior;
- the writer would have to decide system shape rather than implement an agreed shape.

For code generation, the most reliable framing is:

1. identify the baseline implementation to copy or mirror;
2. identify the delta source of truth;
3. identify the contracts and schemas that constrain the delta;
4. identify the executable tests and conformance gate;
5. assign a narrow write scope.

When this framing is present, delta-spec implementation is usually a good fit for sub-agents.

# Agent Workflow Story

## Why There Is An Agent Workflow At All

The repository includes an explicit multi-agent workflow because the project is
large enough that ad hoc task execution becomes expensive and fragile.

The goal is not to add automation for its own sake.
The goal is to make engineering work more disciplined in a repository that
combines:

- runtime code
- contracts
- schemas
- dashboards
- eval storage
- run artifacts

In this kind of system, single-pass coding is often not enough.

## Core Idea

The multi-agent workflow treats different forms of engineering work as distinct
roles rather than collapsing everything into one undifferentiated assistant.

The repository explicitly models roles such as:

- contract sync
- code writing
- test writing
- spec conformance
- code review
- runtime verification
- coverage and gap finding

This reflects the belief that different tasks have different failure modes and
deserve different kinds of scrutiny.

## Control Plane And Execution Split

The workflow is intentionally split into two layers:

- the orchestrator MCP under `Tools/mcp/agent_orchestrator/`
- the external runner under `Execution/orchestration/`

This split matters.

The orchestrator owns:

- workflow state
- routing rules
- completion rules
- step transitions

The external runner owns:

- operational invocation
- status inspection
- result submission
- resume and retry flows

This keeps policy separate from execution.

## Why This Fits The Repository

The repository already has a specification-first structure.
That makes it especially compatible with multi-agent workflows because:

- there are explicit contracts to consult before coding
- there are clear ownership boundaries between subsystems
- there are real conformance questions to answer after implementation
- there are observable runtime and storage surfaces to verify against

The workflow is not floating above the repository.
It is anchored in the repository's structure.

## Default Workflow Shape

The preferred workflow is not “one writer does everything.”

The validated pattern is closer to:

1. reduce ambiguity through context and contract inspection
2. assign a narrow implementation scope
3. add or repair tests
4. run conformance checks
5. review behavior and residual risks
6. verify runtime behavior against the live system when needed

This pattern works especially well in a project where contracts and measured
behavior matter as much as implementation details.

## Why The Coordinator Does Not Immediately Take Over

One of the strongest design choices in the workflow policy is that the
coordinator should not collapse back into doing all implementation work
immediately.

That rule exists to prevent:

- premature takeover
- loss of separation between roles
- shallow verification loops
- reversion to improvised single-agent coding on complex tasks

The coordinator is meant to preserve structure, not erase it.

## Why Spec Conformance Matters In The Workflow

Spec conformance is a mandatory gate for spec-first work.

This is one of the most important ideas in the workflow model because it keeps
the system honest when code, schemas, docs, and dashboards evolve together.

Without a conformance pass, it is too easy for a change to look locally correct
while still drifting from:

- contracts
- storage expectations
- generated artifacts
- observability assumptions

## Runtime Verification As A Separate Role

The workflow also distinguishes runtime verification from code writing.

This matters because a project like this can fail in ways that are only visible
in a live or semi-live environment:

- backend health mismatches
- provider behavior changes
- trace or metric gaps
- storage integration issues

Separating runtime verification from writing keeps acceptance work explicit.

## Why This Is Worth Highlighting

The agent workflow shows that the project is not only a technical system, but
also an operational engineering environment.

It encodes a point of view:

- design should be explicit
- roles should be legible
- conformance should be checked
- runtime behavior should be verified

That is a strong story for presentation because it shows that the repository is
thinking not only about software architecture, but also about engineering
process.

## What This Enables

The workflow architecture helps the team:

- reduce ambiguity before implementation
- keep specs and code aligned
- avoid large unstructured changes
- recover more cleanly from partial progress or failed steps
- preserve review and conformance discipline as the project grows

In practice, it complements the rest of the repository's design very well.

The runtime, specs, measurement layer, evidence layer, and agent workflow all
push in the same direction:
make engineering work explicit, inspectable, and reproducible.

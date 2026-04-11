# Multi-Agent Playbook

## Purpose

This playbook explains how to use the repository multi-agent system for common task types.

Use together with:

- `AgentContext/AGENTS.md`
- `AgentContext/multi_agent_system.md`
- `Specification/architecture/agent_workflow_policy.md`
- `Specification/tasks/multi_agent/`
- `Specification/tasks/multi_agent/launchers.md`
- `Specification/tasks/multi_agent/handoff_packet.md`
- `Specification/tasks/multi_agent/launcher_examples.md`

Role definitions, sequencing policy, and coordinator non-takeover rules are fixed in:

- `Specification/architecture/agent_workflow_policy.md`

## Default Task Modes

### 1. Implement A Change

Use when a task requires code edits.

Recommended order:

1. coordinator
2. code writer
3. test writer
4. spec conformance
5. code review
6. coverage and gaps

Best for:

- `rag_runtime` feature work
- `eval_engine` behavior changes
- MCP server enhancements

### 2. Review A Change

Use when code already exists and you want quality signals.

Recommended order:

1. coordinator
2. spec conformance
3. code review
4. coverage and gaps

Best for:

- pull request review
- local diff review
- pre-merge validation

### 3. Spec-Driven Implementation

Use when the task starts from spec rather than from code.

Recommended order:

1. coordinator
2. spec conformance on current baseline
3. code writer
4. test writer
5. spec conformance again
6. code review
7. coverage and gaps

## Project-Specific Playbooks

### `rag_runtime`

Always consult:

- `Spec MCP`
- `Spec Conformance MCP`
- `Project Context MCP`

Also consult when relevant:

- `Observability MCP`
- `Postgres MCP`

Use this when changing:

- request flow
- token counting
- observability spans or metrics
- Grafana assets under `Measurement/observability`
- request capture storage behavior

### `eval_engine`

Always consult:

- `Spec MCP`
- `Project Context MCP`
- `Postgres MCP`
- `Eval Experiments MCP`

Use this when changing:

- summary building
- run artifacts
- `request_summaries`
- `request_run_summaries`
- live eval dashboards
- run comparison dashboards

### MCP Servers

Use:

- `Code Writer Agent` for server changes
- `Test Writer Agent` for MCP unit tests
- `Code Review Agent` for payload shape, routing, and stale-truth risk
- `Coverage & Gaps Agent` for curated blind spots

Pay special attention to:

- stale path catalogs
- stale known-table lists
- stale dashboard inventories
- stale storage ownership or routing guidance

## Parallelization Guidance

Safe to run in parallel:

- `Test Writer Agent` with `Code Review Agent` after code changes stabilize
- `Spec Conformance Agent` with `Code Review Agent` when both are read-only
- `Coverage & Gaps Agent` with `Code Review Agent`

Keep sequential:

- `Code Writer Agent` before other agents that depend on final changed files
- `Spec Conformance Agent` after spec or code edits if drift status is the gate

## Suggested Handoff Packet

When one agent finishes, pass this packet forward:

- `task`
- `module`
- `changed_files`
- `spec_docs_used`
- `commands_run`
- `known_limitations`
- `open_risks`

## Minimum Viable Usage

If you want the lightest possible setup, use only:

1. coordinator
2. code writer
3. spec conformance
4. code review

Add `test writer` and `coverage and gaps` whenever the task changes behavior rather than only documentation or wiring.

## Fast Start

If you do not want to compose prompts manually:

1. open `Specification/tasks/multi_agent/launchers.md`
2. copy the `Coordinator Launcher`
3. fill in task, module, and constraints
4. run the next launcher from the returned pipeline
5. pass state forward with `Specification/tasks/multi_agent/handoff_packet.md`

If you want a concrete starting point instead of blank templates, adapt one of the examples in `Specification/tasks/multi_agent/launcher_examples.md`.

## External Runner

If you want to keep orchestration state in the MCP but use an external execution helper, use:

- `Execution/orchestration/agent_workflow_runner.py`

That runner is the recommended execution layer for the current architecture:

- `Tools/mcp/agent_orchestrator/` stays the control plane
- `Execution/orchestration/` stays the external runner layer

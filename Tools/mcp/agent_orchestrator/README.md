# Agent Orchestrator MCP

## Purpose

This directory contains the project-specific multi-agent orchestrator MCP.

It accepts one high-level task, builds a workflow, records state, and returns the next ready-to-run assignment for an external agent runner.

The server is policy-first and stateful:

- it plans the workflow from task scope and changed paths
- it persists workflow state under `Tools/mcp/agent_orchestrator/state/`
- it produces structured prompts and step results
- it can loop back when review, conformance, or test findings require another pass

The server does not spawn specialist agents on its own.
It is designed to work with `Execution/orchestration/agent_workflow_runner.py`.

## Why This Exists

This repository already has strong truth sources:

- `Project Context MCP`
- `Spec MCP`
- `Spec Conformance MCP`
- `Postgres MCP`
- `Observability MCP`
- `Qdrant MCP`
- `Eval Experiments MCP`

The orchestrator should not replace those sources.
It coordinates specialist agents around them.

Default agent execution profile:

- model: `gpt-5.4-mini`
- reasoning effort: `medium`

## Tool Surface

- `get_workflow_schema()`
- `get_agent_result_schema()`
- `get_decision_rules()`
- `get_completion_policy()`
- `plan_task(...)`
- `start_workflow(...)`
- `run_workflow(task_id)`
- `submit_step_result(...)`
- `submit_and_continue(...)`
- `get_workflow_status(task_id)`
- `get_workflow_report(task_id)`
- `explain_decision(task_id)`
- `resume_workflow(task_id)`
- `cancel_workflow(task_id, reason=None)`
- `retry_step(task_id, step_id)`
- `list_workflow_artifacts(task_id)`

## When To Use It

Use this server when one user request needs coordinated work across multiple specialist roles.

Good examples:

- "plan and route this spec-sensitive change"
- "run the workflow for this review task"
- "show me the current workflow status"
- "explain why the orchestrator chose these MCPs"
- "continue after a test or review finding"

The workflow is intentionally explicit:

1. classify the task
2. choose the smallest useful pipeline
3. infer the required MCPs from scope and changed areas
4. hand back the next assignment
5. accept structured results
6. loop when follow-up fixes are needed

## Directory Layout

- `schemas/`
  Machine-readable state and result schemas.
- `policies/`
  Project-specific routing and completion rules.
- `routing_policy.md`
  Human-readable guidance for when this MCP should be called.

## State Model

See:

- `schemas/workflow_state.schema.json`
- `schemas/agent_result.schema.json`

The orchestrator treats every agent run as a typed step result rather than as unstructured prose.

## Project-Specific Routing

The orchestrator must be aware of repository-specific semantics, especially:

- `rag_runtime` spec-first workflow
- `hybrid_ingest` sparse vocabulary, BM25 term stats, and hybrid Qdrant payloads
- `run_stack.py` launcher inputs, resolved configs, and provider choices
- `eval_engine` run-vs-live semantics
- `request_summaries` vs `request_run_summaries`
- observability assets under `Measurement/observability`
- eval dashboard assets under `Measurement/evals`
- multi-agent launcher templates under `Specification/tasks/multi_agent`
- stale curated truth risk in `Tools/mcp/*`

See:

- `policies/decision_rules.yaml`
- `policies/completion_policy.yaml`

## Testing

Scenario coverage lives in:

- `tests/test_server.py`

The current tests validate:

- module and MCP inference
- assignment prompt generation
- start and continue workflow helpers
- pipeline expansion after review findings
- step retry behavior
- workflow decision explanations

## Local Run

```bash
./.venv/bin/python Tools/mcp/agent_orchestrator/server.py
```

## Non-Goals

- replacing the existing MCP truth sources
- free-form autonomous architecture redesign
- broad repository-wide planning without module scope
- mutating the local Codex config automatically

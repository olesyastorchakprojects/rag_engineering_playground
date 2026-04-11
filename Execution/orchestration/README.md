# Agent Workflow Runner

## Purpose

This module is the external execution layer for the repository multi-agent workflow.

It uses `Tools/mcp/agent_orchestrator/server.py` as the control plane and provides a thin CLI for:

- starting a workflow
- getting status
- explaining the current routing decision
- resuming the next step
- submitting one step result
- submitting and immediately continuing
- retrying a step
- listing workflow artifacts

## Why This Exists

The orchestrator MCP is the workflow brain.
This runner is the execution-side helper.

That split keeps:

- policy and state in `Tools/mcp/agent_orchestrator/`
- operational usage in `Execution/orchestration/`

## Usage

Start a workflow:

```bash
./.venv/bin/python -m Execution.orchestration.agent_workflow_runner start \
  --task "add a query token metric to rag_runtime observability" \
  --mode implement-change \
  --changed-path Execution/rag_runtime/src/input_validation/mod.rs \
  --changed-path Measurement/observability/grafana/dashboards/rag_runtime.json
```

Explain the next step:

```bash
./.venv/bin/python -m Execution.orchestration.agent_workflow_runner explain \
  --task-id <task_id>
```

Submit one step result and continue:

```bash
./.venv/bin/python -m Execution.orchestration.agent_workflow_runner submit-and-continue \
  --task-id <task_id> \
  --result-json /tmp/step_result.json
```

## Result JSON Format

The result file should match the fields accepted by:

- `submit_step_result`
- `submit_and_continue`

Minimum required fields:

- `step_id`
- `agent`
- `status`
- `summary`
- `recommended_next_agent`

Optional fields:

- `findings`
- `files_changed`
- `tests_changed`
- `spec_inputs_used`
- `mcps_consulted`
- `commands_run`
- `code_updates_needed`
- `spec_updates_needed`
- `mcp_updates_needed`
- `open_risks`
- `blocking_reason`

## Notes

- The runner does not implement automatic Codex sub-agent spawning.
- It is intentionally a thin wrapper around the orchestrator MCP server logic.
- This is the recommended external runner for the current "control plane + external execution" architecture.

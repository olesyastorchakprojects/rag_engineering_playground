# Multi-Agent Launchers

Use this file as the copy-paste entrypoint for the multi-agent workflow.

Replace placeholders before sending a prompt.

## Default Flow

1. run `Coordinator`
2. run the next specialist agent from the returned pipeline
3. pass `handoff_packet.md` fields forward
4. stop when the pipeline is complete

## Coordinator Launcher

```text
Use Specification/tasks/multi_agent/coordinator.md as your role instruction.

Task: <describe the task>
Mode: <implement-change | review-change | spec-driven>
Module or subsystem: <target module>
Relevant files: <known files or "unknown yet">
Desired outcome: <what success looks like>
Constraints: <optional constraints>

Repository context requirements:
- Consult Project Context MCP first.
- Consult Spec MCP for source-of-truth docs.
- Consult Spec Conformance MCP if drift is possible.
- Add runtime-truth MCPs only when needed.

Return:
- the smallest useful agent pipeline
- per-agent inputs
- required MCPs
- execution order
- what can run in parallel
- required handoff contents
```

## Code Writer Launcher

```text
Use Specification/tasks/multi_agent/code_writer_agent.md as your role instruction.

Task: <implementation task>
Module or subsystem: <target module>
Write scope: <files or directories the agent may edit>
Spec topic: <spec topic name>
Required MCPs:
- Project Context MCP
- Spec MCP
- <other MCPs if needed>

Constraints:
- make minimal complete changes
- stay within write scope
- run the smallest meaningful verification

Return:
- summary
- files_changed
- spec_inputs_used
- commands_run
- assumptions
- open_risks
- recommended_next_agent
```

## Test Writer Launcher

```text
Use Specification/tasks/multi_agent/test_writer_agent.md as your role instruction.

Task: <test task>
Module or subsystem: <target module>
Changed implementation files:
- <file 1>
- <file 2>
Spec topic: <spec topic name>
Required MCPs:
- Spec MCP
- <other MCPs if needed>

Constraints:
- align tests to spec intent
- preserve existing local test style
- cover success path, edge cases, and failure modes relevant to the change

Return:
- tests_added_or_changed
- behaviors_locked
- commands_run
- untested_areas
- recommended_next_agent
```

## Spec Conformance Launcher

```text
Use Specification/tasks/multi_agent/spec_conformance_agent.md as your role instruction.

Task: verify spec conformance for the current change.
Module or subsystem: <target module>
Changed files:
- <file 1>
- <file 2>
Spec topic: <spec topic name>
Required MCPs:
- Spec Conformance MCP
- Spec MCP
- Project Context MCP

Return:
- status
- findings
- code_updates_needed
- spec_updates_needed
- mcp_updates_needed
- evidence
- recommended_next_agent
```

## Code Review Launcher

```text
Use Specification/tasks/multi_agent/code_review_agent.md as your role instruction.

Task: review the current change.
Module or subsystem: <target module>
Changed files or diff:
- <file 1>
- <file 2>
Spec topic: <spec topic name>
Required MCPs:
- Spec MCP
- Project Context MCP
- <other MCPs if risk depends on runtime truth>

Review focus:
- correctness
- architecture
- logic
- style consistency
- observability risk
- storage risk

Return:
- findings
- residual_risks
- questions
- recommended_next_agent
```

## Coverage & Gaps Launcher

```text
Use Specification/tasks/multi_agent/coverage_gaps_agent.md as your role instruction.

Task: assess test coverage and remaining gaps for the change.
Module or subsystem: <target module>
Changed implementation files:
- <file 1>
- <file 2>
Changed test files:
- <test file 1>
- <test file 2>
Spec topic: <spec topic name>
Required MCPs:
- Spec Conformance MCP
- Spec MCP
- <coverage outputs if available>

Return:
- coverage_map
- partial_coverage
- uncovered_gaps
- suggested_next_tests
- recommended_next_agent
```

## Project-Specific Quick Starts

### `rag_runtime` Change

Use:

- `Coordinator`
- `Code Writer`
- `Test Writer`
- `Spec Conformance`
- `Code Review`

Usually required MCPs:

- `Project Context MCP`
- `Spec MCP`
- `Spec Conformance MCP`
- `Observability MCP` when metrics, traces, or dashboards change
- `Postgres MCP` when request capture or eval-facing tables matter

### `eval_engine` Change

Use:

- `Coordinator`
- `Code Writer`
- `Test Writer`
- `Spec Conformance`
- `Code Review`
- `Coverage & Gaps`

Usually required MCPs:

- `Project Context MCP`
- `Spec MCP`
- `Postgres MCP`
- `Eval Experiments MCP`
- `Observability MCP` when dashboard or telemetry semantics change

Be explicit about:

- `request_summaries`
- `request_run_summaries`
- live dashboard semantics
- run dashboard semantics

### MCP Server Change

Use:

- `Coordinator`
- `Code Writer`
- `Test Writer`
- `Code Review`
- `Coverage & Gaps`

Usually required MCPs:

- `Project Context MCP`
- `Spec MCP`
- the target MCP itself when it is a read-capable truth source

Ask reviewers to inspect:

- stale curated lists
- stale path catalogs
- stale dashboard inventories
- stale ownership guidance
```


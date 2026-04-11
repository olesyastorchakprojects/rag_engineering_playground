# Launcher Examples

Use these examples as ready-to-adapt starting points for common repository workflows.

Pair with:

- `Specification/tasks/multi_agent/launchers.md`
- `Specification/tasks/multi_agent/handoff_packet.md`
- `AgentContext/multi_agent_playbook.md`

## Example 1: `rag_runtime` Metric Change

### Coordinator

```text
Use Specification/tasks/multi_agent/coordinator.md as your role instruction.

Task: add a new metric for input query token count in rag_runtime and update related observability assets.
Mode: implement-change
Module or subsystem: rag_runtime
Relevant files:
- Execution/rag_runtime/src/input_validation/mod.rs
- Execution/rag_runtime/src/observability/mod.rs
- Measurement/observability
- Specification/codegen/rag_runtime/observability
Desired outcome: implementation, tests, spec conformance check, and review of observability risk.
Constraints:
- preserve current metric naming conventions
- update spec only if the code change introduces new documented behavior

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

### Code Writer

```text
Use Specification/tasks/multi_agent/code_writer_agent.md as your role instruction.

Task: add a metric for input query token count in rag_runtime and wire it into the observability flow.
Module or subsystem: rag_runtime
Write scope:
- Execution/rag_runtime/src/input_validation/mod.rs
- Execution/rag_runtime/src/observability/mod.rs
- Measurement/observability
Spec topic: rag_runtime observability
Required MCPs:
- Project Context MCP
- Spec MCP
- Observability MCP

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

### Spec Conformance

```text
Use Specification/tasks/multi_agent/spec_conformance_agent.md as your role instruction.

Task: verify spec conformance for the current change.
Module or subsystem: rag_runtime
Changed files:
- Execution/rag_runtime/src/input_validation/mod.rs
- Execution/rag_runtime/src/observability/mod.rs
- Measurement/observability/<dashboard or provisioning file>
- Specification/codegen/rag_runtime/observability/<doc>
Spec topic: rag_runtime observability
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

## Example 2: `eval_engine` Run Summary Work

### Coordinator

```text
Use Specification/tasks/multi_agent/coordinator.md as your role instruction.

Task: update eval_engine to support a new run-based summary behavior and keep dashboards aligned.
Mode: implement-change
Module or subsystem: eval_engine
Relevant files:
- Execution/docker/postgres/init/006_request_run_summaries.sql
- Execution/evals
- Measurement/evals
- Tools/mcp/postgres
- Tools/mcp/eval_experiments
Desired outcome: code and SQL updates, tests, conformance review, and validation of live vs run semantics.
Constraints:
- preserve the distinction between request_summaries and request_run_summaries
- preserve the distinction between live and run dashboards

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

### Code Review

```text
Use Specification/tasks/multi_agent/code_review_agent.md as your role instruction.

Task: review the current change.
Module or subsystem: eval_engine
Changed files or diff:
- Execution/docker/postgres/init/006_request_run_summaries.sql
- Execution/evals/<changed files>
- Measurement/evals/<changed dashboard files>
- Tools/mcp/postgres/<changed files>
- Tools/mcp/eval_experiments/<changed files>
Spec topic: eval_engine summaries and eval observability
Required MCPs:
- Spec MCP
- Project Context MCP
- Postgres MCP
- Eval Experiments MCP
- Observability MCP

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

### Coverage & Gaps

```text
Use Specification/tasks/multi_agent/coverage_gaps_agent.md as your role instruction.

Task: assess test coverage and remaining gaps for the eval_engine run-summary change.
Module or subsystem: eval_engine
Changed implementation files:
- Execution/evals/<changed files>
- Execution/docker/postgres/init/006_request_run_summaries.sql
Changed test files:
- <changed test files>
Spec topic: eval_engine summaries and eval observability
Required MCPs:
- Spec Conformance MCP
- Spec MCP
- Eval Experiments MCP

Return:
- coverage_map
- partial_coverage
- uncovered_gaps
- suggested_next_tests
- recommended_next_agent
```

## Example 3: Review-Only For Existing Diff

### Coordinator

```text
Use Specification/tasks/multi_agent/coordinator.md as your role instruction.

Task: review an existing local diff before merge.
Mode: review-change
Module or subsystem: rag_runtime
Relevant files: unknown yet, use the current diff as input
Desired outcome: conformance verdict, review findings, and remaining coverage gaps.
Constraints:
- do not make code changes unless a reviewer explicitly recommends a fix

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

### Spec Conformance

```text
Use Specification/tasks/multi_agent/spec_conformance_agent.md as your role instruction.

Task: verify spec conformance for the current diff.
Module or subsystem: rag_runtime
Changed files:
- <files from current diff>
Spec topic: rag_runtime
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

### Code Review

```text
Use Specification/tasks/multi_agent/code_review_agent.md as your role instruction.

Task: review the current diff.
Module or subsystem: rag_runtime
Changed files or diff:
- <files from current diff>
Spec topic: rag_runtime
Required MCPs:
- Spec MCP
- Project Context MCP
- Observability MCP when metrics or dashboards are touched
- Postgres MCP when storage-facing behavior is touched

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

## Example 4: MCP Server Update

### Coordinator

```text
Use Specification/tasks/multi_agent/coordinator.md as your role instruction.

Task: update an MCP server after repository truth changed and the server metadata is stale.
Mode: implement-change
Module or subsystem: MCP server
Relevant files:
- Tools/mcp/<target_server>
- AgentContext
- Specification
- Measurement or Execution paths referenced by the server
Desired outcome: server updates, tests, review of stale-truth risk, and identified remaining blind spots.
Constraints:
- keep changes minimal
- prefer updating curated truth rather than broadening scope

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

### Code Writer

```text
Use Specification/tasks/multi_agent/code_writer_agent.md as your role instruction.

Task: update the target MCP server so its catalogs, curated lists, and guidance match the repository truth.
Module or subsystem: target MCP server
Write scope:
- Tools/mcp/<target_server>
- related README or routing files
Spec topic: target subsystem and MCP guidance
Required MCPs:
- Project Context MCP
- Spec MCP
- <target MCP if it exposes read-only truth>

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

### Test Writer

```text
Use Specification/tasks/multi_agent/test_writer_agent.md as your role instruction.

Task: add or update MCP tests for the metadata refresh.
Module or subsystem: target MCP server
Changed implementation files:
- Tools/mcp/<target_server>/<changed files>
Spec topic: target subsystem and MCP guidance
Required MCPs:
- Spec MCP

Constraints:
- align tests to spec intent
- preserve existing local test style
- cover stale-truth regressions relevant to the change

Return:
- tests_added_or_changed
- behaviors_locked
- commands_run
- untested_areas
- recommended_next_agent
```

## Example 5: Handoff Between Agents

```text
task: add a new query token metric and expose it through rag_runtime observability
mode: implement-change
module: rag_runtime

changed_files:
- Execution/rag_runtime/src/input_validation/mod.rs
- Execution/rag_runtime/src/observability/mod.rs
- Measurement/observability/grafana/dashboards/rag_runtime.json

changed_test_files:
- Execution/rag_runtime/tests/observability_metric_tests.rs

spec_docs_used:
- Specification/codegen/rag_runtime/observability/implementation.md
- Specification/codegen/rag_runtime/input_validation.md

mcps_consulted:
- Project Context MCP
- Spec MCP
- Observability MCP

commands_run:
- cargo test -p rag_runtime observability_metric

findings:
- metric naming follows current conventions
- dashboard wiring updated, but spec confirmation still needed

known_limitations:
- did not verify live Grafana rendering

open_risks:
- metric may need spec wording update if naming is considered public contract

recommended_next_agent: Spec Conformance Agent
```

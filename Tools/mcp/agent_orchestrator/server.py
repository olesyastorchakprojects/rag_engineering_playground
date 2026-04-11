from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

import yaml
try:
    from fastmcp import FastMCP
except ModuleNotFoundError:  # pragma: no cover - local fallback for schema/policy testing
    class FastMCP:  # type: ignore[override]
        def __init__(self, name: str) -> None:
            self.name = name

        def tool(self, fn: Any) -> Any:
            return fn

        def run(self) -> None:
            raise ModuleNotFoundError("fastmcp is required to run the MCP server")

ROOT = Path(__file__).resolve().parent
SCHEMAS_ROOT = ROOT / "schemas"
POLICIES_ROOT = ROOT / "policies"
STATE_ROOT = ROOT / "state"

WORKFLOW_SCHEMA_PATH = SCHEMAS_ROOT / "workflow_state.schema.json"
AGENT_RESULT_SCHEMA_PATH = SCHEMAS_ROOT / "agent_result.schema.json"
DECISION_RULES_PATH = POLICIES_ROOT / "decision_rules.yaml"
COMPLETION_POLICY_PATH = POLICIES_ROOT / "completion_policy.yaml"

KNOWN_AGENTS = {
    "Coordinator",
    "Code Writer Agent",
    "Test Writer Agent",
    "Spec Conformance Agent",
    "Code Review Agent",
    "Coverage & Gaps Agent",
}

KNOWN_MCPS = [
    "Project Context MCP",
    "Spec MCP",
    "Spec Conformance MCP",
    "Postgres MCP",
    "Observability MCP",
    "Qdrant MCP",
    "Eval Experiments MCP",
]

AGENT_PROMPT_FILES = {
    "Coordinator": "Specification/tasks/multi_agent/coordinator.md",
    "Code Writer Agent": "Specification/tasks/multi_agent/code_writer_agent.md",
    "Test Writer Agent": "Specification/tasks/multi_agent/test_writer_agent.md",
    "Spec Conformance Agent": "Specification/tasks/multi_agent/spec_conformance_agent.md",
    "Code Review Agent": "Specification/tasks/multi_agent/code_review_agent.md",
    "Coverage & Gaps Agent": "Specification/tasks/multi_agent/coverage_gaps_agent.md",
}

mcp = FastMCP("agent-orchestrator")


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must contain a top-level mapping")
    return data


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must contain a top-level object")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _decision_rules() -> dict[str, Any]:
    return _read_yaml(DECISION_RULES_PATH)


def _completion_policy() -> dict[str, Any]:
    return _read_yaml(COMPLETION_POLICY_PATH)


def _workflow_schema() -> dict[str, Any]:
    return _read_json(WORKFLOW_SCHEMA_PATH)


def _agent_result_schema() -> dict[str, Any]:
    return _read_json(AGENT_RESULT_SCHEMA_PATH)


def _workflow_state_path(task_id: str) -> Path:
    return STATE_ROOT / f"{task_id}.json"


def _load_workflow_state(task_id: str) -> dict[str, Any]:
    path = _workflow_state_path(task_id)
    if not path.exists():
        raise ValueError(f"Unknown workflow task_id: {task_id}")
    return _read_json(path)


def _save_workflow_state(state: dict[str, Any]) -> None:
    task_id = state.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise ValueError("workflow state must contain task_id")
    _write_json(_workflow_state_path(task_id), state)


def _normalize_mode(mode: str | None) -> str:
    if mode is None:
        return "implement-change"
    normalized = mode.strip().lower()
    if normalized not in {"implement-change", "review-change", "spec-driven"}:
        raise ValueError(f"Unsupported mode: {mode}")
    return normalized


def _normalize_paths(paths: list[str] | None) -> list[str]:
    if not paths:
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for path in paths:
        normalized = path.strip().lstrip("./")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
    return cleaned


def _guess_module(task: str, paths: list[str], module: str | None) -> str:
    if module and module.strip():
        return module.strip()

    joined = " ".join(paths).lower()
    task_lower = task.lower()

    if "execution/ingest/hybrid/" in joined or "hybrid ingest" in task_lower:
        return "hybrid_ingest"
    if "execution/bin/" in joined or "execution/orchestration/" in joined:
        return "run_stack_launcher"
    if "run_stack" in task_lower or "launcher" in task_lower:
        return "run_stack_launcher"
    if "tools/mcp/agent_orchestrator/" in joined or "agent orchestrator" in task_lower:
        return "agent_orchestrator"
    if "rag_runtime" in joined or "rag runtime" in task_lower:
        return "rag_runtime"
    if "execution/evals/" in joined or "measurement/evals/" in joined or "eval_engine" in task_lower:
        return "eval_engine"
    if "tools/mcp/" in joined or "mcp" in task_lower:
        return "mcp_server"
    if "measurement/observability/" in joined or "observability" in task_lower:
        return "observability"
    if "qdrant" in joined or "qdrant" in task_lower:
        return "retrieval"

    return "unknown"


def _infer_spec_topic(module: str, task: str, paths: list[str]) -> str | None:
    if module == "hybrid_ingest":
        return "hybrid_ingest"
    if module == "rag_runtime":
        if any("Specification/codegen/rag_runtime/observability/" in path for path in paths):
            return "rag_runtime_observability"
        return "rag_runtime"
    if module == "eval_engine":
        if any("Measurement/evals/" in path or "request_run_summaries" in path for path in paths):
            return "eval_observability"
        return "eval_engine"
    if module == "mcp_server":
        if "spec" in task.lower():
            return "spec"
        return None
    return None


def _collect_required_mcps(module: str, paths: list[str]) -> tuple[list[str], list[str]]:
    rules = _decision_rules()
    required: list[str] = []
    flags: list[str] = []

    def _add_mcp(name: str) -> None:
        if name in KNOWN_MCPS and name not in required:
            required.append(name)

    module_rules = rules.get("module_rules", {})
    module_entry = module_rules.get(module, {})
    for name in module_entry.get("add_mcps", []):
        _add_mcp(name)

    for path_rule in rules.get("path_rules", []):
        prefixes = path_rule.get("match_prefixes", [])
        if any(path.startswith(prefix) for prefix in prefixes for path in paths):
            for name in path_rule.get("add_mcps", []):
                _add_mcp(name)
            for flag in path_rule.get("flags", []):
                if flag not in flags:
                    flags.append(flag)

    if not required:
        for name in ["Project Context MCP", "Spec MCP"]:
            _add_mcp(name)

    return required, flags


def _pipeline_for_mode(mode: str) -> list[str]:
    rules = _decision_rules()
    task_modes = rules.get("task_mode_rules", {})
    entry = task_modes.get(mode, {})
    pipeline = entry.get("default_pipeline", [])
    if not isinstance(pipeline, list) or not pipeline:
        raise ValueError(f"No default pipeline configured for mode: {mode}")
    for name in pipeline:
        if name not in KNOWN_AGENTS:
            raise ValueError(f"Unknown agent in pipeline: {name}")
    return pipeline


def _parallelizable_after(agent: str) -> list[str]:
    rules = _decision_rules()
    for entry in rules.get("parallelization_rules", []):
        if entry.get("after") == agent:
            return [name for name in entry.get("may_run_in_parallel", []) if name in KNOWN_AGENTS]
    return []


def _step_status(agent: str) -> str:
    return "completed" if agent == "Coordinator" else "pending"


def _build_pipeline(agent_names: list[str]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    previous_step_id: str | None = None
    for index, agent in enumerate(agent_names, start=1):
        step_id = f"step_{index}"
        blocking_dependencies = [previous_step_id] if previous_step_id else []
        can_run_in_parallel = False
        if previous_step_id and agent in _parallelizable_after(agent_names[index - 2]):
            can_run_in_parallel = True
        steps.append(
            {
                "step_id": step_id,
                "agent": agent,
                "status": _step_status(agent),
                "can_run_in_parallel": can_run_in_parallel,
                "blocking_dependencies": blocking_dependencies,
            }
        )
        previous_step_id = step_id
    return steps


def _agent_inputs(agent: str, module: str, spec_topic: str | None, required_mcps: list[str], paths: list[str]) -> dict[str, Any]:
    rules = _decision_rules()
    execution_defaults = rules.get("execution_defaults", {})
    execution_overrides = rules.get("agent_execution_overrides", {})
    execution_config = {
        "model": execution_defaults.get("model", "gpt-5.4-mini"),
        "reasoning_effort": execution_defaults.get("reasoning_effort", "medium"),
    }
    if isinstance(execution_overrides.get(agent), dict):
        execution_config.update(execution_overrides[agent])

    shared = {
        "module": module,
        "spec_topic": spec_topic,
        "required_mcps": required_mcps,
        "changed_paths": paths,
        "execution_config": execution_config,
    }
    if agent == "Coordinator":
        return {
            **shared,
            "prompt_file": AGENT_PROMPT_FILES[agent],
            "expected_output": [
                "pipeline",
                "inputs",
                "execution_order",
                "parallelism",
                "handoff_requirements",
            ],
            "read_only": True,
        }
    if agent == "Code Writer Agent":
        return {
            **shared,
            "prompt_file": AGENT_PROMPT_FILES[agent],
            "expected_output": [
                "summary",
                "files_changed",
                "spec_inputs_used",
                "commands_run",
                "assumptions",
                "open_risks",
                "recommended_next_agent",
            ],
            "read_only": False,
        }
    if agent == "Test Writer Agent":
        return {
            **shared,
            "prompt_file": AGENT_PROMPT_FILES[agent],
            "expected_output": [
                "tests_added_or_changed",
                "behaviors_locked",
                "commands_run",
                "untested_areas",
                "recommended_next_agent",
            ],
            "read_only": False,
        }
    if agent == "Spec Conformance Agent":
        return {
            **shared,
            "prompt_file": AGENT_PROMPT_FILES[agent],
            "expected_output": [
                "status",
                "findings",
                "code_updates_needed",
                "spec_updates_needed",
                "mcp_updates_needed",
                "evidence",
                "recommended_next_agent",
            ],
            "read_only": True,
        }
    if agent == "Code Review Agent":
        return {
            **shared,
            "prompt_file": AGENT_PROMPT_FILES[agent],
            "expected_output": [
                "findings",
                "residual_risks",
                "questions",
                "recommended_next_agent",
            ],
            "read_only": True,
        }
    if agent == "Coverage & Gaps Agent":
        return {
            **shared,
            "prompt_file": AGENT_PROMPT_FILES[agent],
            "expected_output": [
                "coverage_map",
                "partial_coverage",
                "uncovered_gaps",
                "suggested_next_tests",
                "recommended_next_agent",
            ],
            "read_only": True,
        }
    raise ValueError(f"Unknown agent: {agent}")


def _path_insights(paths: list[str]) -> list[str]:
    insights: list[str] = []
    if any(path.startswith("Measurement/observability/") for path in paths):
        insights.append("observability_assets_changed")
    if any(path.startswith("Measurement/evals/") for path in paths):
        insights.append("eval_dashboards_changed")
    if any(path.startswith("Execution/ingest/hybrid/") for path in paths):
        insights.append("hybrid_ingest_assets_changed")
    if any(path.startswith("Execution/bin/") or path.startswith("Execution/orchestration/") for path in paths):
        insights.append("launcher_assets_changed")
    if any(path.startswith("Execution/docker/postgres/init/") for path in paths):
        insights.append("sql_schema_changed")
    if any(path.startswith("Tools/mcp/") for path in paths):
        insights.append("mcp_metadata_or_tooling_changed")
    if any(re.search(r"request_run_summaries", path) for path in paths):
        insights.append("run_summary_semantics_changed")
    return insights


def _ordered_unique(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _render_prompt_text(
    *,
    task: str,
    agent: str,
    module: str,
    spec_topic: str | None,
    required_mcps: list[str],
    execution_config: dict[str, Any],
    changed_files: list[str],
    changed_test_files: list[str],
    constraints: list[str],
    open_risks: list[str],
) -> str:
    lines = [
        f"Use {AGENT_PROMPT_FILES[agent]} as your role instruction.",
        "",
        f"Task: {task}",
        f"Module or subsystem: {module}",
    ]
    if spec_topic:
        lines.append(f"Spec topic: {spec_topic}")
    if changed_files:
        lines.append("Changed files:")
        lines.extend(f"- {path}" for path in changed_files)
    if changed_test_files:
        lines.append("Changed test files:")
        lines.extend(f"- {path}" for path in changed_test_files)
    if required_mcps:
        lines.append("Required MCPs:")
        lines.extend(f"- {name}" for name in required_mcps)
    if execution_config:
        lines.append("Execution config:")
        lines.append(f"- model: {execution_config.get('model')}")
        lines.append(f"- reasoning_effort: {execution_config.get('reasoning_effort')}")
    if constraints:
        lines.append("Constraints:")
        lines.extend(f"- {item}" for item in constraints)
    if open_risks:
        lines.append("Known open risks:")
        lines.extend(f"- {item}" for item in open_risks)
    lines.extend(
        [
            "",
            "Use the repository handoff template when returning state forward:",
            "- Specification/tasks/multi_agent/handoff_packet.md",
        ]
    )
    return "\n".join(lines)


def _next_pending_agent(state: dict[str, Any]) -> str | None:
    for step in state.get("pipeline", []):
        if step.get("status") == "pending":
            return step.get("agent")
    return None


def _step_by_id(state: dict[str, Any], step_id: str) -> dict[str, Any]:
    for step in state.get("pipeline", []):
        if step.get("step_id") == step_id:
            return step
    raise ValueError(f"Unknown step_id: {step_id}")


def _step_by_agent(state: dict[str, Any], agent: str) -> dict[str, Any] | None:
    for step in state.get("pipeline", []):
        if step.get("agent") == agent:
            return step
    return None


def _clear_step_result(state: dict[str, Any], step_id: str) -> None:
    state["step_results"] = [item for item in state.get("step_results", []) if item.get("step_id") != step_id]


def _reset_steps(state: dict[str, Any], agents: list[str]) -> None:
    targets = set(agents)
    for step in state.get("pipeline", []):
        if step.get("agent") in targets and step.get("agent") != "Coordinator":
            step["status"] = "pending"
            _clear_step_result(state, step["step_id"])


def _ensure_agents_in_pipeline(state: dict[str, Any], agents: list[str]) -> list[str]:
    inserted: list[str] = []
    pipeline = state.get("pipeline", [])
    if not pipeline:
        return inserted

    coordinator_index = 0
    for desired_position, agent in enumerate(agents, start=1):
        if agent == "Coordinator" or _step_by_agent(state, agent) is not None:
            continue
        pipeline.insert(
            min(desired_position, len(pipeline)),
            {
                "step_id": f"step_followup_{uuid.uuid4().hex[:8]}",
                "agent": agent,
                "status": "pending",
                "can_run_in_parallel": False,
                "blocking_dependencies": [pipeline[coordinator_index]["step_id"]],
            },
        )
        inserted.append(agent)
    return inserted


def _followup_agents_for_result(result: dict[str, Any]) -> tuple[list[str], list[str]]:
    agent = result.get("agent")
    followup_agents: list[str] = []
    notes: list[str] = []

    if result.get("spec_updates_needed"):
        notes.append("spec updates are required before workflow can complete")
    if result.get("mcp_updates_needed"):
        followup_agents.extend([
            "Code Writer Agent",
            "Test Writer Agent",
            "Code Review Agent",
            "Coverage & Gaps Agent",
        ])
        notes.append("MCP metadata updates require another implementation cycle")
    if result.get("code_updates_needed"):
        followup_agents.extend([
            "Code Writer Agent",
            "Test Writer Agent",
            "Spec Conformance Agent",
            "Code Review Agent",
            "Coverage & Gaps Agent",
        ])
        notes.append("code updates requested by validation require a new implementation cycle")
    if agent == "Code Review Agent" and result.get("findings"):
        followup_agents.extend([
            "Code Writer Agent",
            "Test Writer Agent",
            "Spec Conformance Agent",
            "Code Review Agent",
            "Coverage & Gaps Agent",
        ])
        notes.append("review findings require a fix-and-validate cycle")
    if agent == "Coverage & Gaps Agent" and result.get("findings"):
        followup_agents.extend([
            "Test Writer Agent",
            "Spec Conformance Agent",
            "Code Review Agent",
            "Coverage & Gaps Agent",
        ])
        notes.append("coverage findings require additional testing and revalidation")
    return _ordered_unique(followup_agents), notes


def _blocking_summary(step_results: list[dict[str, Any]]) -> dict[str, Any]:
    code_updates_needed: list[str] = []
    spec_updates_needed: list[str] = []
    mcp_updates_needed: list[str] = []
    open_risks: list[str] = []
    findings: list[str] = []

    for result in step_results:
        code_updates_needed.extend(result.get("code_updates_needed", []))
        spec_updates_needed.extend(result.get("spec_updates_needed", []))
        mcp_updates_needed.extend(result.get("mcp_updates_needed", []))
        open_risks.extend(result.get("open_risks", []))
        findings.extend(result.get("findings", []))

    return {
        "code_updates_needed": _ordered_unique(code_updates_needed),
        "spec_updates_needed": _ordered_unique(spec_updates_needed),
        "mcp_updates_needed": _ordered_unique(mcp_updates_needed),
        "open_risks": _ordered_unique(open_risks),
        "findings": _ordered_unique(findings),
    }


def _completion_status(state: dict[str, Any]) -> dict[str, Any]:
    summary = _blocking_summary(state.get("step_results", []))
    pipeline = state.get("pipeline", [])
    step_statuses = {step.get("agent"): step.get("status") for step in pipeline}
    mode = state.get("mode", "implement-change")
    policy = _completion_policy()
    completion_rules = policy.get("completion_requirements", {})
    selected = completion_rules.get(mode, completion_rules.get("default", {}))

    required_statuses = selected.get("require_statuses", [])
    missing_required: list[str] = []
    for entry in required_statuses:
        if not isinstance(entry, dict):
            continue
        for agent, required_status in entry.items():
            if step_statuses.get(agent) != required_status:
                missing_required.append(f"{agent} must be {required_status}")

    blocking_reasons: list[str] = []
    for step in pipeline:
        if step.get("status") in {"blocked", "failed"}:
            blocking_reasons.append(f"{step.get('agent')} is {step.get('status')}")
    if summary["spec_updates_needed"]:
        blocking_reasons.append("spec updates still required")
    if summary["mcp_updates_needed"]:
        blocking_reasons.append("MCP updates still required")

    is_complete = not missing_required and not blocking_reasons and _next_pending_agent(state) is None
    return {
        "is_complete": is_complete,
        "missing_required": missing_required,
        "blocking_reasons": blocking_reasons,
        "summary": summary,
        "next_agent": _next_pending_agent(state),
    }


@mcp.tool
def get_workflow_schema() -> dict[str, Any]:
    """Return the machine-readable workflow state schema."""
    return _workflow_schema()


@mcp.tool
def get_agent_result_schema() -> dict[str, Any]:
    """Return the machine-readable specialist-agent result schema."""
    return _agent_result_schema()


@mcp.tool
def get_decision_rules() -> dict[str, Any]:
    """Return the orchestrator routing and loop-back rules."""
    return _decision_rules()


@mcp.tool
def get_completion_policy() -> dict[str, Any]:
    """Return the orchestrator completion and blocking rules."""
    return _completion_policy()


@mcp.tool
def plan_task(
    task: str,
    mode: str | None = None,
    module: str | None = None,
    changed_paths: list[str] | None = None,
    constraints: list[str] | None = None,
) -> dict[str, Any]:
    """
    Build a project-aware workflow plan for one high-level task.
    This phase plans the workflow but does not execute specialist agents.
    """
    if not task.strip():
        raise ValueError("task must not be empty")

    normalized_mode = _normalize_mode(mode)
    normalized_paths = _normalize_paths(changed_paths)
    resolved_module = _guess_module(task, normalized_paths, module)
    spec_topic = _infer_spec_topic(resolved_module, task, normalized_paths)
    required_mcps, flags = _collect_required_mcps(resolved_module, normalized_paths)
    agent_names = _pipeline_for_mode(normalized_mode)
    pipeline = _build_pipeline(agent_names)
    task_id = f"wf_{uuid.uuid4().hex[:12]}"
    normalized_constraints = [item.strip() for item in (constraints or []) if item.strip()]

    step_inputs = {
        step["step_id"]: _agent_inputs(
            agent=step["agent"],
            module=resolved_module,
            spec_topic=spec_topic,
            required_mcps=required_mcps,
            paths=normalized_paths,
        )
        for step in pipeline
    }

    workflow_state = {
        "task_id": task_id,
        "input_task": task.strip(),
        "mode": normalized_mode,
        "module": resolved_module,
        "status": "planned",
        "pipeline": pipeline,
        "current_step_index": 1 if len(pipeline) > 1 else 0,
        "step_results": [
            {
                "step_id": "step_1",
                "agent": "Coordinator",
                "status": "completed",
                "summary": "Workflow planned from task input and policy rules.",
                "files_changed": [],
                "tests_changed": [],
                "spec_inputs_used": [],
                "mcps_consulted": required_mcps,
                "commands_run": [],
                "findings": [],
                "code_updates_needed": [],
                "spec_updates_needed": [],
                "mcp_updates_needed": [],
                "open_risks": [],
                "recommended_next_agent": pipeline[1]["agent"] if len(pipeline) > 1 else "None",
            }
        ],
        "required_mcps": required_mcps,
        "spec_topic": spec_topic,
        "constraints": normalized_constraints,
        "flags": flags,
        "path_insights": _path_insights(normalized_paths),
        "changed_files": normalized_paths,
        "changed_test_files": [],
        "open_risks": [],
    }

    _save_workflow_state(workflow_state)

    return {
        "task_id": task_id,
        "task": task.strip(),
        "mode": normalized_mode,
        "module": resolved_module,
        "spec_topic": spec_topic,
        "changed_paths": normalized_paths,
        "constraints": normalized_constraints,
        "required_mcps": required_mcps,
        "flags": flags,
        "path_insights": _path_insights(normalized_paths),
        "pipeline": pipeline,
        "step_inputs": step_inputs,
        "handoff_template": "Specification/tasks/multi_agent/handoff_packet.md",
        "launcher_template": "Specification/tasks/multi_agent/launchers.md",
        "workflow_state": workflow_state,
        "next_action": pipeline[1]["agent"] if len(pipeline) > 1 else None,
    }


@mcp.tool
def start_workflow(
    task: str,
    mode: str | None = None,
    module: str | None = None,
    changed_paths: list[str] | None = None,
    constraints: list[str] | None = None,
) -> dict[str, Any]:
    """Plan a task and immediately prepare the first specialist-agent assignment."""
    planned = plan_task(
        task=task,
        mode=mode,
        module=module,
        changed_paths=changed_paths,
        constraints=constraints,
    )
    running = run_workflow(planned["task_id"])
    return {
        "planned": planned,
        "running": running,
    }


@mcp.tool
def run_workflow(task_id: str) -> dict[str, Any]:
    """
    Advance a planned workflow into a runnable state.
    This Phase 2 scaffold prepares the next agent assignment but does not spawn agents automatically.
    """
    state = _load_workflow_state(task_id)
    if state.get("status") == "planned":
        state["status"] = "running"

    next_agent = _next_pending_agent(state)
    if next_agent is None:
        completion = _completion_status(state)
        state["status"] = "completed" if completion["is_complete"] else "blocked"
        state["final_report"] = {
            "summary": "Workflow has no pending steps.",
            "completion_reason": "all planned steps are complete" if completion["is_complete"] else "workflow requires follow-up",
            "remaining_followups": completion["blocking_reasons"] + completion["missing_required"],
        }
        _save_workflow_state(state)
        return {
            "task_id": task_id,
            "status": state["status"],
            "next_agent": None,
            "assignment": None,
            "completion": completion,
        }

    step = _step_by_agent(state, next_agent)
    if step is None:
        raise ValueError(f"Could not locate step for next agent: {next_agent}")
    step["status"] = "running"
    state["current_step_index"] = max(0, state["pipeline"].index(step))
    _save_workflow_state(state)

    return {
        "task_id": task_id,
        "status": state["status"],
        "next_agent": next_agent,
        "assignment": {
            "step_id": step["step_id"],
            "agent": next_agent,
            "inputs": _agent_inputs(
                agent=next_agent,
                module=state["module"],
                spec_topic=state.get("spec_topic"),
                required_mcps=state["required_mcps"],
                paths=state.get("changed_files", []),
            ),
            "prompt_text": _render_prompt_text(
                task=state["input_task"],
                agent=next_agent,
                module=state["module"],
                spec_topic=state.get("spec_topic"),
                required_mcps=state["required_mcps"],
                execution_config=_agent_inputs(
                    agent=next_agent,
                    module=state["module"],
                    spec_topic=state.get("spec_topic"),
                    required_mcps=state["required_mcps"],
                    paths=state.get("changed_files", []),
                )["execution_config"],
                changed_files=state.get("changed_files", []),
                changed_test_files=state.get("changed_test_files", []),
                constraints=state.get("constraints", []),
                open_risks=state.get("open_risks", []),
            ),
            "handoff_template": "Specification/tasks/multi_agent/handoff_packet.md",
            "launcher_template": "Specification/tasks/multi_agent/launchers.md",
        },
        "note": "The workflow engine marks the next step as running and returns a ready-to-use assignment with prompt text. Automatic sub-agent execution is not implemented yet.",
    }


@mcp.tool
def submit_step_result(
    task_id: str,
    step_id: str,
    agent: str,
    status: str,
    summary: str,
    recommended_next_agent: str,
    findings: list[str] | None = None,
    files_changed: list[str] | None = None,
    tests_changed: list[str] | None = None,
    spec_inputs_used: list[str] | None = None,
    mcps_consulted: list[str] | None = None,
    commands_run: list[str] | None = None,
    code_updates_needed: list[str] | None = None,
    spec_updates_needed: list[str] | None = None,
    mcp_updates_needed: list[str] | None = None,
    open_risks: list[str] | None = None,
    blocking_reason: str | None = None,
) -> dict[str, Any]:
    """Submit a structured result for one workflow step."""
    if agent not in KNOWN_AGENTS:
        raise ValueError(f"Unknown agent: {agent}")
    if status not in {"completed", "blocked", "failed"}:
        raise ValueError(f"Unsupported step status: {status}")
    if not summary.strip():
        raise ValueError("summary must not be empty")

    state = _load_workflow_state(task_id)
    step = _step_by_id(state, step_id)
    if step.get("agent") != agent:
        raise ValueError(f"Step {step_id} is assigned to {step.get('agent')}, not {agent}")

    result = {
        "step_id": step_id,
        "agent": agent,
        "status": status,
        "summary": summary.strip(),
        "files_changed": _normalize_paths(files_changed),
        "tests_changed": _normalize_paths(tests_changed),
        "spec_inputs_used": _ordered_unique([item.strip() for item in (spec_inputs_used or []) if item.strip()]),
        "mcps_consulted": _ordered_unique([item.strip() for item in (mcps_consulted or []) if item.strip()]),
        "commands_run": _ordered_unique([item.strip() for item in (commands_run or []) if item.strip()]),
        "findings": _ordered_unique([item.strip() for item in (findings or []) if item.strip()]),
        "code_updates_needed": _ordered_unique([item.strip() for item in (code_updates_needed or []) if item.strip()]),
        "spec_updates_needed": _ordered_unique([item.strip() for item in (spec_updates_needed or []) if item.strip()]),
        "mcp_updates_needed": _ordered_unique([item.strip() for item in (mcp_updates_needed or []) if item.strip()]),
        "open_risks": _ordered_unique([item.strip() for item in (open_risks or []) if item.strip()]),
        "recommended_next_agent": recommended_next_agent.strip(),
    }
    if blocking_reason:
        result["blocking_reason"] = blocking_reason.strip()

    step_results = [item for item in state.get("step_results", []) if item.get("step_id") != step_id]
    step_results.append(result)
    state["step_results"] = step_results
    step["status"] = status

    if result["files_changed"]:
        state["changed_files"] = _ordered_unique(state.get("changed_files", []) + result["files_changed"])
    if result["tests_changed"]:
        state["changed_test_files"] = _ordered_unique(state.get("changed_test_files", []) + result["tests_changed"])
    if result["open_risks"]:
        state["open_risks"] = _ordered_unique(state.get("open_risks", []) + result["open_risks"])

    followup_agents, followup_notes = _followup_agents_for_result(result)
    inserted_agents: list[str] = []
    if followup_agents:
        inserted_agents = _ensure_agents_in_pipeline(state, followup_agents)
        _reset_steps(state, followup_agents)
        state["open_risks"] = _ordered_unique(state.get("open_risks", []) + followup_notes)

    completion = _completion_status(state)
    if status in {"blocked", "failed"}:
        state["status"] = status
    elif completion["is_complete"]:
        state["status"] = "completed"
        state["final_report"] = {
            "summary": "Workflow completed based on current completion policy.",
            "completion_reason": "all required steps completed with no remaining blockers",
            "remaining_followups": [],
        }
    else:
        state["status"] = "running"

    _save_workflow_state(state)
    return {
        "task_id": task_id,
        "workflow_status": state["status"],
        "completion": completion,
        "next_agent": completion["next_agent"],
        "followup_agents": followup_agents,
        "inserted_agents": inserted_agents,
        "followup_notes": followup_notes,
    }


@mcp.tool
def submit_and_continue(
    task_id: str,
    step_id: str,
    agent: str,
    status: str,
    summary: str,
    recommended_next_agent: str,
    findings: list[str] | None = None,
    files_changed: list[str] | None = None,
    tests_changed: list[str] | None = None,
    spec_inputs_used: list[str] | None = None,
    mcps_consulted: list[str] | None = None,
    commands_run: list[str] | None = None,
    code_updates_needed: list[str] | None = None,
    spec_updates_needed: list[str] | None = None,
    mcp_updates_needed: list[str] | None = None,
    open_risks: list[str] | None = None,
    blocking_reason: str | None = None,
) -> dict[str, Any]:
    """Submit one step result and immediately return the next assignment or final workflow state."""
    submitted = submit_step_result(
        task_id=task_id,
        step_id=step_id,
        agent=agent,
        status=status,
        summary=summary,
        recommended_next_agent=recommended_next_agent,
        findings=findings,
        files_changed=files_changed,
        tests_changed=tests_changed,
        spec_inputs_used=spec_inputs_used,
        mcps_consulted=mcps_consulted,
        commands_run=commands_run,
        code_updates_needed=code_updates_needed,
        spec_updates_needed=spec_updates_needed,
        mcp_updates_needed=mcp_updates_needed,
        open_risks=open_risks,
        blocking_reason=blocking_reason,
    )
    if submitted["workflow_status"] in {"completed", "blocked", "failed", "cancelled"}:
        return {
            "submitted": submitted,
            "next_assignment": None,
            "report": get_workflow_report(task_id),
        }
    return {
        "submitted": submitted,
        "next_assignment": run_workflow(task_id),
    }


@mcp.tool
def get_workflow_status(task_id: str) -> dict[str, Any]:
    """Return the current workflow state and next-action summary."""
    state = _load_workflow_state(task_id)
    completion = _completion_status(state)
    return {
        "task_id": task_id,
        "status": state.get("status"),
        "module": state.get("module"),
        "mode": state.get("mode"),
        "next_agent": completion["next_agent"],
        "pipeline": state.get("pipeline", []),
        "changed_files": state.get("changed_files", []),
        "changed_test_files": state.get("changed_test_files", []),
        "open_risks": state.get("open_risks", []),
        "completion": completion,
    }


@mcp.tool
def get_workflow_report(task_id: str) -> dict[str, Any]:
    """Return a compact workflow report with step results and remaining blockers."""
    state = _load_workflow_state(task_id)
    completion = _completion_status(state)
    return {
        "task_id": task_id,
        "status": state.get("status"),
        "task": state.get("input_task"),
        "mode": state.get("mode"),
        "module": state.get("module"),
        "required_mcps": state.get("required_mcps", []),
        "changed_files": state.get("changed_files", []),
        "changed_test_files": state.get("changed_test_files", []),
        "step_results": state.get("step_results", []),
        "blocking_summary": completion["summary"],
        "missing_required": completion["missing_required"],
        "blocking_reasons": completion["blocking_reasons"],
        "final_report": state.get("final_report"),
    }


@mcp.tool
def explain_decision(task_id: str) -> dict[str, Any]:
    """Explain the current workflow routing decision, blockers, and next step."""
    state = _load_workflow_state(task_id)
    completion = _completion_status(state)
    next_agent = completion["next_agent"]
    next_assignment = None
    if next_agent is not None:
        next_assignment = {
            "agent": next_agent,
            "prompt_file": AGENT_PROMPT_FILES[next_agent],
            "prompt_text": _render_prompt_text(
                task=state["input_task"],
                agent=next_agent,
                module=state["module"],
                spec_topic=state.get("spec_topic"),
                required_mcps=state["required_mcps"],
                execution_config=_agent_inputs(
                    agent=next_agent,
                    module=state["module"],
                    spec_topic=state.get("spec_topic"),
                    required_mcps=state["required_mcps"],
                    paths=state.get("changed_files", []),
                )["execution_config"],
                changed_files=state.get("changed_files", []),
                changed_test_files=state.get("changed_test_files", []),
                constraints=state.get("constraints", []),
                open_risks=state.get("open_risks", []),
            ),
        }

    return {
        "task_id": task_id,
        "status": state.get("status"),
        "mode": state.get("mode"),
        "module": state.get("module"),
        "required_mcps": state.get("required_mcps", []),
        "flags": state.get("flags", []),
        "path_insights": state.get("path_insights", []),
        "blocking_reasons": completion["blocking_reasons"],
        "missing_required": completion["missing_required"],
        "next_agent": next_agent,
        "next_assignment": next_assignment,
    }


@mcp.tool
def resume_workflow(task_id: str) -> dict[str, Any]:
    """Resume a workflow from blocked or running state by preparing the next pending assignment."""
    state = _load_workflow_state(task_id)
    if state.get("status") == "cancelled":
        raise ValueError("Cancelled workflows cannot be resumed")
    if state.get("status") == "completed":
        return {
            "task_id": task_id,
            "status": "completed",
            "message": "Workflow is already complete.",
        }
    if state.get("status") in {"blocked", "failed"}:
        state["status"] = "running"
        _save_workflow_state(state)
    return run_workflow(task_id)


@mcp.tool
def cancel_workflow(task_id: str, reason: str | None = None) -> dict[str, Any]:
    """Cancel a workflow and persist the final cancellation reason."""
    state = _load_workflow_state(task_id)
    state["status"] = "cancelled"
    state["final_report"] = {
        "summary": "Workflow was cancelled before completion.",
        "completion_reason": reason.strip() if reason and reason.strip() else "cancelled by operator",
        "remaining_followups": [],
    }
    _save_workflow_state(state)
    return {
        "task_id": task_id,
        "status": "cancelled",
        "reason": state["final_report"]["completion_reason"],
    }


@mcp.tool
def retry_step(task_id: str, step_id: str) -> dict[str, Any]:
    """Reset one step to pending and clear its persisted result so the workflow can rerun it."""
    state = _load_workflow_state(task_id)
    step = _step_by_id(state, step_id)
    if step.get("agent") == "Coordinator":
        raise ValueError("Coordinator step cannot be retried")

    step["status"] = "pending"
    _clear_step_result(state, step_id)
    state["status"] = "running"
    _save_workflow_state(state)

    completion = _completion_status(state)
    return {
        "task_id": task_id,
        "reset_step": {
            "step_id": step_id,
            "agent": step.get("agent"),
        },
        "next_agent": completion["next_agent"],
        "workflow_status": state["status"],
    }


@mcp.tool
def list_workflow_artifacts(task_id: str) -> dict[str, Any]:
    """List persisted artifacts for one workflow."""
    state = _load_workflow_state(task_id)
    state_path = _workflow_state_path(task_id)
    return {
        "task_id": task_id,
        "artifacts": [
            {
                "kind": "workflow_state",
                "path": str(state_path.relative_to(ROOT.parent.parent.parent)),
            }
        ],
        "step_result_count": len(state.get("step_results", [])),
    }


if __name__ == "__main__":
    mcp.run()

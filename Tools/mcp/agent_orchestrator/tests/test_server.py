from __future__ import annotations

from pathlib import Path

from Tools.mcp.agent_orchestrator import server


def _use_temp_state_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(server, "STATE_ROOT", tmp_path / "state")


def test_plan_task_infers_module_and_mcps(monkeypatch, tmp_path):
    _use_temp_state_dir(monkeypatch, tmp_path)

    result = server.plan_task(
        task="add a query token metric to rag_runtime observability",
        mode="implement-change",
        changed_paths=[
            "Execution/rag_runtime/src/input_validation/mod.rs",
            "Measurement/observability/grafana/dashboards/rag_runtime.json",
        ],
    )

    assert result["module"] == "rag_runtime"
    assert result["required_mcps"] == [
        "Project Context MCP",
        "Spec MCP",
        "Spec Conformance MCP",
        "Observability MCP",
    ]
    assert result["next_action"] == "Code Writer Agent"


def test_plan_task_infers_hybrid_ingest_module_and_mcps(monkeypatch, tmp_path):
    _use_temp_state_dir(monkeypatch, tmp_path)

    result = server.plan_task(
        task="update hybrid ingest sparse artifacts",
        mode="implement-change",
        changed_paths=[
            "Execution/ingest/hybrid/ingest.py",
            "Execution/ingest/hybrid/configs/fixed_bm25.toml",
        ],
    )

    assert result["module"] == "hybrid_ingest"
    assert result["path_insights"] == ["hybrid_ingest_assets_changed"]
    assert result["required_mcps"] == [
        "Project Context MCP",
        "Spec MCP",
        "Spec Conformance MCP",
        "Qdrant MCP",
    ]


def test_plan_task_infers_run_stack_launcher_module_and_mcps(monkeypatch, tmp_path):
    _use_temp_state_dir(monkeypatch, tmp_path)

    result = server.plan_task(
        task="adjust run stack launcher defaults",
        mode="implement-change",
        changed_paths=["Execution/bin/run_stack.py"],
    )

    assert result["module"] == "run_stack_launcher"
    assert result["path_insights"] == ["launcher_assets_changed"]
    assert result["required_mcps"] == [
        "Project Context MCP",
        "Spec MCP",
        "Eval Experiments MCP",
    ]


def test_run_workflow_returns_ready_prompt_text(monkeypatch, tmp_path):
    _use_temp_state_dir(monkeypatch, tmp_path)

    planned = server.plan_task(
        task="review eval dashboard change",
        mode="review-change",
        changed_paths=["Measurement/evals/grafana/dashboards/eval_runs.json"],
    )
    running = server.run_workflow(planned["task_id"])

    assert running["next_agent"] == "Spec Conformance Agent"
    assert "Use Specification/tasks/multi_agent/spec_conformance_agent.md" in running["assignment"]["prompt_text"]
    assert "Eval Experiments MCP" in running["assignment"]["prompt_text"]
    assert running["assignment"]["inputs"]["execution_config"] == {
        "model": "gpt-5.4-mini",
        "reasoning_effort": "medium",
    }
    assert "model: gpt-5.4-mini" in running["assignment"]["prompt_text"]


def test_review_findings_expand_pipeline_with_write_steps(monkeypatch, tmp_path):
    _use_temp_state_dir(monkeypatch, tmp_path)

    planned = server.plan_task(
        task="review rag_runtime token metric change",
        mode="review-change",
        changed_paths=[
            "Execution/rag_runtime/src/input_validation/mod.rs",
            "Measurement/observability/grafana/dashboards/rag_runtime.json",
        ],
    )

    spec_step = server.run_workflow(planned["task_id"])
    server.submit_step_result(
        task_id=planned["task_id"],
        step_id=spec_step["assignment"]["step_id"],
        agent=spec_step["next_agent"],
        status="completed",
        summary="Spec conformance check finished with no blocking mismatches.",
        recommended_next_agent="Code Review Agent",
    )

    review_step = server.run_workflow(planned["task_id"])
    result = server.submit_step_result(
        task_id=planned["task_id"],
        step_id=review_step["assignment"]["step_id"],
        agent=review_step["next_agent"],
        status="completed",
        summary="Review found a correctness issue.",
        recommended_next_agent="Code Writer Agent",
        findings=["Metric is emitted before validation and can overcount rejected inputs."],
    )

    status = server.get_workflow_status(planned["task_id"])
    pipeline_agents = [step["agent"] for step in status["pipeline"]]

    assert result["inserted_agents"] == ["Code Writer Agent", "Test Writer Agent"]
    assert status["next_agent"] == "Code Writer Agent"
    assert pipeline_agents == [
        "Coordinator",
        "Code Writer Agent",
        "Test Writer Agent",
        "Spec Conformance Agent",
        "Code Review Agent",
        "Coverage & Gaps Agent",
    ]


def test_retry_step_resets_completed_step(monkeypatch, tmp_path):
    _use_temp_state_dir(monkeypatch, tmp_path)

    planned = server.plan_task(
        task="review eval dashboard change",
        mode="review-change",
        changed_paths=["Measurement/evals/grafana/dashboards/eval_runs.json"],
    )
    running = server.run_workflow(planned["task_id"])
    server.submit_step_result(
        task_id=planned["task_id"],
        step_id=running["assignment"]["step_id"],
        agent=running["next_agent"],
        status="completed",
        summary="Spec conformance completed.",
        recommended_next_agent="Code Review Agent",
    )

    retried = server.retry_step(planned["task_id"], running["assignment"]["step_id"])
    status = server.get_workflow_status(planned["task_id"])

    assert retried["reset_step"]["agent"] == "Spec Conformance Agent"
    assert status["next_agent"] == "Spec Conformance Agent"
    assert status["pipeline"][1]["status"] == "pending"


def test_explain_decision_reports_next_assignment(monkeypatch, tmp_path):
    _use_temp_state_dir(monkeypatch, tmp_path)

    planned = server.plan_task(
        task="add eval run summary comparison support",
        mode="implement-change",
        changed_paths=[
            "Execution/docker/postgres/init/006_request_run_summaries.sql",
            "Measurement/evals/grafana/dashboards/eval_runs.json",
        ],
    )
    explanation = server.explain_decision(planned["task_id"])

    assert explanation["next_agent"] == "Code Writer Agent"
    assert "Execution/docker/postgres/init/006_request_run_summaries.sql" in explanation["next_assignment"]["prompt_text"]
    assert explanation["required_mcps"] == [
        "Project Context MCP",
        "Spec MCP",
        "Postgres MCP",
        "Eval Experiments MCP",
        "Observability MCP",
    ]


def test_start_workflow_returns_first_assignment(monkeypatch, tmp_path):
    _use_temp_state_dir(monkeypatch, tmp_path)

    result = server.start_workflow(
        task="add a query token metric to rag_runtime observability",
        mode="implement-change",
        changed_paths=[
            "Execution/rag_runtime/src/input_validation/mod.rs",
            "Measurement/observability/grafana/dashboards/rag_runtime.json",
        ],
    )

    assert result["planned"]["task_id"] == result["running"]["task_id"]
    assert result["running"]["next_agent"] == "Code Writer Agent"
    assert "Use Specification/tasks/multi_agent/code_writer_agent.md" in result["running"]["assignment"]["prompt_text"]


def test_submit_and_continue_returns_next_assignment(monkeypatch, tmp_path):
    _use_temp_state_dir(monkeypatch, tmp_path)

    started = server.start_workflow(
        task="review eval dashboard change",
        mode="review-change",
        changed_paths=["Measurement/evals/grafana/dashboards/eval_runs.json"],
    )
    running = started["running"]

    result = server.submit_and_continue(
        task_id=started["planned"]["task_id"],
        step_id=running["assignment"]["step_id"],
        agent=running["next_agent"],
        status="completed",
        summary="Spec conformance completed with no blocking mismatches.",
        recommended_next_agent="Code Review Agent",
    )

    assert result["submitted"]["next_agent"] == "Code Review Agent"
    assert result["next_assignment"]["next_agent"] == "Code Review Agent"
    assert "Use Specification/tasks/multi_agent/code_review_agent.md" in result["next_assignment"]["assignment"]["prompt_text"]

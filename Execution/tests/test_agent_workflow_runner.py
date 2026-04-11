from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from Execution.orchestration import agent_workflow_runner
from Tools.mcp.agent_orchestrator import server as orchestrator


class AgentWorkflowRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        orchestrator.STATE_ROOT = Path(self._tmpdir.name) / "state"

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_start_dispatch_returns_first_assignment(self) -> None:
        result = agent_workflow_runner.dispatch(
            [
                "start",
                "--task",
                "add a query token metric to rag_runtime observability",
                "--mode",
                "implement-change",
                "--changed-path",
                "Execution/rag_runtime/src/input_validation/mod.rs",
                "--changed-path",
                "Measurement/observability/grafana/dashboards/rag_runtime.json",
            ]
        )

        self.assertEqual(result["running"]["next_agent"], "Code Writer Agent")
        self.assertEqual(result["planned"]["module"], "rag_runtime")

    def test_submit_and_continue_dispatch_uses_result_json(self) -> None:
        started = agent_workflow_runner.dispatch(
            [
                "start",
                "--task",
                "review eval dashboard change",
                "--mode",
                "review-change",
                "--changed-path",
                "Measurement/evals/grafana/dashboards/eval_runs.json",
            ]
        )

        running = started["running"]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(
                {
                    "step_id": running["assignment"]["step_id"],
                    "agent": running["next_agent"],
                    "status": "completed",
                    "summary": "Spec conformance completed with no blocking mismatches.",
                    "recommended_next_agent": "Code Review Agent",
                },
                handle,
            )
            result_path = handle.name

        try:
            result = agent_workflow_runner.dispatch(
                [
                    "submit-and-continue",
                    "--task-id",
                    started["planned"]["task_id"],
                    "--result-json",
                    result_path,
                ]
            )
        finally:
            Path(result_path).unlink(missing_ok=True)

        self.assertEqual(result["submitted"]["next_agent"], "Code Review Agent")
        self.assertEqual(result["next_assignment"]["next_agent"], "Code Review Agent")


if __name__ == "__main__":
    unittest.main()

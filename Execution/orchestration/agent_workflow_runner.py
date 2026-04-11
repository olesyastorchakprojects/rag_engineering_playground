from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from Tools.mcp.agent_orchestrator import server as orchestrator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the external agent workflow runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Plan and start a workflow")
    start.add_argument("--task", required=True)
    start.add_argument("--mode")
    start.add_argument("--module")
    start.add_argument("--changed-path", action="append", dest="changed_paths", default=[])
    start.add_argument("--constraint", action="append", dest="constraints", default=[])

    status = subparsers.add_parser("status", help="Get workflow status")
    status.add_argument("--task-id", required=True)

    explain = subparsers.add_parser("explain", help="Explain the current routing decision")
    explain.add_argument("--task-id", required=True)

    resume = subparsers.add_parser("resume", help="Resume a workflow")
    resume.add_argument("--task-id", required=True)

    cancel = subparsers.add_parser("cancel", help="Cancel a workflow")
    cancel.add_argument("--task-id", required=True)
    cancel.add_argument("--reason")

    artifacts = subparsers.add_parser("artifacts", help="List workflow artifacts")
    artifacts.add_argument("--task-id", required=True)

    retry = subparsers.add_parser("retry", help="Retry one step")
    retry.add_argument("--task-id", required=True)
    retry.add_argument("--step-id", required=True)

    submit = subparsers.add_parser("submit", help="Submit one step result")
    submit.add_argument("--task-id", required=True)
    submit.add_argument("--result-json", required=True)

    submit_and_continue = subparsers.add_parser(
        "submit-and-continue",
        help="Submit one step result and immediately fetch the next assignment",
    )
    submit_and_continue.add_argument("--task-id", required=True)
    submit_and_continue.add_argument("--result-json", required=True)

    return parser


def _load_result_payload(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("result JSON must be an object")
    return payload


def _submit_kwargs(task_id: str, result_json: str) -> dict[str, Any]:
    payload = _load_result_payload(result_json)
    payload["task_id"] = task_id
    return payload


def dispatch(argv: list[str] | None = None) -> dict[str, Any]:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "start":
        return orchestrator.start_workflow(
            task=args.task,
            mode=args.mode,
            module=args.module,
            changed_paths=args.changed_paths,
            constraints=args.constraints,
        )
    if args.command == "status":
        return orchestrator.get_workflow_status(args.task_id)
    if args.command == "explain":
        return orchestrator.explain_decision(args.task_id)
    if args.command == "resume":
        return orchestrator.resume_workflow(args.task_id)
    if args.command == "cancel":
        return orchestrator.cancel_workflow(args.task_id, reason=args.reason)
    if args.command == "artifacts":
        return orchestrator.list_workflow_artifacts(args.task_id)
    if args.command == "retry":
        return orchestrator.retry_step(args.task_id, args.step_id)
    if args.command == "submit":
        return orchestrator.submit_step_result(**_submit_kwargs(args.task_id, args.result_json))
    if args.command == "submit-and-continue":
        return orchestrator.submit_and_continue(**_submit_kwargs(args.task_id, args.result_json))

    raise ValueError(f"Unsupported command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    payload = dispatch(argv)
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

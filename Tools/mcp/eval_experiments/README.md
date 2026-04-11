# Eval Experiments MCP

This MCP server provides a run-oriented layer for eval analysis.

It is not a replacement for:

- `Postgres MCP` for raw access to eval tables
- `Spec MCP` for formal eval-pipeline contracts
- `Project Context MCP` for the broader operational picture

Instead, it adds a higher-level analytical view on top of:

- PostgreSQL eval tables
- `Evidence/evals/runs/*/run_manifest.json`
- `Evidence/evals/runs/*/run_report.md`
- `Measurement/evals/grafana/*` as the repository-owned observability surface for eval dashboards

The current dashboard surface is:

- `Eval Usage Overview` reflects request-level token usage and run volume for recent eval traffic
- `Eval Runs` reflects the batch/run-oriented eval picture and run comparison view

## Tool Surface

- `list_recent_runs(limit=20)`
- `get_run_manifest(run_id)`
- `get_run_report(run_id)`
- `summarize_run(run_id)`
- `compare_runs(run_a, run_b)`
- `find_runs_for_request(request_id, limit=20)`
- `compare_request_across_runs(request_id, run_a, run_b)`
- `get_run_request_matrix(run_id)`
- `get_run_regressions(run_a, run_b, limit=20)`
- `get_run_artifact_health(run_id)`

## When To Use It

Use this server when you want the eval story at the run level rather than the row level.

Good examples:

- "show me the latest runs"
- "summarize this run from its manifest, report, and DB truth"
- "compare these two runs"
- "which runs included this `request_id`?"
- "what changed for this request across two runs?"
- "what regressions or scope mismatches stand out?"

## Semantics

- `run_id` is the source of truth for run identity
- `run_manifest.json` is the source of truth for run metadata
- `run_report.md` is the source of truth for the human-readable run snapshot
- row-level run truth comes from:
  - `judge_generation_results`
  - `judge_retrieval_results`
  - `eval_processing_state`
- `request_summaries` is useful request-level data, but it is not a run-scoped source of truth

## Notes

- the comparison path is intentionally lightweight
- the server does not recompute a full markdown report diff
- if `run_report.md` is missing, run summarization still works
- if the manifest is missing, the server can still fall back to DB rows, but provenance and request-scope diffing become degraded
- `compare_request_across_runs(...)` does not use `request_summaries` as the main comparison signal because it is not run-scoped
- `get_run_request_matrix(...)` is most complete when `run_manifest.json` provides `run_scope_request_ids`
- `summarize_run(...)` and `get_run_artifact_health(...)` also try to surface split/mismatch cases where generation and retrieval rows for the same frozen scope ended up under different `run_id` values

## Local Run

```bash
./.venv/bin/python Tools/mcp/eval_experiments/server.py
```

## Expected MCP Registration

This server is intended to be registered as a local stdio MCP server in the local Codex configuration.

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg import Error as PsycopgError
from psycopg.rows import dict_row
from fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNS_ROOT = REPO_ROOT / "Evidence" / "evals" / "runs"
EVAL_GRAFANA_DASHBOARDS_DIR = REPO_ROOT / "Measurement" / "evals" / "grafana" / "dashboards"
EVAL_GRAFANA_PROVISIONING_DIR = REPO_ROOT / "Measurement" / "evals" / "grafana" / "provisioning"
DEFAULT_POSTGRES_URL = "postgres://postgres:postgres@localhost:5432/rag_eval"

mcp = FastMCP("eval-experiments")


def _postgres_url() -> str:
    return os.environ.get("POSTGRES_URL", DEFAULT_POSTGRES_URL)


def _redact_url(url: str) -> str:
    parts = urlsplit(url)
    if "@" not in parts.netloc:
        return url
    userinfo, hostinfo = parts.netloc.rsplit("@", 1)
    if ":" in userinfo:
        username, _password = userinfo.split(":", 1)
        safe_netloc = f"{username}:***@{hostinfo}"
    else:
        safe_netloc = f"{userinfo}@{hostinfo}"
    return urlunsplit((parts.scheme, safe_netloc, parts.path, parts.query, parts.fragment))


def _db_error_payload(operation: str, exc: Exception, **context: Any) -> dict[str, Any]:
    payload = {
        "ok": False,
        "operation": operation,
        "error_type": exc.__class__.__name__,
        "error": str(exc),
        "postgres_url": _redact_url(_postgres_url()),
    }
    if context:
        payload["context"] = context
    return payload


def _tool_error_payload(operation: str, exc: Exception, **context: Any) -> dict[str, Any]:
    payload = {
        "ok": False,
        "operation": operation,
        "error_type": exc.__class__.__name__,
        "error": str(exc),
    }
    if context:
        payload["context"] = context
    return payload


def _validate_limit(limit: int) -> int:
    if limit < 1:
        raise ValueError("limit must be >= 1")
    return min(limit, 100)


def _validate_run_id(run_id: str) -> str:
    candidate = run_id.strip()
    if not candidate:
        raise ValueError("run_id must not be empty")
    return candidate


def _validate_request_id(request_id: str) -> str:
    candidate = request_id.strip()
    if not candidate:
        raise ValueError("request_id must not be empty")
    return candidate


def _connect() -> psycopg.Connection[Any]:
    return psycopg.connect(_postgres_url(), connect_timeout=3, row_factory=dict_row)


def _fetch_all(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def _fetch_one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    rows = _fetch_all(sql, params)
    return rows[0] if rows else None


def _parse_started_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _sort_runs_by_started_at_desc(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(row: dict[str, Any]) -> tuple[int, float, str]:
        parsed = _parse_started_at(row.get("started_at"))
        if parsed is None:
            return (1, 0.0, str(row.get("run_id", "")))
        return (0, -parsed.timestamp(), str(row.get("run_id", "")))

    return sorted(rows, key=sort_key)


def _iter_run_dirs() -> list[Path]:
    if not RUNS_ROOT.exists():
        return []
    return sorted([path for path in RUNS_ROOT.iterdir() if path.is_dir()], reverse=True)


def _find_run_dirs(run_id: str) -> list[Path]:
    matches = []
    for run_dir in _iter_run_dirs():
        if run_dir.name == run_id or run_dir.name.endswith(f"_{run_id}"):
            matches.append(run_dir)
    return sorted(matches, key=lambda path: path.name)


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _eval_observability_assets() -> dict[str, Any]:
    dashboard_files = (
        sorted(_display_path(path) for path in EVAL_GRAFANA_DASHBOARDS_DIR.glob("*.json"))
        if EVAL_GRAFANA_DASHBOARDS_DIR.exists()
        else []
    )
    provisioning_files = (
        sorted(_display_path(path) for path in EVAL_GRAFANA_PROVISIONING_DIR.rglob("*.y*ml"))
        if EVAL_GRAFANA_PROVISIONING_DIR.exists()
        else []
    )
    return {
        "dashboards_root": (
            _display_path(EVAL_GRAFANA_DASHBOARDS_DIR) if EVAL_GRAFANA_DASHBOARDS_DIR.exists() else None
        ),
        "provisioning_root": (
            _display_path(EVAL_GRAFANA_PROVISIONING_DIR) if EVAL_GRAFANA_PROVISIONING_DIR.exists() else None
        ),
        "dashboard_files": dashboard_files,
        "provisioning_files": provisioning_files,
        "dashboard_roles": [
            {
                "path": "Measurement/evals/grafana/dashboards/eval_usage_overview.json",
                "role": "usage",
                "purpose": "Request-level token usage and run volume overview for recent eval traffic.",
            },
            {
                "path": "Measurement/evals/grafana/dashboards/eval_runs.json",
                "role": "run",
                "purpose": "Batch eval run comparison backed by request_run_summaries rows.",
            },
        ],
    }


def _run_manifest_path(run_dir: Path) -> Path:
    return run_dir / "run_manifest.json"


def _run_report_path(run_dir: Path) -> Path:
    return run_dir / "run_report.md"


def _resolve_single_run_dir(run_id: str) -> Path:
    matches = _find_run_dirs(run_id)
    if not matches:
        raise FileNotFoundError(f"run artifact directory not found for run_id={run_id}")
    if len(matches) > 1:
        raise RuntimeError(f"multiple artifact directories found for run_id={run_id}")
    return matches[0]


def _load_manifest(run_id: str) -> dict[str, Any]:
    run_dir = _resolve_single_run_dir(run_id)
    manifest_path = _run_manifest_path(run_dir)
    if not manifest_path.is_file():
        raise FileNotFoundError(f"run manifest missing for run_id={run_id}")
    manifest = _read_json(manifest_path)
    manifest["_artifact_dir"] = _display_path(run_dir)
    manifest["_manifest_path"] = _display_path(manifest_path)
    report_path = _run_report_path(run_dir)
    manifest["_report_exists"] = report_path.is_file()
    if report_path.is_file():
        manifest["_report_path"] = _display_path(report_path)
    return manifest


def _load_report_text(run_id: str) -> dict[str, Any]:
    run_dir = _resolve_single_run_dir(run_id)
    report_path = _run_report_path(run_dir)
    if not report_path.is_file():
        return {
            "ok": True,
            "run_id": run_id,
            "found": False,
            "artifact_dir": _display_path(run_dir),
            "report_path": _display_path(report_path),
            "text": None,
            "eval_observability_assets": _eval_observability_assets(),
        }
    return {
        "ok": True,
        "run_id": run_id,
        "found": True,
        "artifact_dir": _display_path(run_dir),
        "report_path": _display_path(report_path),
        "text": report_path.read_text(encoding="utf-8"),
        "eval_observability_assets": _eval_observability_assets(),
    }


def _run_db_summary(run_id: str) -> dict[str, Any]:
    generation_rows = _fetch_one(
        """
        select
            count(*)::bigint as row_count,
            count(distinct request_id)::bigint as request_count
        from judge_generation_results
        where run_id = %s
        """,
        (run_id,),
    ) or {"row_count": 0, "request_count": 0}
    retrieval_rows = _fetch_one(
        """
        select
            count(*)::bigint as row_count,
            count(distinct request_id)::bigint as request_count
        from judge_retrieval_results
        where run_id = %s
        """,
        (run_id,),
    ) or {"row_count": 0, "request_count": 0}
    generation_suites = _fetch_all(
        """
        select suite_name::text as suite_name, count(*)::bigint as row_count
        from judge_generation_results
        where run_id = %s
        group by suite_name
        order by suite_name
        """,
        (run_id,),
    )
    retrieval_suites = _fetch_all(
        """
        select suite_name::text as suite_name, count(*)::bigint as row_count
        from judge_retrieval_results
        where run_id = %s
        group by suite_name
        order by suite_name
        """,
        (run_id,),
    )
    requests = _fetch_all(
        """
        with generation_counts as (
            select request_id, count(*)::bigint as generation_row_count
            from judge_generation_results
            where run_id = %s
            group by request_id
        ),
        retrieval_counts as (
            select request_id, count(*)::bigint as retrieval_row_count
            from judge_retrieval_results
            where run_id = %s
            group by request_id
        ),
        run_requests as (
            select
                coalesce(g.request_id, r.request_id) as request_id,
                coalesce(g.generation_row_count, 0) as generation_row_count,
                coalesce(r.retrieval_row_count, 0) as retrieval_row_count
            from generation_counts g
            full outer join retrieval_counts r using (request_id)
        )
        select
            rr.request_id,
            rr.generation_row_count,
            rr.retrieval_row_count,
            eps.status::text as eval_status,
            eps.current_stage::text as current_stage,
            rc.trace_id,
            rc.normalized_query,
            rc.received_at
        from run_requests rr
        left join eval_processing_state eps on eps.request_id = rr.request_id
        left join request_captures rc on rc.request_id = rr.request_id
        order by rc.received_at desc nulls last, rr.request_id
        """,
        (run_id, run_id),
    )
    return {
        "generation_rows": generation_rows,
        "retrieval_rows": retrieval_rows,
        "generation_suites": generation_suites,
        "retrieval_suites": retrieval_suites,
        "requests": requests,
    }


def _summarize_run(run_id: str) -> dict[str, Any]:
    db = _run_db_summary(run_id)
    manifest = None
    manifest_error = None
    try:
        manifest = _load_manifest(run_id)
    except Exception as exc:
        manifest_error = {
            "error_type": exc.__class__.__name__,
            "error": str(exc),
        }
    requests = db["requests"]
    db_summary = {
        "generation_row_count": db["generation_rows"]["row_count"],
        "generation_request_count": db["generation_rows"]["request_count"],
        "retrieval_row_count": db["retrieval_rows"]["row_count"],
        "retrieval_request_count": db["retrieval_rows"]["request_count"],
        "generation_suites": db["generation_suites"],
        "retrieval_suites": db["retrieval_suites"],
        "request_count_from_db": len(requests),
        "requests_with_failed_state": sum(1 for row in requests if row.get("eval_status") == "failed"),
        "requests_with_completed_state": sum(1 for row in requests if row.get("eval_status") == "completed"),
        "requests_with_pending_state": sum(1 for row in requests if row.get("eval_status") == "pending"),
    }
    cross_run_diagnostics = _cross_run_scope_diagnostics(run_id, manifest, db_summary)
    return {
        "ok": True,
        "run_id": run_id,
        "manifest": manifest,
        "manifest_found": manifest is not None,
        "manifest_error": manifest_error,
        "artifact_dir": manifest.get("_artifact_dir") if isinstance(manifest, dict) else None,
        "report_exists": manifest.get("_report_exists") if isinstance(manifest, dict) else False,
        "db_summary": db_summary,
        "cross_run_diagnostics": cross_run_diagnostics,
        "request_preview": requests[:10],
        "eval_observability_assets": _eval_observability_assets(),
    }


def _comparison_manifest_view(summary: dict[str, Any]) -> dict[str, Any]:
    manifest = summary.get("manifest")
    if isinstance(manifest, dict):
        return {
            "found": True,
            "status": manifest.get("status"),
            "run_type": manifest.get("run_type"),
            "judge_model": manifest.get("judge_model"),
            "request_count": manifest.get("request_count"),
            "generation_suite_versions": manifest.get("generation_suite_versions"),
            "retrieval_suite_versions": manifest.get("retrieval_suite_versions"),
            "started_at": manifest.get("started_at"),
        }
    return {
        "found": False,
        "status": None,
        "run_type": None,
        "judge_model": None,
        "request_count": None,
        "generation_suite_versions": None,
        "retrieval_suite_versions": None,
        "started_at": None,
        "manifest_error": summary.get("manifest_error"),
    }


def _manifest_scope_index(manifest: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(manifest, dict):
        return {}
    request_ids = manifest.get("run_scope_request_ids")
    if not isinstance(request_ids, list):
        return {}
    index: dict[str, dict[str, Any]] = {}
    for request_id in request_ids:
        if isinstance(request_id, str) and request_id:
            index[request_id] = {
                "request_id": request_id,
                "generation_row_count": 0,
                "retrieval_row_count": 0,
                "eval_status": None,
                "current_stage": None,
                "trace_id": None,
                "normalized_query": None,
                "received_at": None,
            }
    return index


def _request_metric_index(rows: list[dict[str, Any]], suite_name: str) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("suite_name") != suite_name:
            continue
        request_id = row.get("request_id")
        if not isinstance(request_id, str):
            continue
        index[request_id] = row
    return index


def _cross_run_scope_diagnostics(
    run_id: str,
    manifest: dict[str, Any] | None,
    db_summary: dict[str, Any],
) -> dict[str, Any] | None:
    if not isinstance(manifest, dict):
        return None
    request_ids = manifest.get("run_scope_request_ids")
    if not isinstance(request_ids, list) or not request_ids:
        return None

    scope_request_ids = [request_id for request_id in request_ids if isinstance(request_id, str) and request_id]
    if not scope_request_ids:
        return None

    other_generation_runs = _fetch_all(
        """
        select
            run_id,
            count(*)::bigint as row_count,
            count(distinct request_id)::bigint as request_count
        from judge_generation_results
        where request_id = any(%s)
          and run_id <> %s
        group by run_id
        order by request_count desc, row_count desc, run_id asc
        """,
        (scope_request_ids, run_id),
    )
    other_retrieval_runs = _fetch_all(
        """
        select
            run_id,
            count(*)::bigint as row_count,
            count(distinct request_id)::bigint as request_count
        from judge_retrieval_results
        where request_id = any(%s)
          and run_id <> %s
        group by run_id
        order by request_count desc, row_count desc, run_id asc
        """,
        (scope_request_ids, run_id),
    )

    matching_generation_runs = [
        row for row in other_generation_runs if row.get("request_count") == len(scope_request_ids)
    ]
    likely_split_run_scope = (
        db_summary.get("generation_row_count", 0) == 0
        and db_summary.get("retrieval_row_count", 0) > 0
        and bool(matching_generation_runs)
    )
    notes = []
    if likely_split_run_scope:
        notes.append(
            "Current run has retrieval rows but no generation rows, while the same frozen request scope has generation rows under a different run_id."
        )
    return {
        "scope_request_count": len(scope_request_ids),
        "other_generation_runs": other_generation_runs[:10],
        "other_retrieval_runs": other_retrieval_runs[:10],
        "matching_generation_runs": matching_generation_runs[:10],
        "likely_split_run_scope": likely_split_run_scope,
        "notes": notes,
    }


@mcp.tool
def list_recent_runs(limit: int = 20) -> dict[str, Any]:
    """Return recent run manifests discovered under Evidence/evals/runs."""
    try:
        limit = _validate_limit(limit)
        rows = []
        for run_dir in _iter_run_dirs():
            manifest_path = _run_manifest_path(run_dir)
            if not manifest_path.is_file():
                continue
            try:
                manifest = _read_json(manifest_path)
            except Exception:
                continue
            rows.append(
                {
                    "run_id": manifest.get("run_id"),
                    "run_type": manifest.get("run_type"),
                    "status": manifest.get("status"),
                    "started_at": manifest.get("started_at"),
                    "completed_at": manifest.get("completed_at"),
                    "request_count": manifest.get("request_count"),
                    "judge_model": manifest.get("judge_model"),
                    "artifact_dir": _display_path(run_dir),
                    "report_exists": _run_report_path(run_dir).is_file(),
                }
            )
        rows = _sort_runs_by_started_at_desc(rows)[:limit]
        return {
            "ok": True,
            "limit": limit,
            "runs": rows,
            "count": len(rows),
            "eval_observability_assets": _eval_observability_assets(),
        }
    except Exception as exc:
        return _tool_error_payload("list_recent_runs", exc, limit=limit)


@mcp.tool
def get_run_manifest(run_id: str) -> dict[str, Any]:
    """Return one run_manifest.json artifact by run_id."""
    try:
        run_id = _validate_run_id(run_id)
        manifest = _load_manifest(run_id)
        return {
            "ok": True,
            "run_id": run_id,
            "manifest": manifest,
            "found": True,
            "eval_observability_assets": _eval_observability_assets(),
        }
    except Exception as exc:
        return _tool_error_payload("get_run_manifest", exc, run_id=run_id)


@mcp.tool
def get_run_report(run_id: str) -> dict[str, Any]:
    """Return one run_report.md artifact by run_id when present."""
    try:
        run_id = _validate_run_id(run_id)
        return _load_report_text(run_id)
    except Exception as exc:
        return _tool_error_payload("get_run_report", exc, run_id=run_id)


@mcp.tool
def summarize_run(run_id: str) -> dict[str, Any]:
    """Return combined artifact and DB summary for one run_id."""
    try:
        run_id = _validate_run_id(run_id)
        return _summarize_run(run_id)
    except PsycopgError as exc:
        return _db_error_payload("summarize_run", exc, run_id=run_id)
    except Exception as exc:
        return _tool_error_payload("summarize_run", exc, run_id=run_id)


@mcp.tool
def compare_runs(run_a: str, run_b: str) -> dict[str, Any]:
    """Return a compact comparison between two run_ids."""
    try:
        run_a = _validate_run_id(run_a)
        run_b = _validate_run_id(run_b)
        summary_a = _summarize_run(run_a)
        summary_b = _summarize_run(run_b)
        if not summary_a.get("ok", False):
            return summary_a
        if not summary_b.get("ok", False):
            return summary_b

        manifest_a = _comparison_manifest_view(summary_a)
        manifest_b = _comparison_manifest_view(summary_b)
        db_a = summary_a["db_summary"]
        db_b = summary_b["db_summary"]
        cross_run_diag_a = summary_a.get("cross_run_diagnostics")
        cross_run_diag_b = summary_b.get("cross_run_diagnostics")
        request_ids_a = set(summary_a.get("manifest", {}).get("run_scope_request_ids", [])) if isinstance(summary_a.get("manifest"), dict) else set()
        request_ids_b = set(summary_b.get("manifest", {}).get("run_scope_request_ids", [])) if isinstance(summary_b.get("manifest"), dict) else set()
        notes = []
        if not (manifest_a.get("found") and manifest_b.get("found")):
            notes.append("One or both manifests are missing; request-scope diff is incomplete and DB-backed counts are primary.")
        if isinstance(cross_run_diag_a, dict) and cross_run_diag_a.get("likely_split_run_scope"):
            notes.append(f"run_a appears split across run_ids; generation rows for its frozen scope likely live under a different run_id than {run_a}.")
        if isinstance(cross_run_diag_b, dict) and cross_run_diag_b.get("likely_split_run_scope"):
            notes.append(f"run_b appears split across run_ids; generation rows for its frozen scope likely live under a different run_id than {run_b}.")

        return {
            "ok": True,
            "run_a": run_a,
            "run_b": run_b,
            "manifest_diff": {
                "status": [manifest_a.get("status"), manifest_b.get("status")],
                "run_type": [manifest_a.get("run_type"), manifest_b.get("run_type")],
                "judge_model": [manifest_a.get("judge_model"), manifest_b.get("judge_model")],
                "request_count": [manifest_a.get("request_count"), manifest_b.get("request_count")],
                "generation_suite_versions": [
                    manifest_a.get("generation_suite_versions"),
                    manifest_b.get("generation_suite_versions"),
                ],
                "retrieval_suite_versions": [
                    manifest_a.get("retrieval_suite_versions"),
                    manifest_b.get("retrieval_suite_versions"),
                ],
                "manifest_found": [manifest_a.get("found"), manifest_b.get("found")],
                "started_at": [manifest_a.get("started_at"), manifest_b.get("started_at")],
            },
            "db_diff": {
                "generation_row_count": [db_a["generation_row_count"], db_b["generation_row_count"]],
                "retrieval_row_count": [db_a["retrieval_row_count"], db_b["retrieval_row_count"]],
                "requests_with_failed_state": [db_a["requests_with_failed_state"], db_b["requests_with_failed_state"]],
                "requests_with_completed_state": [
                    db_a["requests_with_completed_state"],
                    db_b["requests_with_completed_state"],
                ],
                "requests_with_pending_state": [db_a["requests_with_pending_state"], db_b["requests_with_pending_state"]],
            },
            "request_scope_diff": {
                "shared_request_count": len(request_ids_a & request_ids_b),
                "only_in_run_a_count": len(request_ids_a - request_ids_b),
                "only_in_run_b_count": len(request_ids_b - request_ids_a),
                "only_in_run_a": sorted(request_ids_a - request_ids_b)[:20],
                "only_in_run_b": sorted(request_ids_b - request_ids_a)[:20],
            },
            "cross_run_diagnostics": {
                "run_a": cross_run_diag_a,
                "run_b": cross_run_diag_b,
            },
            "notes": notes,
        }
    except PsycopgError as exc:
        return _db_error_payload("compare_runs", exc, run_a=run_a, run_b=run_b)
    except Exception as exc:
        return _tool_error_payload("compare_runs", exc, run_a=run_a, run_b=run_b)


@mcp.tool
def find_runs_for_request(request_id: str, limit: int = 20) -> dict[str, Any]:
    """Return run_ids in which one request_id appears, with lightweight coverage info."""
    try:
        request_id = _validate_request_id(request_id)
        limit = _validate_limit(limit)
        rows = _fetch_all(
            """
            with generation_runs as (
                select run_id, count(*)::bigint as generation_row_count
                from judge_generation_results
                where request_id = %s
                group by run_id
            ),
            retrieval_runs as (
                select run_id, count(*)::bigint as retrieval_row_count
                from judge_retrieval_results
                where request_id = %s
                group by run_id
            ),
            merged as (
                select
                    coalesce(g.run_id, r.run_id) as run_id,
                    coalesce(g.generation_row_count, 0) as generation_row_count,
                    coalesce(r.retrieval_row_count, 0) as retrieval_row_count
                from generation_runs g
                full outer join retrieval_runs r using (run_id)
            )
            select *
            from merged
            order by run_id desc
            """,
            (request_id, request_id),
        )
        enriched = []
        for row in rows:
            try:
                manifest = _load_manifest(row["run_id"])
                row = {
                    **row,
                    "run_status": manifest.get("status"),
                    "run_type": manifest.get("run_type"),
                    "started_at": manifest.get("started_at"),
                    "judge_model": manifest.get("judge_model"),
                }
            except Exception:
                pass
            enriched.append(row)
        enriched = _sort_runs_by_started_at_desc(enriched)
        return {
            "ok": True,
            "request_id": request_id,
            "runs": enriched[:limit],
            "count": min(len(enriched), limit),
        }
    except PsycopgError as exc:
        return _db_error_payload("find_runs_for_request", exc, request_id=request_id, limit=limit)
    except Exception as exc:
        return _tool_error_payload("find_runs_for_request", exc, request_id=request_id, limit=limit)


@mcp.tool
def compare_request_across_runs(request_id: str, run_a: str, run_b: str) -> dict[str, Any]:
    """Return request-level generation/retrieval row diff for one request_id across two runs."""
    try:
        request_id = _validate_request_id(request_id)
        run_a = _validate_run_id(run_a)
        run_b = _validate_run_id(run_b)
        generation = _fetch_all(
            """
            select
                run_id,
                suite_name::text as suite_name,
                score,
                label,
                trace_id,
                created_at
            from judge_generation_results
            where request_id = %s and run_id = any(%s)
            order by run_id, suite_name
            """,
            (request_id, [run_a, run_b]),
        )
        retrieval = _fetch_all(
            """
            select
                run_id,
                chunk_id,
                retrieval_rank,
                retrieval_score,
                selected_for_generation,
                suite_name::text as suite_name,
                score,
                label,
                trace_id,
                created_at
            from judge_retrieval_results
            where request_id = %s and run_id = any(%s)
            order by run_id, retrieval_rank, chunk_id
            """,
            (request_id, [run_a, run_b]),
        )
        return {
            "ok": True,
            "request_id": request_id,
            "run_a": run_a,
            "run_b": run_b,
            "generation_rows": generation,
            "retrieval_rows": retrieval,
            "generation_row_count": len(generation),
            "retrieval_row_count": len(retrieval),
            "note": "request_summaries is intentionally omitted here because it is not run-scoped",
        }
    except PsycopgError as exc:
        return _db_error_payload(
            "compare_request_across_runs",
            exc,
            request_id=request_id,
            run_a=run_a,
            run_b=run_b,
        )
    except Exception as exc:
        return _tool_error_payload(
            "compare_request_across_runs",
            exc,
            request_id=request_id,
            run_a=run_a,
            run_b=run_b,
        )


@mcp.tool
def get_run_request_matrix(run_id: str) -> dict[str, Any]:
    """Return per-request row coverage and stage/status for one run_id."""
    try:
        run_id = _validate_run_id(run_id)
        manifest = None
        try:
            manifest = _load_manifest(run_id)
        except Exception:
            manifest = None
        rows = _fetch_all(
            """
            with generation_counts as (
                select request_id, count(*)::bigint as generation_row_count
                from judge_generation_results
                where run_id = %s
                group by request_id
            ),
            retrieval_counts as (
                select request_id, count(*)::bigint as retrieval_row_count
                from judge_retrieval_results
                where run_id = %s
                group by request_id
            )
            select
                coalesce(g.request_id, r.request_id, rc.request_id) as request_id,
                coalesce(g.generation_row_count, 0) as generation_row_count,
                coalesce(r.retrieval_row_count, 0) as retrieval_row_count,
                eps.status::text as eval_status,
                eps.current_stage::text as current_stage,
                rc.trace_id,
                rc.normalized_query,
                rc.reranker_kind,
                rc.received_at
            from generation_counts g
            full outer join retrieval_counts r using (request_id)
            full outer join request_captures rc on rc.request_id = coalesce(g.request_id, r.request_id)
            left join eval_processing_state eps on eps.request_id = rc.request_id
            order by rc.received_at desc nulls last, request_id
            """,
            (run_id, run_id),
        )
        row_index = _manifest_scope_index(manifest)
        for row in rows:
            request_id = row.get("request_id")
            if not isinstance(request_id, str) or not request_id:
                continue
            if request_id in row_index:
                row_index[request_id].update(row)
            else:
                row_index[request_id] = row
        merged_rows = list(row_index.values()) if row_index else rows
        merged_rows.sort(
            key=lambda row: (
                row.get("received_at") is not None,
                row.get("received_at") or "",
                row.get("request_id") or "",
            ),
            reverse=True,
        )
        return {
            "ok": True,
            "run_id": run_id,
            "rows": merged_rows,
            "count": len(merged_rows),
            "note": "request_summaries is intentionally omitted here because it is not run-scoped",
            "manifest_scope_used": manifest is not None and bool(_manifest_scope_index(manifest)),
        }
    except PsycopgError as exc:
        return _db_error_payload("get_run_request_matrix", exc, run_id=run_id)
    except Exception as exc:
        return _tool_error_payload("get_run_request_matrix", exc, run_id=run_id)


@mcp.tool
def get_run_artifact_health(run_id: str) -> dict[str, Any]:
    """Return manifest/report presence and lightweight artifact consistency checks for one run_id."""
    try:
        run_id = _validate_run_id(run_id)
        run_dir = _resolve_single_run_dir(run_id)
        manifest_path = _run_manifest_path(run_dir)
        report_path = _run_report_path(run_dir)
        manifest = _read_json(manifest_path) if manifest_path.is_file() else None
        db_error = None
        cross_run_diagnostics = None
        try:
            db = _run_db_summary(run_id)
            db_summary = {
                "generation_row_count": db["generation_rows"]["row_count"],
                "generation_request_count": db["generation_rows"]["request_count"],
                "retrieval_row_count": db["retrieval_rows"]["row_count"],
                "retrieval_request_count": db["retrieval_rows"]["request_count"],
            }
            cross_run_diagnostics = _cross_run_scope_diagnostics(run_id, manifest, db_summary)
        except PsycopgError as exc:
            db_error = {
                "error_type": exc.__class__.__name__,
                "error": str(exc),
                "postgres_url": _redact_url(_postgres_url()),
            }

        checks = {
            "artifact_dir_exists": run_dir.is_dir(),
            "manifest_exists": manifest_path.is_file(),
            "report_exists": report_path.is_file(),
            "manifest_run_id_matches": isinstance(manifest, dict) and manifest.get("run_id") == run_id,
            "manifest_request_count_matches_scope": (
                isinstance(manifest, dict)
                and manifest.get("request_count") == len(manifest.get("run_scope_request_ids", []))
            ),
            "manifest_completed_at_consistent": (
                not isinstance(manifest, dict)
                or (
                    manifest.get("status") == "running"
                    and "completed_at" not in manifest
                )
                or (
                    manifest.get("status") in {"completed", "failed"}
                    and isinstance(manifest.get("completed_at"), str)
                )
            ),
        }
        if db_error is None:
            checks["cross_run_scope_consistent"] = (
                cross_run_diagnostics is None or not cross_run_diagnostics.get("likely_split_run_scope", False)
            )
        return {
            "ok": True,
            "run_id": run_id,
            "artifact_dir": _display_path(run_dir),
            "manifest_path": _display_path(manifest_path),
            "report_path": _display_path(report_path),
            "checks": checks,
            "db_error": db_error,
            "cross_run_diagnostics": cross_run_diagnostics,
            "healthy": all(checks.values()),
            "eval_observability_assets": _eval_observability_assets(),
        }
    except Exception as exc:
        return _tool_error_payload("get_run_artifact_health", exc, run_id=run_id)


@mcp.tool
def get_run_regressions(run_a: str, run_b: str, limit: int = 20) -> dict[str, Any]:
    """Return opinionated regression candidates where run_b looks worse than run_a."""
    try:
        run_a = _validate_run_id(run_a)
        run_b = _validate_run_id(run_b)
        limit = _validate_limit(limit)
        rows = _fetch_all(
            """
            with generation as (
                select
                    request_id,
                    run_id,
                    suite_name::text as suite_name,
                    score,
                    label
                from judge_generation_results
                where run_id = any(%s)
            ),
            paired_generation as (
                select
                    coalesce(a.request_id, b.request_id) as request_id,
                    coalesce(a.suite_name, b.suite_name) as suite_name,
                    a.score as score_a,
                    b.score as score_b,
                    a.label as label_a,
                    b.label as label_b
                from (
                    select * from generation where run_id = %s
                ) a
                full outer join (
                    select * from generation where run_id = %s
                ) b
                using (request_id, suite_name)
            ),
            retrieval_weighted as (
                select
                    run_id,
                    request_id,
                    case
                        when sum(1.0 / retrieval_rank) = 0 then null
                        else sum(score * (1.0 / retrieval_rank)) / sum(1.0 / retrieval_rank)
                    end as weighted_score
                from judge_retrieval_results
                where run_id = any(%s)
                group by run_id, request_id
            ),
            paired_retrieval as (
                select
                    coalesce(a.request_id, b.request_id) as request_id,
                    a.weighted_score as retrieval_weighted_a,
                    b.weighted_score as retrieval_weighted_b
                from (
                    select * from retrieval_weighted where run_id = %s
                ) a
                full outer join (
                    select * from retrieval_weighted where run_id = %s
                ) b
                using (request_id)
            )
            select
                pg.request_id,
                pg.suite_name,
                pg.score_a,
                pg.score_b,
                pg.label_a,
                pg.label_b,
                pr.retrieval_weighted_a,
                pr.retrieval_weighted_b,
                rc.trace_id,
                rc.normalized_query
            from paired_generation pg
            left join paired_retrieval pr using (request_id)
            left join request_captures rc on rc.request_id = pg.request_id
            where pg.score_a is not null
              and (pg.score_b is null or pg.score_b < pg.score_a)
            order by
                case when pg.score_b is null then 1 else 0 end desc,
                (pg.score_a - pg.score_b) desc nulls last,
                pg.request_id,
                pg.suite_name
            limit %s
            """,
            ([run_a, run_b], run_a, run_b, [run_a, run_b], run_a, run_b, limit),
        )
        for row in rows:
            if row.get("score_b") is None:
                row["regression_kind"] = "missing_in_run_b"
                row["score_delta"] = None
            else:
                row["regression_kind"] = "score_drop"
                row["score_delta"] = row["score_a"] - row["score_b"]
        return {
            "ok": True,
            "run_a": run_a,
            "run_b": run_b,
            "limit": limit,
            "regressions": rows,
            "count": len(rows),
            "note": "Current strong-MVP regressions are generation regressions: either score drops or generation rows missing in run_b, with retrieval weighted context when available.",
        }
    except PsycopgError as exc:
        return _db_error_payload("get_run_regressions", exc, run_a=run_a, run_b=run_b, limit=limit)
    except Exception as exc:
        return _tool_error_payload("get_run_regressions", exc, run_a=run_a, run_b=run_b, limit=limit)


if __name__ == "__main__":
    mcp.run()

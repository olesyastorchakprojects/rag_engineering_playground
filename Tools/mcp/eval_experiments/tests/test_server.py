from __future__ import annotations

from datetime import datetime, timezone
from psycopg import Error as PsycopgError

from Tools.mcp.eval_experiments import server


def test_validate_limit_caps_large_values() -> None:
    assert server._validate_limit(500) == 100


def test_find_run_dirs_matches_timestamped_and_plain_dirs(monkeypatch) -> None:
    class DummyPath:
        def __init__(self, name: str) -> None:
            self.name = name

        def is_dir(self) -> bool:
            return True

    monkeypatch.setattr(
        server,
        "_iter_run_dirs",
        lambda: [
            DummyPath("2026-03-27T20-20-11.888460+00-00_d3662912-5aae-4fad-9130-611591e39ba3"),
            DummyPath("d3662912-5aae-4fad-9130-611591e39ba3"),
        ],
    )
    matches = server._find_run_dirs("d3662912-5aae-4fad-9130-611591e39ba3")
    assert len(matches) == 2


def test_tool_error_payload_shape() -> None:
    payload = server._tool_error_payload("demo", ValueError("bad input"), run_id="x")
    assert payload["ok"] is False
    assert payload["operation"] == "demo"
    assert payload["error_type"] == "ValueError"
    assert payload["context"]["run_id"] == "x"


def test_sort_runs_by_started_at_desc_prefers_newer_timestamp() -> None:
    rows = [
        {"run_id": "older", "started_at": "2026-03-27T19:00:00+00:00"},
        {"run_id": "newer", "started_at": "2026-03-27T20:00:00+00:00"},
    ]
    sorted_rows = server._sort_runs_by_started_at_desc(rows)
    assert [row["run_id"] for row in sorted_rows] == ["newer", "older"]


def test_sort_runs_by_started_at_desc_handles_naive_and_missing_timestamps() -> None:
    rows = [
        {"run_id": "missing", "started_at": None},
        {"run_id": "naive", "started_at": "2026-03-27T19:00:00"},
        {"run_id": "aware", "started_at": "2026-03-27T20:00:00+00:00"},
    ]
    sorted_rows = server._sort_runs_by_started_at_desc(rows)
    assert [row["run_id"] for row in sorted_rows] == ["aware", "naive", "missing"]


def test_summarize_run_degrades_without_manifest(monkeypatch) -> None:
    monkeypatch.setattr(server, "_load_manifest", lambda run_id: (_ for _ in ()).throw(FileNotFoundError("missing manifest")))
    monkeypatch.setattr(
        server,
        "_run_db_summary",
        lambda run_id: {
            "generation_rows": {"row_count": 4, "request_count": 1},
            "retrieval_rows": {"row_count": 4, "request_count": 1},
            "generation_suites": [],
            "retrieval_suites": [],
            "requests": [],
        },
    )
    result = server._summarize_run("run-1")
    assert result["ok"] is True
    assert result["manifest_found"] is False
    assert result["manifest_error"]["error_type"] == "FileNotFoundError"
    assert result["db_summary"]["generation_row_count"] == 4


def test_summarize_run_detects_cross_run_scope_mismatch(monkeypatch) -> None:
    monkeypatch.setattr(
        server,
        "_run_db_summary",
        lambda run_id: {
            "generation_rows": {"row_count": 0, "request_count": 0},
            "retrieval_rows": {"row_count": 8, "request_count": 2},
            "generation_suites": [],
            "retrieval_suites": [{"suite_name": "retrieval_relevance", "row_count": 8}],
            "requests": [],
        },
    )
    monkeypatch.setattr(
        server,
        "_load_manifest",
        lambda run_id: {"run_id": run_id, "run_scope_request_ids": ["req-1", "req-2"]},
    )
    calls = iter(
        [
            [{"run_id": "prior-run", "row_count": 8, "request_count": 2}],
            [],
        ]
    )
    monkeypatch.setattr(server, "_fetch_all", lambda sql, params=(): next(calls))
    result = server._summarize_run("run-1")
    assert result["ok"] is True
    assert result["cross_run_diagnostics"]["likely_split_run_scope"] is True
    assert result["cross_run_diagnostics"]["other_generation_runs"][0]["run_id"] == "prior-run"


def test_summarize_run_avoids_false_split_scope_on_partial_overlap(monkeypatch) -> None:
    monkeypatch.setattr(
        server,
        "_run_db_summary",
        lambda run_id: {
            "generation_rows": {"row_count": 0, "request_count": 0},
            "retrieval_rows": {"row_count": 8, "request_count": 2},
            "generation_suites": [],
            "retrieval_suites": [{"suite_name": "retrieval_relevance", "row_count": 8}],
            "requests": [],
        },
    )
    monkeypatch.setattr(
        server,
        "_load_manifest",
        lambda run_id: {"run_id": run_id, "run_scope_request_ids": ["req-1", "req-2", "req-3"]},
    )
    calls = iter(
        [
            [{"run_id": "prior-run", "row_count": 8, "request_count": 2}],
            [],
        ]
    )
    monkeypatch.setattr(server, "_fetch_all", lambda sql, params=(): next(calls))
    result = server._summarize_run("run-1")
    assert result["ok"] is True
    assert result["cross_run_diagnostics"]["likely_split_run_scope"] is False
    assert result["cross_run_diagnostics"]["matching_generation_runs"] == []


def test_compare_request_across_runs_omits_request_summary(monkeypatch) -> None:
    monkeypatch.setattr(server, "_fetch_all", lambda sql, params=(): [])
    result = server.compare_request_across_runs("req-1", "run-a", "run-b")
    assert result["ok"] is True
    assert "request_summary" not in result
    assert "not run-scoped" in result["note"]


def test_compare_runs_surfaces_cross_run_scope_diagnostics(monkeypatch) -> None:
    summaries = {
        "run-a": {
            "ok": True,
            "manifest": {"run_scope_request_ids": ["req-1"]},
            "db_summary": {
                "generation_row_count": 4,
                "retrieval_row_count": 4,
                "requests_with_failed_state": 0,
                "requests_with_completed_state": 1,
                "requests_with_pending_state": 0,
            },
            "cross_run_diagnostics": None,
        },
        "run-b": {
            "ok": True,
            "manifest": {"run_scope_request_ids": ["req-1"]},
            "db_summary": {
                "generation_row_count": 0,
                "retrieval_row_count": 4,
                "requests_with_failed_state": 1,
                "requests_with_completed_state": 0,
                "requests_with_pending_state": 0,
            },
            "cross_run_diagnostics": {
                "likely_split_run_scope": True,
                "other_generation_runs": [{"run_id": "prior-run", "row_count": 4, "request_count": 1}],
                "other_retrieval_runs": [],
                "notes": ["split scope"],
            },
        },
    }
    monkeypatch.setattr(server, "_summarize_run", lambda run_id: summaries[run_id])
    monkeypatch.setattr(
        server,
        "_comparison_manifest_view",
        lambda summary: {
            "found": True,
            "status": "failed",
            "run_type": "experiment",
            "judge_model": "m1",
            "request_count": 1,
            "generation_suite_versions": {},
            "retrieval_suite_versions": {},
            "started_at": "2026-03-27T20:00:00+00:00",
        },
    )
    result = server.compare_runs("run-a", "run-b")
    assert result["ok"] is True
    assert result["cross_run_diagnostics"]["run_b"]["likely_split_run_scope"] is True
    assert any("run_b appears split across run_ids" in note for note in result["notes"])


def test_find_runs_for_request_sorts_by_started_at(monkeypatch) -> None:
    monkeypatch.setattr(
        server,
        "_fetch_all",
        lambda sql, params=(): [
            {"run_id": "run-old", "generation_row_count": 1, "retrieval_row_count": 1},
            {"run_id": "run-new", "generation_row_count": 1, "retrieval_row_count": 1},
        ],
    )
    manifests = {
        "run-old": {"status": "completed", "run_type": "experiment", "started_at": "2026-03-27T19:00:00+00:00", "judge_model": "m1"},
        "run-new": {"status": "completed", "run_type": "experiment", "started_at": "2026-03-27T20:00:00+00:00", "judge_model": "m1"},
    }
    monkeypatch.setattr(server, "_load_manifest", lambda run_id: manifests[run_id])
    result = server.find_runs_for_request("req-1")
    assert result["ok"] is True
    assert [row["run_id"] for row in result["runs"]] == ["run-new", "run-old"]


def test_get_run_artifact_health_checks_request_count_vs_scope(monkeypatch, tmp_path) -> None:
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    manifest_path = run_dir / "run_manifest.json"
    manifest_path.write_text(
        '{"run_id":"run-1","status":"failed","request_count":2,"run_scope_request_ids":["a"],"completed_at":"2026-03-27T20:25:10+00:00"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(server, "_resolve_single_run_dir", lambda run_id: run_dir)
    result = server.get_run_artifact_health("run-1")
    assert result["ok"] is True
    assert result["checks"]["manifest_request_count_matches_scope"] is False
    assert result["healthy"] is False


def test_get_run_artifact_health_degrades_without_db(monkeypatch, tmp_path) -> None:
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    manifest_path = run_dir / "run_manifest.json"
    manifest_path.write_text(
        '{"run_id":"run-1","status":"failed","request_count":2,"run_scope_request_ids":["req-1","req-2"],"completed_at":"2026-03-27T20:25:10+00:00"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(server, "_resolve_single_run_dir", lambda run_id: run_dir)
    monkeypatch.setattr(server, "_run_db_summary", lambda run_id: (_ for _ in ()).throw(PsycopgError("db down")))
    result = server.get_run_artifact_health("run-1")
    assert result["ok"] is True
    assert result["db_error"]["error_type"] == "Error"
    assert "cross_run_scope_consistent" not in result["checks"]
    assert result["checks"]["artifact_dir_exists"] is True
    assert result["checks"]["manifest_exists"] is True


def test_get_run_artifact_health_flags_cross_run_scope_mismatch(monkeypatch, tmp_path) -> None:
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    manifest_path = run_dir / "run_manifest.json"
    manifest_path.write_text(
        '{"run_id":"run-1","status":"failed","request_count":2,"run_scope_request_ids":["req-1","req-2"],"completed_at":"2026-03-27T20:25:10+00:00"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(server, "_resolve_single_run_dir", lambda run_id: run_dir)
    monkeypatch.setattr(
        server,
        "_run_db_summary",
        lambda run_id: {
            "generation_rows": {"row_count": 0, "request_count": 0},
            "retrieval_rows": {"row_count": 8, "request_count": 2},
            "generation_suites": [],
            "retrieval_suites": [],
            "requests": [],
        },
    )
    calls = iter(
        [
            [{"run_id": "prior-run", "row_count": 8, "request_count": 2}],
            [],
        ]
    )
    monkeypatch.setattr(server, "_fetch_all", lambda sql, params=(): next(calls))
    result = server.get_run_artifact_health("run-1")
    assert result["ok"] is True
    assert result["checks"]["cross_run_scope_consistent"] is False
    assert result["cross_run_diagnostics"]["likely_split_run_scope"] is True
    assert result["healthy"] is False


def test_get_run_request_matrix_omits_request_summaries(monkeypatch) -> None:
    monkeypatch.setattr(
        server,
        "_fetch_all",
        lambda sql, params=(): [
            {
                "request_id": "req-1",
                "generation_row_count": 2,
                "retrieval_row_count": 3,
                "eval_status": "completed",
                "current_stage": "build_request_summary",
                "trace_id": "trace-1",
                "normalized_query": "why",
                "reranker_kind": "Heuristic",
                "received_at": "2026-03-27T20:00:00+00:00",
            }
        ],
    )
    result = server.get_run_request_matrix("run-1")
    assert result["ok"] is True
    assert "not run-scoped" in result["note"]
    assert "has_request_summary" not in result["rows"][0]


def test_get_run_regressions_marks_missing_rows_in_run_b(monkeypatch) -> None:
    monkeypatch.setattr(
        server,
        "_fetch_all",
        lambda sql, params=(): [
            {
                "request_id": "req-1",
                "suite_name": "groundedness",
                "score_a": 1.0,
                "score_b": None,
                "label_a": "pass",
                "label_b": None,
                "retrieval_weighted_a": 0.8,
                "retrieval_weighted_b": None,
                "trace_id": "trace-1",
                "normalized_query": "why",
            }
        ],
    )
    result = server.get_run_regressions("run-a", "run-b")
    assert result["ok"] is True
    assert result["regressions"][0]["regression_kind"] == "missing_in_run_b"
    assert result["regressions"][0]["score_delta"] is None


def test_find_runs_for_request_applies_limit_after_manifest_sort(monkeypatch) -> None:
    monkeypatch.setattr(
        server,
        "_fetch_all",
        lambda sql, params=(): [
            {"run_id": "run-z", "generation_row_count": 1, "retrieval_row_count": 1},
            {"run_id": "run-a", "generation_row_count": 1, "retrieval_row_count": 1},
            {"run_id": "run-m", "generation_row_count": 1, "retrieval_row_count": 1},
        ],
    )
    manifests = {
        "run-z": {"status": "completed", "run_type": "experiment", "started_at": "2026-03-27T19:00:00+00:00", "judge_model": "m1"},
        "run-a": {"status": "completed", "run_type": "experiment", "started_at": "2026-03-27T21:00:00+00:00", "judge_model": "m1"},
        "run-m": {"status": "completed", "run_type": "experiment", "started_at": "2026-03-27T20:00:00+00:00", "judge_model": "m1"},
    }
    monkeypatch.setattr(server, "_load_manifest", lambda run_id: manifests[run_id])
    result = server.find_runs_for_request("req-1", limit=2)
    assert result["ok"] is True
    assert [row["run_id"] for row in result["runs"]] == ["run-a", "run-m"]


def test_get_run_request_matrix_expands_manifest_scope(monkeypatch) -> None:
    monkeypatch.setattr(
        server,
        "_load_manifest",
        lambda run_id: {"run_scope_request_ids": ["req-1", "req-2"]},
    )
    monkeypatch.setattr(
        server,
        "_fetch_all",
        lambda sql, params=(): [
            {
                "request_id": "req-1",
                "generation_row_count": 2,
                "retrieval_row_count": 3,
                "eval_status": "completed",
                "current_stage": "build_request_summary",
                "trace_id": "trace-1",
                "normalized_query": "why",
                "received_at": "2026-03-27T20:00:00+00:00",
            }
        ],
    )
    result = server.get_run_request_matrix("run-1")
    assert result["ok"] is True
    assert result["manifest_scope_used"] is True
    request_ids = [row["request_id"] for row in result["rows"]]
    assert request_ids == ["req-1", "req-2"]
    req2 = result["rows"][1]
    assert req2["generation_row_count"] == 0
    assert req2["retrieval_row_count"] == 0

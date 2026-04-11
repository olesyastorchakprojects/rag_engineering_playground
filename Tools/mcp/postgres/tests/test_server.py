from __future__ import annotations

from unittest.mock import patch

from Tools.mcp.postgres import server
from Tools.mcp.postgres.server import (
    DEFAULT_POSTGRES_URL,
    KNOWN_TABLES,
    _db_error_payload,
    _extract_ok_row,
    _redact_url,
    _validate_limit,
    _validate_query_text,
    _validate_table_name,
)


def test_known_tables_include_request_captures() -> None:
    assert "request_captures" in KNOWN_TABLES
    assert "eval_processing_state" in KNOWN_TABLES
    assert "request_run_summaries" in KNOWN_TABLES
    assert "runtime_run_configs" in KNOWN_TABLES
    assert "eval_run_configs" in KNOWN_TABLES


def test_redact_url_masks_password() -> None:
    redacted = _redact_url(DEFAULT_POSTGRES_URL)
    assert "postgres:***@" in redacted


def test_validate_limit_caps_large_values() -> None:
    assert _validate_limit(500) == 200


def test_validate_table_name_accepts_known_table() -> None:
    assert _validate_table_name("request_captures") == "request_captures"


def test_db_error_payload_is_structured() -> None:
    payload = _db_error_payload("demo", RuntimeError("boom"), request_id="r1")
    assert payload["ok"] is False
    assert payload["operation"] == "demo"
    assert payload["context"]["request_id"] == "r1"


def test_validate_limit_rejects_non_positive() -> None:
    try:
        _validate_limit(0)
    except ValueError as exc:
        assert "limit must be >= 1" in str(exc)
    else:
        raise AssertionError("expected ValueError for zero limit")


def test_validate_query_text_rejects_short_text() -> None:
    try:
        _validate_query_text("ab")
    except ValueError as exc:
        assert "at least 3 characters" in str(exc)
    else:
        raise AssertionError("expected ValueError for short query text")


def test_extract_ok_row_returns_row() -> None:
    assert _extract_ok_row({"ok": True, "row": {"request_id": "r1"}}, "demo") == {"request_id": "r1"}


def test_extract_ok_row_rejects_non_ok_payload() -> None:
    try:
        _extract_ok_row({"ok": False, "error": "boom"}, "demo")
    except RuntimeError as exc:
        assert "returned non-ok result" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for non-ok payload")


@patch.object(server, "_fetch_all")
def test_get_request_eval_bundle_propagates_capture_error(mock_fetch_all) -> None:
    mock_fetch_all.side_effect = server.PsycopgError("db down")
    result = server.get_request_eval_bundle("req-1")
    assert result["ok"] is False
    assert result["operation"] == "get_request_capture"


@patch.object(server, "_fetch_one")
@patch.object(server, "_fetch_all")
def test_get_request_eval_bundle_uses_limited_projections(mock_fetch_all, mock_fetch_one) -> None:
    mock_fetch_one.side_effect = [
        {
            "request_id": "req-1",
            "trace_id": "tr-1",
            "received_at": "2026-03-28T00:00:00Z",
            "normalized_query": "q",
            "input_token_count": 5,
            "pipeline_config_version": "v1",
            "corpus_version": "c1",
            "retriever_version": "r1",
            "embedding_model": "e1",
            "reranker_kind": "Heuristic",
            "prompt_template_id": "p1",
            "prompt_template_version": "p1v",
            "generation_model": "g1",
            "top_k_requested": 5,
            "retrieval_result_count": 5,
            "selected_for_generation_count": 3,
            "final_answer": "a",
            "prompt_tokens": 10,
            "completion_tokens": 2,
            "total_tokens": 12,
            "stored_at": "2026-03-28T00:00:01Z",
        },
        {
            "request_id": "req-1",
            "current_stage": "judge_generation",
            "status": "running",
        },
        {
            "request_id": "req-1",
            "trace_id": "tr-1",
            "source_received_at": "2026-03-28T00:00:00Z",
            "summarized_at": "2026-03-28T00:00:02Z",
            "normalized_query": "q",
            "input_token_count": 5,
            "retriever_version": "r1",
            "reranker_kind": "Heuristic",
            "generation_model": "g1",
            "top_k_requested": 5,
            "answer_completeness_score": 0.9,
            "answer_completeness_label": "good",
            "groundedness_score": 0.9,
            "groundedness_label": "good",
            "answer_relevance_score": 0.9,
            "answer_relevance_label": "good",
            "correct_refusal_score": None,
            "correct_refusal_label": None,
            "retrieval_relevance_mean": 0.8,
            "retrieval_relevance_selected_mean": 0.9,
            "retrieval_relevance_topk_mean": 0.8,
            "retrieval_relevance_weighted_topk": 0.85,
            "retrieval_relevance_relevant_count": 4,
            "retrieval_relevance_selected_count": 3,
            "retrieval_chunk_count": 5,
        },
        {"row_count": 4},
        {"row_count": 8},
    ]
    mock_fetch_all.side_effect = [
        [
            {
                "request_id": "req-1",
                "run_id": "run-1",
                "trace_id": "tr-1",
                "suite_name": "groundedness",
                "judge_model": "judge",
                "judge_prompt_version": "v1",
                "score": 0.9,
                "label": "good",
                "created_at": "2026-03-28T00:00:03Z",
            }
        ],
        [
            {
                "request_id": "req-1",
                "run_id": "run-1",
                "trace_id": "tr-1",
                "chunk_id": "c1",
                "document_id": "d1",
                "retrieval_rank": 1,
                "retrieval_score": 0.99,
                "selected_for_generation": True,
                "suite_name": "retrieval_relevance",
                "judge_model": "judge",
                "judge_prompt_version": "v1",
                "score": 0.8,
                "label": "good",
                "created_at": "2026-03-28T00:00:03Z",
            }
        ],
    ]
    result = server.get_request_eval_bundle("req-1", generation_limit=10, retrieval_limit=15)
    assert result["ok"] is True
    assert result["capture"]["retrieval_result_count"] == 5
    assert result["request_summary"]["retrieval_chunk_count"] == 5
    assert result["judge_generation_result_count"] == 4
    assert result["judge_retrieval_result_count"] == 8


@patch.object(server, "_fetch_one")
@patch.object(server, "_fetch_all")
def test_check_connection_reports_visible_tables(mock_fetch_all, mock_fetch_one) -> None:
    mock_fetch_one.return_value = {"version": "PostgreSQL 16"}
    mock_fetch_all.return_value = [{"table_name": "request_captures"}, {"table_name": "eval_processing_state"}]
    result = server.check_connection()
    assert result["ok"] is True
    assert result["version"] == "PostgreSQL 16"
    assert "request_captures" in result["visible_tables"]
    assert "judge_generation_results" in result["missing_tables"]


@patch.object(server, "_fetch_all")
def test_get_eval_stage_summary_returns_grouped_counts(mock_fetch_all) -> None:
    mock_fetch_all.side_effect = [
        [{"status": "completed", "row_count": 5}],
        [{"current_stage": "judge_generation", "row_count": 5}],
        [{"current_stage": "judge_generation", "status": "completed", "row_count": 5}],
    ]
    result = server.get_eval_stage_summary()
    assert result["ok"] is True
    assert result["by_status"][0]["status"] == "completed"
    assert result["by_stage"][0]["current_stage"] == "judge_generation"


@patch.object(server, "_fetch_all")
def test_get_requests_by_run_id_returns_request_rows(mock_fetch_all) -> None:
    mock_fetch_all.return_value = [
        {
            "request_id": "req-1",
            "generation_row_count": 4,
            "retrieval_row_count": 8,
            "eval_status": "completed",
            "current_stage": "build_request_summary",
            "trace_id": "tr-1",
            "received_at": "2026-03-28T00:00:00Z",
            "normalized_query": "q",
            "reranker_kind": "Heuristic",
        }
    ]
    result = server.get_requests_by_run_id("run-1", limit=25)
    assert result["ok"] is True
    assert result["rows"][0]["request_id"] == "req-1"
    assert result["rows"][0]["retrieval_row_count"] == 8


@patch.object(server, "_fetch_one")
@patch.object(server, "_fetch_all")
def test_get_run_results_returns_aggregates(mock_fetch_all, mock_fetch_one) -> None:
    mock_fetch_all.side_effect = [
        [{"suite_name": "groundedness", "row_count": 3, "avg_score": 0.8}],
        [{"suite_name": "retrieval_relevance", "row_count": 7, "avg_score": 0.7}],
        [{"request_id": "req-1"}, {"request_id": "req-2"}],
    ]
    mock_fetch_one.return_value = {"request_count": 2}
    result = server.get_run_results("run-1")
    assert result["ok"] is True
    assert result["request_count"] == 2
    assert result["generation_by_suite"][0]["suite_name"] == "groundedness"
    assert result["retrieval_by_suite"][0]["suite_name"] == "retrieval_relevance"

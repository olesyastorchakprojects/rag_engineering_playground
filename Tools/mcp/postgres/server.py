from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg import Error as PsycopgError
from psycopg.rows import dict_row
from fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_POSTGRES_URL = "postgres://postgres:postgres@localhost:5432/rag_eval"
KNOWN_TABLES = [
    "request_captures",
    "judge_generation_results",
    "judge_retrieval_results",
    "request_summaries",
    "request_run_summaries",
    "eval_processing_state",
    "runtime_run_configs",
    "eval_run_configs",
]

mcp = FastMCP("postgres")


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


def _validate_table_name(table_name: str) -> str:
    candidate = table_name.strip()
    if candidate not in KNOWN_TABLES:
        raise ValueError(f"Unknown table: {table_name!r}")
    return candidate


def _validate_limit(limit: int) -> int:
    if limit < 1:
        raise ValueError("limit must be >= 1")
    return min(limit, 200)


def _validate_query_text(query_text: str) -> str:
    candidate = query_text.strip()
    if not candidate:
        raise ValueError("query_text must not be empty")
    if len(candidate) < 3:
        raise ValueError("query_text must be at least 3 characters long")
    return candidate


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


def _extract_ok_row(result: dict[str, Any], operation: str) -> dict[str, Any] | None:
    if not result.get("ok", False):
        raise RuntimeError(f"{operation} returned non-ok result")
    return result.get("row")


@mcp.tool
def check_connection() -> dict[str, Any]:
    """Return whether PostgreSQL is reachable and curated tables are visible."""
    try:
        version_row = _fetch_one("select version() as version")
        visible_tables = _fetch_all(
            """
            select table_name
            from information_schema.tables
            where table_schema = 'public'
              and table_name = any(%s)
            order by table_name
            """,
            (KNOWN_TABLES,),
        )
        table_names = [row["table_name"] for row in visible_tables]
        return {
            "ok": True,
            "postgres_url": _redact_url(_postgres_url()),
            "version": version_row["version"] if version_row else None,
            "visible_tables": table_names,
            "missing_tables": [table for table in KNOWN_TABLES if table not in table_names],
        }
    except PsycopgError as exc:
        return _db_error_payload("check_connection", exc)


@mcp.tool
def get_connection_defaults() -> dict[str, Any]:
    """Return default local Postgres connection settings and known eval tables."""
    return {
        "ok": True,
        "postgres_url": _redact_url(_postgres_url()),
        "source": "POSTGRES_URL env" if os.environ.get("POSTGRES_URL") else "project default local stack DSN",
        "known_tables": KNOWN_TABLES,
        "compose_path": "Execution/docker/compose.yaml",
    }


@mcp.tool
def get_known_tables() -> dict[str, Any]:
    """Return the curated eval-truth table set used by the project."""
    return {
        "ok": True,
        "tables": KNOWN_TABLES,
        "count": len(KNOWN_TABLES),
    }


@mcp.tool
def describe_table(table_name: str) -> dict[str, Any]:
    """Return columns and indexes for one curated public table."""
    table_name = _validate_table_name(table_name)
    try:
        columns = _fetch_all(
            """
            select
                column_name,
                data_type,
                udt_name,
                is_nullable,
                column_default
            from information_schema.columns
            where table_schema = 'public' and table_name = %s
            order by ordinal_position
            """,
            (table_name,),
        )
        indexes = _fetch_all(
            """
            select indexname, indexdef
            from pg_indexes
            where schemaname = 'public' and tablename = %s
            order by indexname
            """,
            (table_name,),
        )
        return {
            "ok": True,
            "table_name": table_name,
            "columns": columns,
            "indexes": indexes,
        }
    except PsycopgError as exc:
        return _db_error_payload("describe_table", exc, table_name=table_name)


@mcp.tool
def get_table_row_counts() -> dict[str, Any]:
    """Return row counts for the curated eval-truth tables."""
    try:
        counts = []
        for table_name in KNOWN_TABLES:
            row = _fetch_one(f"select count(*)::bigint as row_count from {table_name}")
            counts.append(
                {
                    "table_name": table_name,
                    "row_count": row["row_count"] if row is not None else None,
                }
            )
        return {
            "ok": True,
            "tables": counts,
        }
    except PsycopgError as exc:
        return _db_error_payload("get_table_row_counts", exc)


@mcp.tool
def get_recent_request_captures(limit: int = 20) -> dict[str, Any]:
    """Return recent request capture rows with lightweight fields for inspection."""
    limit = _validate_limit(limit)
    try:
        rows = _fetch_all(
            """
            select
                request_id,
                trace_id,
                received_at,
                normalized_query,
                reranker_kind,
                retriever_version,
                generation_model,
                top_k_requested,
                stored_at
            from request_captures
            order by received_at desc
            limit %s
            """,
            (limit,),
        )
        return {
            "ok": True,
            "limit": limit,
            "rows": rows,
            "count": len(rows),
        }
    except PsycopgError as exc:
        return _db_error_payload("get_recent_request_captures", exc, limit=limit)


@mcp.tool
def find_requests_by_query_text(query_text: str, limit: int = 20) -> dict[str, Any]:
    """Return request capture rows matching raw_query or normalized_query by ILIKE fragment."""
    query_text = _validate_query_text(query_text)
    limit = _validate_limit(limit)
    pattern = f"%{query_text}%"
    try:
        rows = _fetch_all(
            """
            select
                request_id,
                trace_id,
                received_at,
                raw_query,
                normalized_query,
                reranker_kind,
                generation_model,
                stored_at
            from request_captures
            where raw_query ilike %s
               or normalized_query ilike %s
            order by received_at desc
            limit %s
            """,
            (pattern, pattern, limit),
        )
        return {
            "ok": True,
            "query_text": query_text,
            "limit": limit,
            "rows": rows,
            "count": len(rows),
        }
    except PsycopgError as exc:
        return _db_error_payload("find_requests_by_query_text", exc, query_text=query_text, limit=limit)


@mcp.tool
def get_request_capture(request_id: str) -> dict[str, Any]:
    """Return one lightweight request_captures projection by request_id."""
    request_id = request_id.strip()
    if not request_id:
        raise ValueError("request_id must not be empty")
    try:
        row = _fetch_one(
            """
            select
                request_id,
                trace_id,
                received_at,
                normalized_query,
                input_token_count,
                pipeline_config_version,
                corpus_version,
                retriever_version,
                embedding_model,
                reranker_kind,
                prompt_template_id,
                prompt_template_version,
                generation_model,
                top_k_requested,
                jsonb_array_length(retrieval_results) as retrieval_result_count,
                (
                    select count(*)::int
                    from jsonb_array_elements(retrieval_results) as item
                    where (item ->> 'selected_for_generation')::boolean = true
                ) as selected_for_generation_count,
                final_answer,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                stored_at
            from request_captures
            where request_id = %s
            """,
            (request_id,),
        )
        return {
            "ok": True,
            "request_id": request_id,
            "row": row,
            "found": row is not None,
        }
    except PsycopgError as exc:
        return _db_error_payload("get_request_capture", exc, request_id=request_id)


@mcp.tool
def get_request_capture_full(request_id: str) -> dict[str, Any]:
    """Return the full request_captures row by request_id, including retrieval_results JSONB."""
    request_id = request_id.strip()
    if not request_id:
        raise ValueError("request_id must not be empty")
    try:
        row = _fetch_one(
            """
            select *
            from request_captures
            where request_id = %s
            """,
            (request_id,),
        )
        return {
            "ok": True,
            "request_id": request_id,
            "row": row,
            "found": row is not None,
        }
    except PsycopgError as exc:
        return _db_error_payload("get_request_capture_full", exc, request_id=request_id)


@mcp.tool
def find_request_capture_by_trace_id(trace_id: str, limit: int = 20) -> dict[str, Any]:
    """Return request capture rows sharing one trace_id."""
    trace_id = trace_id.strip()
    if not trace_id:
        raise ValueError("trace_id must not be empty")
    limit = _validate_limit(limit)
    try:
        rows = _fetch_all(
            """
            select
                request_id,
                trace_id,
                received_at,
                normalized_query,
                reranker_kind,
                generation_model,
                stored_at
            from request_captures
            where trace_id = %s
            order by received_at desc
            limit %s
            """,
            (trace_id, limit),
        )
        return {
            "ok": True,
            "trace_id": trace_id,
            "rows": rows,
            "count": len(rows),
        }
    except PsycopgError as exc:
        return _db_error_payload("find_request_capture_by_trace_id", exc, trace_id=trace_id, limit=limit)


@mcp.tool
def get_eval_processing_state(request_id: str) -> dict[str, Any]:
    """Return one eval_processing_state row by request_id."""
    request_id = request_id.strip()
    if not request_id:
        raise ValueError("request_id must not be empty")
    try:
        row = _fetch_one(
            """
            select *
            from eval_processing_state
            where request_id = %s
            """,
            (request_id,),
        )
        return {
            "ok": True,
            "request_id": request_id,
            "row": row,
            "found": row is not None,
        }
    except PsycopgError as exc:
        return _db_error_payload("get_eval_processing_state", exc, request_id=request_id)


@mcp.tool
def get_request_summary(request_id: str) -> dict[str, Any]:
    """Return one lightweight request_summaries projection by request_id."""
    request_id = request_id.strip()
    if not request_id:
        raise ValueError("request_id must not be empty")
    try:
        row = _fetch_one(
            """
            select
                request_id,
                trace_id,
                source_received_at,
                summarized_at,
                normalized_query,
                input_token_count,
                retriever_version,
                reranker_kind,
                generation_model,
                top_k_requested,
                answer_completeness_score,
                answer_completeness_label,
                groundedness_score,
                groundedness_label,
                answer_relevance_score,
                answer_relevance_label,
                correct_refusal_score,
                correct_refusal_label,
                retrieval_relevance_mean,
                retrieval_relevance_selected_mean,
                retrieval_relevance_topk_mean,
                retrieval_relevance_weighted_topk,
                retrieval_relevance_relevant_count,
                retrieval_relevance_selected_count,
                retrieval_chunk_count
            from request_summaries
            where request_id = %s
            """,
            (request_id,),
        )
        return {
            "ok": True,
            "request_id": request_id,
            "row": row,
            "found": row is not None,
        }
    except PsycopgError as exc:
        return _db_error_payload("get_request_summary", exc, request_id=request_id)


@mcp.tool
def get_request_summary_full(request_id: str) -> dict[str, Any]:
    """Return the full request_summaries row by request_id."""
    request_id = request_id.strip()
    if not request_id:
        raise ValueError("request_id must not be empty")
    try:
        row = _fetch_one(
            """
            select *
            from request_summaries
            where request_id = %s
            """,
            (request_id,),
        )
        return {
            "ok": True,
            "request_id": request_id,
            "row": row,
            "found": row is not None,
        }
    except PsycopgError as exc:
        return _db_error_payload("get_request_summary_full", exc, request_id=request_id)


@mcp.tool
def get_request_eval_bundle(request_id: str, generation_limit: int = 20, retrieval_limit: int = 50) -> dict[str, Any]:
    """Return request capture, eval state, summary, and limited judge rows for one request_id."""
    request_id = request_id.strip()
    if not request_id:
        raise ValueError("request_id must not be empty")
    generation_limit = _validate_limit(generation_limit)
    retrieval_limit = _validate_limit(retrieval_limit)

    try:
        capture_result = get_request_capture(request_id)
        state_result = get_eval_processing_state(request_id)
        summary_result = get_request_summary(request_id)

        if not capture_result.get("ok", False):
            return capture_result
        if not state_result.get("ok", False):
            return state_result
        if not summary_result.get("ok", False):
            return summary_result

        capture = _extract_ok_row(capture_result, "get_request_capture")
        state = _extract_ok_row(state_result, "get_eval_processing_state")
        summary = _extract_ok_row(summary_result, "get_request_summary")
        generation_rows = _fetch_all(
            """
            select
                request_id,
                run_id,
                trace_id,
                suite_name::text as suite_name,
                judge_model,
                judge_prompt_version,
                score,
                label,
                created_at
            from judge_generation_results
            where request_id = %s
            order by run_id, suite_name
            limit %s
            """,
            (request_id, generation_limit),
        )
        retrieval_rows = _fetch_all(
            """
            select
                request_id,
                run_id,
                trace_id,
                chunk_id,
                document_id,
                retrieval_rank,
                retrieval_score,
                selected_for_generation,
                suite_name::text as suite_name,
                judge_model,
                judge_prompt_version,
                score,
                label,
                created_at
            from judge_retrieval_results
            where request_id = %s
            order by run_id, retrieval_rank, chunk_id
            limit %s
            """,
            (request_id, retrieval_limit),
        )
        generation_count = _fetch_one(
            """
            select count(*)::bigint as row_count
            from judge_generation_results
            where request_id = %s
            """,
            (request_id,),
        )
        retrieval_count = _fetch_one(
            """
            select count(*)::bigint as row_count
            from judge_retrieval_results
            where request_id = %s
            """,
            (request_id,),
        )
        run_ids = sorted(
            {
                row["run_id"]
                for row in [*generation_rows, *retrieval_rows]
                if isinstance(row, dict) and row.get("run_id")
            }
        )
        return {
            "ok": True,
            "request_id": request_id,
            "capture": capture,
            "eval_processing_state": state,
            "request_summary": summary,
            "judge_generation_results": generation_rows,
            "judge_retrieval_results": retrieval_rows,
            "judge_generation_result_count": generation_count["row_count"] if generation_count else 0,
            "judge_retrieval_result_count": retrieval_count["row_count"] if retrieval_count else 0,
            "generation_limit": generation_limit,
            "retrieval_limit": retrieval_limit,
            "run_ids": run_ids,
        }
    except (PsycopgError, RuntimeError) as exc:
        return _db_error_payload(
            "get_request_eval_bundle",
            exc,
            request_id=request_id,
            generation_limit=generation_limit,
            retrieval_limit=retrieval_limit,
        )


@mcp.tool
def get_incomplete_eval_requests(limit: int = 20) -> dict[str, Any]:
    """Return pending, running, or failed eval requests ordered by most recent updates first."""
    limit = _validate_limit(limit)
    try:
        rows = _fetch_all(
            """
            select
                request_id,
                request_received_at,
                current_stage,
                status,
                attempt_count,
                started_at,
                completed_at,
                updated_at,
                last_error
            from eval_processing_state
            where status <> 'completed'
            order by updated_at desc, request_received_at desc
            limit %s
            """,
            (limit,),
        )
        return {
            "ok": True,
            "limit": limit,
            "rows": rows,
            "count": len(rows),
        }
    except PsycopgError as exc:
        return _db_error_payload("get_incomplete_eval_requests", exc, limit=limit)


@mcp.tool
def get_eval_stage_summary() -> dict[str, Any]:
    """Return compact status and stage aggregates from eval_processing_state."""
    try:
        by_status = _fetch_all(
            """
            select status::text as status, count(*)::bigint as row_count
            from eval_processing_state
            group by status
            order by status
            """
        )
        by_stage = _fetch_all(
            """
            select current_stage::text as current_stage, count(*)::bigint as row_count
            from eval_processing_state
            group by current_stage
            order by current_stage
            """
        )
        by_stage_and_status = _fetch_all(
            """
            select
                current_stage::text as current_stage,
                status::text as status,
                count(*)::bigint as row_count
            from eval_processing_state
            group by current_stage, status
            order by current_stage, status
            """
        )
        return {
            "ok": True,
            "by_status": by_status,
            "by_stage": by_stage,
            "by_stage_and_status": by_stage_and_status,
        }
    except PsycopgError as exc:
        return _db_error_payload("get_eval_stage_summary", exc)


@mcp.tool
def get_failed_eval_requests(limit: int = 20) -> dict[str, Any]:
    """Return only failed eval requests ordered by most recent updates first."""
    limit = _validate_limit(limit)
    try:
        rows = _fetch_all(
            """
            select
                request_id,
                request_received_at,
                current_stage,
                status,
                attempt_count,
                started_at,
                completed_at,
                updated_at,
                last_error
            from eval_processing_state
            where status = 'failed'
            order by updated_at desc, request_received_at desc
            limit %s
            """,
            (limit,),
        )
        return {
            "ok": True,
            "limit": limit,
            "rows": rows,
            "count": len(rows),
        }
    except PsycopgError as exc:
        return _db_error_payload("get_failed_eval_requests", exc, limit=limit)


@mcp.tool
def get_requests_by_run_id(run_id: str, limit: int = 200) -> dict[str, Any]:
    """Return request-level run membership and row coverage for one run_id."""
    run_id = run_id.strip()
    if not run_id:
        raise ValueError("run_id must not be empty")
    limit = _validate_limit(limit)
    try:
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
                rc.received_at,
                rc.normalized_query
            from run_requests rr
            left join eval_processing_state eps on eps.request_id = rr.request_id
            left join request_captures rc on rc.request_id = rr.request_id
            order by rc.received_at desc nulls last, rr.request_id
            limit %s
            """,
            (run_id, run_id, limit),
        )
        return {
            "ok": True,
            "run_id": run_id,
            "limit": limit,
            "rows": rows,
            "count": len(rows),
        }
    except PsycopgError as exc:
        return _db_error_payload("get_requests_by_run_id", exc, run_id=run_id, limit=limit)


@mcp.tool
def get_run_results(run_id: str) -> dict[str, Any]:
    """Return run-scoped judge-result counts and suite aggregates for one run_id."""
    run_id = run_id.strip()
    if not run_id:
        raise ValueError("run_id must not be empty")

    try:
        generation_rows = _fetch_all(
            """
            select
                suite_name::text as suite_name,
                count(*)::bigint as row_count,
                avg(score)::numeric(8,4) as avg_score
            from judge_generation_results
            where run_id = %s
            group by suite_name
            order by suite_name
            """,
            (run_id,),
        )
        retrieval_rows = _fetch_all(
            """
            select
                suite_name::text as suite_name,
                count(*)::bigint as row_count,
                avg(score)::numeric(8,4) as avg_score
            from judge_retrieval_results
            where run_id = %s
            group by suite_name
            order by suite_name
            """,
            (run_id,),
        )
        distinct_requests = _fetch_one(
            """
            select count(distinct request_id)::bigint as request_count
            from (
                select request_id from judge_generation_results where run_id = %s
                union
                select request_id from judge_retrieval_results where run_id = %s
            ) as run_requests
            """,
            (run_id, run_id),
        )
        sample_request_ids = _fetch_all(
            """
            select request_id
            from (
                select request_id from judge_generation_results where run_id = %s
                union
                select request_id from judge_retrieval_results where run_id = %s
            ) as run_requests
            order by request_id
            limit 20
            """,
            (run_id, run_id),
        )
        return {
            "ok": True,
            "run_id": run_id,
            "request_count": distinct_requests["request_count"] if distinct_requests else 0,
            "generation_by_suite": generation_rows,
            "retrieval_by_suite": retrieval_rows,
            "sample_request_ids": [row["request_id"] for row in sample_request_ids],
            "note": "request_summaries is not included here because it is request-scoped, not run-scoped.",
        }
    except PsycopgError as exc:
        return _db_error_payload("get_run_results", exc, run_id=run_id)


if __name__ == "__main__":
    mcp.run()

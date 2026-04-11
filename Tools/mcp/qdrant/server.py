from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_QDRANT_URL = "http://localhost:6333"
DEFAULT_INGEST_CONFIG_PATH = REPO_ROOT / "Execution" / "ingest" / "dense" / "ingest.toml"

mcp = FastMCP("qdrant")


def _qdrant_url() -> str:
    return os.environ.get("QDRANT_URL", DEFAULT_QDRANT_URL).rstrip("/")


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        import tomllib as parser  # type: ignore
    except ModuleNotFoundError:
        import tomli as parser  # type: ignore
    with path.open("rb") as handle:
        data = parser.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"TOML root must be an object: {path}")
    return data


def _resolve_config_path(config_path: str = "") -> Path:
    if not config_path:
        return DEFAULT_INGEST_CONFIG_PATH
    candidate = (REPO_ROOT / config_path).resolve()
    if REPO_ROOT.resolve() not in candidate.parents and candidate != REPO_ROOT.resolve():
        raise ValueError(f"config_path is outside repository: {config_path}")
    if not candidate.is_file():
        raise ValueError(f"config_path does not exist: {config_path}")
    return candidate


def _load_ingest_config(config_path: str = "") -> dict[str, Any]:
    return _load_toml(_resolve_config_path(config_path))


def _ingest_mode(config: dict[str, Any]) -> str:
    sparse = config.get("sparse")
    if isinstance(sparse, dict) and isinstance(sparse.get("strategy"), dict):
        return "hybrid"
    return "dense"


def _hybrid_strategy_suffix(strategy_kind: str) -> str:
    mapping = {
        "bag_of_words": "bow",
        "bm25_like": "bm25",
    }
    if strategy_kind not in mapping:
        raise ValueError(f"Unsupported hybrid sparse strategy kind: {strategy_kind}")
    return mapping[strategy_kind]


def _expected_collection_name_from_config(config: dict[str, Any]) -> str:
    try:
        base_name = str(config["qdrant"]["collection"]["name"])
    except Exception as exc:
        raise ValueError("Could not resolve qdrant.collection.name from ingest config") from exc
    if _ingest_mode(config) == "hybrid":
        strategy_kind = str(config["sparse"]["strategy"]["kind"])
        return f"{base_name}_{_hybrid_strategy_suffix(strategy_kind)}"
    return base_name


def _default_collection_name(config_path: str = "") -> str:
    config = _load_ingest_config(config_path)
    return _expected_collection_name_from_config(config)


def _resolve_collection_name(collection_name: str = "", config_path: str = "") -> str:
    candidate = collection_name.strip()
    if candidate:
        return candidate
    return _default_collection_name(config_path)


def _validate_limit(limit: int) -> int:
    if limit < 1:
        raise ValueError("limit must be >= 1")
    return min(limit, 100)


def _http_json(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    timeout_sec: float = 3.0,
) -> dict[str, Any]:
    url = _qdrant_url() + path
    headers = {
        "Accept": "application/json",
        "User-Agent": "prompt-gen-qdrant-mcp/1.0",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url=url, method=method, data=data, headers=headers)
    try:
        with urlopen(request, timeout=timeout_sec) as response:
            body = response.read().decode("utf-8", errors="replace")
            json_body = json.loads(body) if body else None
            return {
                "ok": True,
                "status_code": getattr(response, "status", 200),
                "url": url,
                "json": json_body,
            }
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            json_body = json.loads(body) if body else None
        except Exception:
            json_body = None
        return {
            "ok": False,
            "status_code": exc.code,
            "url": url,
            "error_type": "HTTPError",
            "error": str(exc),
            "json": json_body,
            "body": body,
        }
    except URLError as exc:
        return {
            "ok": False,
            "status_code": None,
            "url": url,
            "error_type": "URLError",
            "error": str(exc),
        }
    except Exception as exc:  # pragma: no cover - defensive runtime fallback
        return {
            "ok": False,
            "status_code": None,
            "url": url,
            "error_type": exc.__class__.__name__,
            "error": str(exc),
        }


def _qdrant_error_payload(operation: str, response: dict[str, Any], **context: Any) -> dict[str, Any]:
    payload = {
        "ok": False,
        "operation": operation,
        "qdrant_url": _qdrant_url(),
        "status_code": response.get("status_code"),
        "error_type": response.get("error_type"),
        "error": response.get("error"),
    }
    if "body" in response:
        payload["body"] = response["body"]
    if context:
        payload["context"] = context
    return payload


def _tool_error_payload(operation: str, exc: Exception, **context: Any) -> dict[str, Any]:
    payload = {
        "ok": False,
        "operation": operation,
        "qdrant_url": _qdrant_url(),
        "error_type": exc.__class__.__name__,
        "error": str(exc),
    }
    if context:
        payload["context"] = context
    return payload


def _summarize_point(point: dict[str, Any]) -> dict[str, Any]:
    payload = point.get("payload", {}) if isinstance(point, dict) else {}
    if not isinstance(payload, dict):
        payload = {}
    return {
        "id": point.get("id"),
        "score": point.get("score"),
        "payload": payload,
        "chunk_id": payload.get("chunk_id"),
        "doc_id": payload.get("doc_id"),
        "document_title": payload.get("document_title"),
        "section_title": payload.get("section_title"),
        "page_start": payload.get("page_start"),
        "page_end": payload.get("page_end"),
        "content_hash": payload.get("content_hash"),
    }


def _collection_info_from_response(collection_name: str, response_json: dict[str, Any] | None) -> dict[str, Any]:
    result = response_json.get("result", {}) if isinstance(response_json, dict) else {}
    config = result.get("config", {}) if isinstance(result, dict) else {}
    params = config.get("params", {}) if isinstance(config, dict) else {}
    vectors = params.get("vectors", {}) if isinstance(params, dict) else {}
    sparse_vectors = params.get("sparse_vectors", {}) if isinstance(params, dict) else {}
    metadata = config.get("metadata", {}) if isinstance(config, dict) else {}
    payload_schema = result.get("payload_schema", {}) if isinstance(result, dict) else {}
    vector_layout = "single"
    vector_size = vectors.get("size") if isinstance(vectors, dict) else None
    vector_distance = vectors.get("distance") if isinstance(vectors, dict) else None
    if isinstance(vectors, dict) and ("size" not in vectors or "distance" not in vectors):
        vector_layout = "named_or_multivector"
        vector_size = None
        vector_distance = None
    return {
        "collection_name": collection_name,
        "status": result.get("status"),
        "optimizer_status": result.get("optimizer_status"),
        "points_count": result.get("points_count"),
        "indexed_vectors_count": result.get("indexed_vectors_count"),
        "segments_count": result.get("segments_count"),
        "vector_layout": vector_layout,
        "vector_size": vector_size,
        "vector_distance": vector_distance,
        "raw_vectors_config": vectors if isinstance(vectors, dict) else None,
        "raw_sparse_vectors_config": sparse_vectors if isinstance(sparse_vectors, dict) else None,
        "on_disk_payload": params.get("on_disk_payload") if isinstance(params, dict) else None,
        "metadata": metadata if isinstance(metadata, dict) else {},
        "payload_schema": payload_schema if isinstance(payload_schema, dict) else {},
    }


def _collection_info(collection_name: str) -> dict[str, Any]:
    quoted = quote(collection_name, safe="")
    response = _http_json("GET", f"/collections/{quoted}")
    if not response.get("ok"):
        raise RuntimeError(json.dumps(_qdrant_error_payload("get_collection_info", response, collection_name=collection_name)))
    return _collection_info_from_response(collection_name, response.get("json"))


def _compatibility_signals(collection_name: str, config_path: str = "") -> dict[str, Any]:
    config = _load_ingest_config(config_path)
    info = _collection_info(collection_name)
    ingest_mode = _ingest_mode(config)

    expected_model = config["embedding"]["model"]["name"]
    expected_dimension = config["embedding"]["model"]["dimension"]
    expected_distance = config["qdrant"]["collection"]["distance"]
    expected_collection_name = _expected_collection_name_from_config(config)
    actual_model = info["metadata"].get("embedding_model_name")

    checks: dict[str, Any] = {
        "ingest_mode": ingest_mode,
        "collection_name_matches": collection_name == expected_collection_name,
        "embedding_model_name_matches": actual_model == expected_model,
    }
    expected: dict[str, Any] = {
        "collection_name": expected_collection_name,
        "embedding_model_name": expected_model,
        "vector_dimension": expected_dimension,
        "vector_distance": expected_distance,
    }

    problems = []
    if not checks["collection_name_matches"]:
        problems.append("collection name differs from ingest config")
    if actual_model is None:
        problems.append("collection metadata missing embedding_model_name")
    elif not checks["embedding_model_name_matches"]:
        problems.append("collection embedding_model_name mismatch")

    if ingest_mode == "dense":
        expected_vector_name = config["qdrant"]["collection"]["vector_name"]
        checks.update(
            {
                "vector_dimension_matches": info["vector_size"] == expected_dimension,
                "vector_distance_matches": info["vector_distance"] == expected_distance,
                "vector_name_supported": expected_vector_name == "default",
            }
        )
        expected["vector_name"] = expected_vector_name
        if not checks["vector_dimension_matches"]:
            problems.append("collection vector dimension mismatch")
        if not checks["vector_distance_matches"]:
            problems.append("collection vector distance mismatch")
        if not checks["vector_name_supported"]:
            problems.append("non-default vector_name is not yet summarized by this MCP")
    else:
        expected_dense_vector_name = config["qdrant"]["collection"]["dense_vector_name"]
        expected_sparse_vector_name = config["qdrant"]["collection"]["sparse_vector_name"]
        expected_strategy_kind = config["sparse"]["strategy"]["kind"]
        expected_strategy_version = config["sparse"]["strategy"]["version"]
        raw_vectors = info["raw_vectors_config"] if isinstance(info["raw_vectors_config"], dict) else {}
        raw_sparse_vectors = (
            info["raw_sparse_vectors_config"] if isinstance(info["raw_sparse_vectors_config"], dict) else {}
        )
        dense_config = raw_vectors.get(expected_dense_vector_name) if isinstance(raw_vectors, dict) else None
        vocabulary_identity = info["metadata"].get("vocabulary_identity")

        checks.update(
            {
                "dense_vector_name_matches": isinstance(raw_vectors, dict) and expected_dense_vector_name in raw_vectors,
                "sparse_vectors_present": isinstance(raw_sparse_vectors, dict) and bool(raw_sparse_vectors),
                "sparse_vector_name_matches": isinstance(raw_sparse_vectors, dict)
                and expected_sparse_vector_name in raw_sparse_vectors,
                "vector_dimension_matches": isinstance(dense_config, dict)
                and dense_config.get("size") == expected_dimension,
                "vector_distance_matches": isinstance(dense_config, dict)
                and dense_config.get("distance") == expected_distance,
                "sparse_strategy_kind_matches": info["metadata"].get("sparse_strategy_kind") == expected_strategy_kind,
                "sparse_strategy_version_matches": info["metadata"].get("sparse_strategy_version")
                == expected_strategy_version,
                "vocabulary_identity_present": isinstance(vocabulary_identity, dict),
            }
        )
        expected.update(
            {
                "dense_vector_name": expected_dense_vector_name,
                "sparse_vector_name": expected_sparse_vector_name,
                "sparse_strategy_kind": expected_strategy_kind,
                "sparse_strategy_version": expected_strategy_version,
            }
        )
        if not checks["dense_vector_name_matches"]:
            problems.append("collection dense_vector_name mismatch")
        if not checks["sparse_vectors_present"]:
            problems.append("collection sparse_vectors missing")
        if checks["sparse_vectors_present"] and not checks["sparse_vector_name_matches"]:
            problems.append("collection sparse_vector_name mismatch")
        if not checks["vector_dimension_matches"]:
            problems.append("collection dense vector dimension mismatch")
        if not checks["vector_distance_matches"]:
            problems.append("collection dense vector distance mismatch")
        if not checks["sparse_strategy_kind_matches"]:
            problems.append("collection sparse_strategy_kind mismatch")
        if not checks["sparse_strategy_version_matches"]:
            problems.append("collection sparse_strategy_version mismatch")
        if not checks["vocabulary_identity_present"]:
            problems.append("collection metadata missing vocabulary_identity")

    return {
        "ok": True,
        "ingest_mode": ingest_mode,
        "collection_name": collection_name,
        "config_path": str(_resolve_config_path(config_path).relative_to(REPO_ROOT)),
        "expected": expected,
        "actual": info,
        "checks": checks,
        "compatible": len(problems) == 0,
        "problems": problems,
    }


def _scroll_points(collection_name: str, filter_payload: dict[str, Any] | None = None, limit: int = 10) -> dict[str, Any]:
    quoted = quote(collection_name, safe="")
    request_body: dict[str, Any] = {
        "limit": limit,
        "with_payload": True,
        "with_vector": False,
    }
    if filter_payload is not None:
        request_body["filter"] = filter_payload
    return _http_json("POST", f"/collections/{quoted}/points/scroll", payload=request_body, timeout_sec=5.0)


def _filter_match(field_name: str, value: str) -> dict[str, Any]:
    return {"must": [{"key": field_name, "match": {"value": value}}]}


def _required_chunk_payload_fields() -> list[str]:
    return [
        "chunk_id",
        "doc_id",
        "text",
        "content_hash",
        "page_start",
        "page_end",
        "document_title",
    ]


def _resolve_collection_context(
    operation: str,
    collection_name: str = "",
    config_path: str = "",
) -> tuple[str | None, dict[str, Any] | None]:
    try:
        return _resolve_collection_name(collection_name, config_path), None
    except Exception as exc:
        return None, _tool_error_payload(
            operation,
            exc,
            collection_name=collection_name,
            config_path=config_path,
        )


@mcp.tool
def check_connection() -> dict[str, Any]:
    """Return whether Qdrant is reachable and whether the default ingest-derived collection is visible."""
    list_response = _http_json("GET", "/collections")
    if not list_response.get("ok"):
        return _qdrant_error_payload("check_connection", list_response)

    collection_names = []
    payload = list_response.get("json", {})
    result = payload.get("result", {}) if isinstance(payload, dict) else {}
    collections = result.get("collections", []) if isinstance(result, dict) else []
    for entry in collections:
        if isinstance(entry, dict) and isinstance(entry.get("name"), str):
            collection_names.append(entry["name"])

    expected_collection = None
    try:
        expected_collection = _default_collection_name()
    except Exception:
        expected_collection = None

    return {
        "ok": True,
        "qdrant_url": _qdrant_url(),
        "collections": collection_names,
        "collection_count": len(collection_names),
        "default_dense_collection": expected_collection,
        "default_collection_present": expected_collection in collection_names if expected_collection else None,
    }


@mcp.tool
def get_connection_defaults() -> dict[str, Any]:
    """Return default local Qdrant connection settings and default ingest config path."""
    return {
        "ok": True,
        "qdrant_url": _qdrant_url(),
        "source": "QDRANT_URL env" if os.environ.get("QDRANT_URL") else "project default local stack URL",
        "default_ingest_config_path": str(DEFAULT_INGEST_CONFIG_PATH.relative_to(REPO_ROOT)),
        "chunk_schema_path": "Execution/schemas/chunk.schema.json",
    }


@mcp.tool
def list_collections() -> dict[str, Any]:
    """Return the current Qdrant collection list."""
    response = _http_json("GET", "/collections")
    if not response.get("ok"):
        return _qdrant_error_payload("list_collections", response)
    payload = response.get("json", {})
    result = payload.get("result", {}) if isinstance(payload, dict) else {}
    collections = result.get("collections", []) if isinstance(result, dict) else []
    names = [entry["name"] for entry in collections if isinstance(entry, dict) and isinstance(entry.get("name"), str)]
    return {
        "ok": True,
        "collections": names,
        "count": len(names),
    }


@mcp.tool
def get_collection_info(collection_name: str = "", config_path: str = "") -> dict[str, Any]:
    """Return live collection config and lightweight metadata for one collection."""
    collection_name, error = _resolve_collection_context("get_collection_info", collection_name, config_path)
    if error is not None:
        return error
    assert collection_name is not None
    response = _http_json("GET", f"/collections/{quote(collection_name, safe='')}")
    if not response.get("ok"):
        return _qdrant_error_payload("get_collection_info", response, collection_name=collection_name)
    return {
        "ok": True,
        **_collection_info_from_response(collection_name, response.get("json")),
    }


@mcp.tool
def get_collection_compatibility(collection_name: str = "", config_path: str = "") -> dict[str, Any]:
    """Compare a live collection against dense ingest config expectations."""
    try:
        collection_name = _resolve_collection_name(collection_name, config_path)
        return _compatibility_signals(collection_name, config_path)
    except RuntimeError as exc:
        try:
            payload = json.loads(str(exc))
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass
        return {
            "ok": False,
            "operation": "get_collection_compatibility",
            "error_type": exc.__class__.__name__,
            "error": str(exc),
            "qdrant_url": _qdrant_url(),
        }
    except Exception as exc:
        return {
            "ok": False,
            "operation": "get_collection_compatibility",
            "error_type": exc.__class__.__name__,
            "error": str(exc),
            "qdrant_url": _qdrant_url(),
        }


@mcp.tool
def get_sample_points(collection_name: str = "", limit: int = 10, config_path: str = "") -> dict[str, Any]:
    """Return a lightweight sample of points from one collection without vectors."""
    try:
        limit = _validate_limit(limit)
    except Exception as exc:
        return _tool_error_payload("get_sample_points", exc, limit=limit, config_path=config_path)
    collection_name, error = _resolve_collection_context("get_sample_points", collection_name, config_path)
    if error is not None:
        return error
    assert collection_name is not None
    response = _scroll_points(collection_name, limit=limit)
    if not response.get("ok"):
        return _qdrant_error_payload("get_sample_points", response, collection_name=collection_name, limit=limit)
    payload = response.get("json", {})
    result = payload.get("result", {}) if isinstance(payload, dict) else {}
    points = result.get("points", []) if isinstance(result, dict) else []
    return {
        "ok": True,
        "collection_name": collection_name,
        "limit": limit,
        "points": [_summarize_point(point) for point in points if isinstance(point, dict)],
        "count": len(points),
        "next_page_offset": result.get("next_page_offset") if isinstance(result, dict) else None,
    }


@mcp.tool
def get_point_by_id(point_id: str, collection_name: str = "", config_path: str = "") -> dict[str, Any]:
    """Return one point by Qdrant point id."""
    try:
        point_id = point_id.strip()
        if not point_id:
            raise ValueError("point_id must not be empty")
    except Exception as exc:
        return _tool_error_payload("get_point_by_id", exc, point_id=point_id, config_path=config_path)
    collection_name, error = _resolve_collection_context("get_point_by_id", collection_name, config_path)
    if error is not None:
        return error
    assert collection_name is not None
    response = _http_json(
        "POST",
        f"/collections/{quote(collection_name, safe='')}/points",
        payload={"ids": [point_id], "with_payload": True, "with_vector": False},
        timeout_sec=5.0,
    )
    if not response.get("ok"):
        return _qdrant_error_payload("get_point_by_id", response, collection_name=collection_name, point_id=point_id)
    payload = response.get("json", {})
    result = payload.get("result", []) if isinstance(payload, dict) else []
    point = result[0] if isinstance(result, list) and result else None
    return {
        "ok": True,
        "collection_name": collection_name,
        "point_id": point_id,
        "found": point is not None,
        "point": _summarize_point(point) if isinstance(point, dict) else None,
    }


@mcp.tool
def find_points_by_chunk_id(chunk_id: str, collection_name: str = "", limit: int = 20, config_path: str = "") -> dict[str, Any]:
    """Return points whose payload chunk_id matches one value."""
    try:
        chunk_id = chunk_id.strip()
        if not chunk_id:
            raise ValueError("chunk_id must not be empty")
        limit = _validate_limit(limit)
    except Exception as exc:
        return _tool_error_payload(
            "find_points_by_chunk_id",
            exc,
            chunk_id=chunk_id,
            limit=limit,
            config_path=config_path,
        )
    collection_name, error = _resolve_collection_context("find_points_by_chunk_id", collection_name, config_path)
    if error is not None:
        return error
    assert collection_name is not None
    response = _scroll_points(
        collection_name,
        filter_payload=_filter_match("chunk_id", chunk_id),
        limit=limit,
    )
    if not response.get("ok"):
        return _qdrant_error_payload(
            "find_points_by_chunk_id",
            response,
            collection_name=collection_name,
            chunk_id=chunk_id,
            limit=limit,
        )
    payload = response.get("json", {})
    result = payload.get("result", {}) if isinstance(payload, dict) else {}
    points = result.get("points", []) if isinstance(result, dict) else []
    return {
        "ok": True,
        "collection_name": collection_name,
        "chunk_id": chunk_id,
        "points": [_summarize_point(point) for point in points if isinstance(point, dict)],
        "count": len(points),
    }


@mcp.tool
def get_point_by_chunk_id(chunk_id: str, collection_name: str = "", config_path: str = "") -> dict[str, Any]:
    """Return the unique point for one chunk_id, and flag duplicate anomalies."""
    scan_limit = 10
    try:
        chunk_id = chunk_id.strip()
        if not chunk_id:
            raise ValueError("chunk_id must not be empty")
    except Exception as exc:
        return _tool_error_payload("get_point_by_chunk_id", exc, chunk_id=chunk_id, config_path=config_path)
    collection_name, error = _resolve_collection_context("get_point_by_chunk_id", collection_name, config_path)
    if error is not None:
        return error
    assert collection_name is not None
    response = _scroll_points(
        collection_name,
        filter_payload=_filter_match("chunk_id", chunk_id),
        limit=scan_limit,
    )
    if not response.get("ok"):
        return _qdrant_error_payload(
            "get_point_by_chunk_id",
            response,
            collection_name=collection_name,
            chunk_id=chunk_id,
        )
    payload = response.get("json", {})
    result = payload.get("result", {}) if isinstance(payload, dict) else {}
    points = [point for point in (result.get("points", []) if isinstance(result, dict) else []) if isinstance(point, dict)]
    summarized = [_summarize_point(point) for point in points]
    return {
        "ok": True,
        "collection_name": collection_name,
        "chunk_id": chunk_id,
        "found": len(points) > 0,
        "point": summarized[0] if len(points) == 1 else None,
        "duplicate_count": max(0, len(points) - 1),
        "anomaly": "duplicate_chunk_id" if len(points) > 1 else None,
        "duplicate_check_truncated": len(points) >= scan_limit,
        "scan_limit": scan_limit,
        "matches": summarized,
        "count": len(points),
    }


@mcp.tool
def find_points_by_content_hash(content_hash: str, collection_name: str = "", limit: int = 20, config_path: str = "") -> dict[str, Any]:
    """Return points whose payload content_hash matches one value."""
    try:
        content_hash = content_hash.strip()
        if not content_hash:
            raise ValueError("content_hash must not be empty")
        limit = _validate_limit(limit)
    except Exception as exc:
        return _tool_error_payload(
            "find_points_by_content_hash",
            exc,
            content_hash=content_hash,
            limit=limit,
            config_path=config_path,
        )
    collection_name, error = _resolve_collection_context("find_points_by_content_hash", collection_name, config_path)
    if error is not None:
        return error
    assert collection_name is not None
    response = _scroll_points(
        collection_name,
        filter_payload=_filter_match("content_hash", content_hash),
        limit=limit,
    )
    if not response.get("ok"):
        return _qdrant_error_payload(
            "find_points_by_content_hash",
            response,
            collection_name=collection_name,
            content_hash=content_hash,
            limit=limit,
        )
    payload = response.get("json", {})
    result = payload.get("result", {}) if isinstance(payload, dict) else {}
    points = result.get("points", []) if isinstance(result, dict) else []
    return {
        "ok": True,
        "collection_name": collection_name,
        "content_hash": content_hash,
        "points": [_summarize_point(point) for point in points if isinstance(point, dict)],
        "count": len(points),
    }


@mcp.tool
def find_points_by_document_id(document_id: str, collection_name: str = "", limit: int = 20, config_path: str = "") -> dict[str, Any]:
    """Return points whose payload doc_id matches one value."""
    try:
        document_id = document_id.strip()
        if not document_id:
            raise ValueError("document_id must not be empty")
        limit = _validate_limit(limit)
    except Exception as exc:
        return _tool_error_payload(
            "find_points_by_document_id",
            exc,
            document_id=document_id,
            limit=limit,
            config_path=config_path,
        )
    collection_name, error = _resolve_collection_context("find_points_by_document_id", collection_name, config_path)
    if error is not None:
        return error
    assert collection_name is not None
    response = _scroll_points(
        collection_name,
        filter_payload=_filter_match("doc_id", document_id),
        limit=limit,
    )
    if not response.get("ok"):
        return _qdrant_error_payload(
            "find_points_by_document_id",
            response,
            collection_name=collection_name,
            document_id=document_id,
            limit=limit,
        )
    payload = response.get("json", {})
    result = payload.get("result", {}) if isinstance(payload, dict) else {}
    points = result.get("points", []) if isinstance(result, dict) else []
    return {
        "ok": True,
        "collection_name": collection_name,
        "document_id": document_id,
        "points": [_summarize_point(point) for point in points if isinstance(point, dict)],
        "count": len(points),
    }


@mcp.tool
def get_retrieval_payload_health(collection_name: str = "", sample_limit: int = 25, config_path: str = "") -> dict[str, Any]:
    """Sample one collection and report payload-shape health for retrieval debugging."""
    try:
        sample_limit = _validate_limit(sample_limit)
    except Exception as exc:
        return _tool_error_payload(
            "get_retrieval_payload_health",
            exc,
            sample_limit=sample_limit,
            config_path=config_path,
        )
    collection_name, error = _resolve_collection_context("get_retrieval_payload_health", collection_name, config_path)
    if error is not None:
        return error
    assert collection_name is not None
    response = _scroll_points(collection_name, limit=sample_limit)
    if not response.get("ok"):
        return _qdrant_error_payload(
            "get_retrieval_payload_health",
            response,
            collection_name=collection_name,
            sample_limit=sample_limit,
        )
    payload = response.get("json", {})
    result = payload.get("result", {}) if isinstance(payload, dict) else {}
    points = [point for point in (result.get("points", []) if isinstance(result, dict) else []) if isinstance(point, dict)]

    required_fields = _required_chunk_payload_fields()
    missing_field_counts = {field: 0 for field in required_fields}
    duplicate_chunk_ids: dict[str, int] = {}
    seen_chunk_ids: dict[str, int] = {}
    invalid_page_ranges = 0

    for point in points:
        summarized = _summarize_point(point)
        payload_obj = summarized["payload"] if isinstance(summarized["payload"], dict) else {}
        for field in required_fields:
            value = payload_obj.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing_field_counts[field] += 1
        chunk_id = payload_obj.get("chunk_id")
        if isinstance(chunk_id, str) and chunk_id.strip():
            seen_chunk_ids[chunk_id] = seen_chunk_ids.get(chunk_id, 0) + 1
        page_start = payload_obj.get("page_start")
        page_end = payload_obj.get("page_end")
        if isinstance(page_start, int) and isinstance(page_end, int) and page_end < page_start:
            invalid_page_ranges += 1

    for chunk_id, count in seen_chunk_ids.items():
        if count > 1:
            duplicate_chunk_ids[chunk_id] = count

    sample_empty = len(points) == 0
    health_ok = (
        not sample_empty
        and invalid_page_ranges == 0
        and len(duplicate_chunk_ids) == 0
        and all(count == 0 for count in missing_field_counts.values())
    )

    return {
        "ok": True,
        "collection_name": collection_name,
        "sample_limit": sample_limit,
        "sample_count": len(points),
        "sample_empty": sample_empty,
        "required_fields": required_fields,
        "missing_field_counts": missing_field_counts,
        "duplicate_chunk_ids": duplicate_chunk_ids,
        "invalid_page_range_count": invalid_page_ranges,
        "healthy_sample": health_ok,
        "health_interpretation": "insufficient_sample" if sample_empty else "evaluated",
    }


if __name__ == "__main__":
    mcp.run()

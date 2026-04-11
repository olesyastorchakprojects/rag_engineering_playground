from __future__ import annotations

from pathlib import Path

from Tools.mcp.qdrant import server


def test_default_collection_name_matches_ingest_config() -> None:
    assert server._default_collection_name() == "chunks_dense_qwen3"


def test_validate_limit_caps_large_values() -> None:
    assert server._validate_limit(1000) == 100


def test_collection_info_summary_extracts_metadata() -> None:
    payload = {
        "result": {
            "status": "green",
            "optimizer_status": "ok",
            "points_count": 10,
            "indexed_vectors_count": 10,
            "segments_count": 1,
            "config": {
                "params": {
                    "vectors": {
                        "size": 1024,
                        "distance": "Cosine",
                    },
                    "on_disk_payload": True,
                },
                "metadata": {
                    "embedding_model_name": "qwen3-embedding:0.6b",
                },
            },
            "payload_schema": {},
        }
    }
    summary = server._collection_info_from_response("chunks_dense_qwen3", payload)
    assert summary["vector_size"] == 1024
    assert summary["vector_distance"] == "Cosine"
    assert summary["metadata"]["embedding_model_name"] == "qwen3-embedding:0.6b"


def test_collection_info_summary_marks_named_vector_layout() -> None:
    payload = {
        "result": {
            "config": {
                "params": {
                    "vectors": {
                        "dense": {
                            "size": 1024,
                            "distance": "Cosine",
                        }
                    }
                }
            }
        }
    }
    summary = server._collection_info_from_response("chunks_dense_qwen3", payload)
    assert summary["vector_layout"] == "named_or_multivector"
    assert summary["vector_size"] is None
    assert summary["raw_vectors_config"] == {"dense": {"size": 1024, "distance": "Cosine"}}


def test_collection_info_summary_extracts_sparse_vectors() -> None:
    payload = {
        "result": {
            "config": {
                "params": {
                    "vectors": {
                        "dense": {
                            "size": 1024,
                            "distance": "Cosine",
                        }
                    },
                    "sparse_vectors": {
                        "sparse": {}
                    },
                },
                "metadata": {
                    "sparse_strategy_kind": "bag_of_words",
                },
            }
        }
    }
    summary = server._collection_info_from_response("chunks_hybrid_qwen3_bow", payload)
    assert summary["raw_sparse_vectors_config"] == {"sparse": {}}
    assert summary["metadata"]["sparse_strategy_kind"] == "bag_of_words"


def test_summarize_point_exposes_payload_identity_fields() -> None:
    point = {
        "id": "point-1",
        "score": 0.99,
        "payload": {
            "chunk_id": "chunk-1",
            "doc_id": "doc-1",
            "document_title": "Doc",
        },
    }
    summary = server._summarize_point(point)
    assert summary["id"] == "point-1"
    assert summary["chunk_id"] == "chunk-1"
    assert summary["doc_id"] == "doc-1"


def test_filter_match_builds_qdrant_filter() -> None:
    assert server._filter_match("chunk_id", "abc") == {
        "must": [{"key": "chunk_id", "match": {"value": "abc"}}]
    }


def test_required_chunk_payload_fields_contains_core_retrieval_fields() -> None:
    fields = server._required_chunk_payload_fields()
    assert "chunk_id" in fields
    assert "text" in fields
    assert "content_hash" in fields


def test_resolve_config_path_defaults_to_ingest_toml() -> None:
    path = server._resolve_config_path()
    assert path == Path("/home/olesia/code/prompt_gen_proj/Execution/ingest/dense/ingest.toml")


def test_default_collection_name_for_hybrid_config_is_derived() -> None:
    path = "Execution/ingest/hybrid/ingest.toml"
    assert server._default_collection_name(path) == "chunks_hybrid_qwen3_bow"


def test_compatibility_signals_for_hybrid_collection(monkeypatch) -> None:
    monkeypatch.setattr(
        server,
        "_load_ingest_config",
        lambda config_path="": {
            "embedding": {"model": {"name": "qwen3-embedding:0.6b", "dimension": 1024}},
            "sparse": {"strategy": {"kind": "bag_of_words", "version": "v1"}},
            "qdrant": {
                "collection": {
                    "name": "chunks_hybrid_qwen3",
                    "distance": "Cosine",
                    "dense_vector_name": "dense",
                    "sparse_vector_name": "sparse",
                }
            },
        },
    )
    monkeypatch.setattr(
        server,
        "_collection_info",
        lambda collection_name: {
            "collection_name": collection_name,
            "vector_size": None,
            "vector_distance": None,
            "raw_vectors_config": {"dense": {"size": 1024, "distance": "Cosine"}},
            "raw_sparse_vectors_config": {"sparse": {}},
            "metadata": {
                "embedding_model_name": "qwen3-embedding:0.6b",
                "sparse_strategy_kind": "bag_of_words",
                "sparse_strategy_version": "v1",
                "vocabulary_identity": {"collection_name": "chunks_hybrid_qwen3"},
            },
        },
    )
    result = server._compatibility_signals("chunks_hybrid_qwen3_bow", "Execution/ingest/hybrid/ingest.toml")
    assert result["compatible"] is True
    assert result["ingest_mode"] == "hybrid"
    assert result["checks"]["dense_vector_name_matches"] is True
    assert result["checks"]["sparse_vector_name_matches"] is True


def test_tool_error_payload_shape() -> None:
    payload = server._tool_error_payload("demo", ValueError("bad input"), chunk_id="x")
    assert payload["ok"] is False
    assert payload["operation"] == "demo"
    assert payload["error_type"] == "ValueError"
    assert payload["context"]["chunk_id"] == "x"


def test_get_sample_points_returns_structured_error_for_invalid_limit() -> None:
    result = server.get_sample_points(limit=0)
    assert result["ok"] is False
    assert result["operation"] == "get_sample_points"
    assert result["error_type"] == "ValueError"


def test_get_point_by_chunk_id_returns_structured_error_for_missing_chunk_id() -> None:
    result = server.get_point_by_chunk_id("")
    assert result["ok"] is False
    assert result["operation"] == "get_point_by_chunk_id"


def test_get_retrieval_payload_health_empty_sample_is_not_healthy(monkeypatch) -> None:
    monkeypatch.setattr(server, "_resolve_collection_name", lambda collection_name="", config_path="": "chunks_dense_qwen3")
    monkeypatch.setattr(
        server,
        "_scroll_points",
        lambda collection_name, filter_payload=None, limit=10: {
            "ok": True,
            "json": {"result": {"points": []}},
        },
    )
    result = server.get_retrieval_payload_health()
    assert result["ok"] is True
    assert result["sample_empty"] is True
    assert result["healthy_sample"] is False
    assert result["health_interpretation"] == "insufficient_sample"


def test_get_point_by_chunk_id_marks_truncated_duplicate_check(monkeypatch) -> None:
    monkeypatch.setattr(server, "_resolve_collection_name", lambda collection_name="", config_path="": "chunks_dense_qwen3")
    monkeypatch.setattr(
        server,
        "_scroll_points",
        lambda collection_name, filter_payload=None, limit=10: {
            "ok": True,
            "json": {
                "result": {
                    "points": [
                        {"id": f"point-{index}", "payload": {"chunk_id": "chunk-1", "doc_id": "doc-1"}}
                        for index in range(10)
                    ]
                }
            },
        },
    )
    result = server.get_point_by_chunk_id("chunk-1")
    assert result["ok"] is True
    assert result["duplicate_check_truncated"] is True
    assert result["anomaly"] == "duplicate_chunk_id"

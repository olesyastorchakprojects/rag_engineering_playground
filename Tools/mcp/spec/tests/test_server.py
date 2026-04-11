from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server import (
    find_source_of_truth,
    get_spec_roots,
    get_topic_index,
    get_topic_sources,
    list_spec_documents,
    read_spec_document,
    search_spec_documents,
)


def test_get_spec_roots_has_specification() -> None:
    roots = get_spec_roots()
    assert roots["specification_root"] == "Specification"


def test_list_spec_documents_finds_eval_specs() -> None:
    result = list_spec_documents("Specification/codegen/evals")
    assert result["count"] > 0
    assert any(path.endswith("eval_orchestrator.md") for path in result["documents"])


def test_read_spec_document_reads_known_file() -> None:
    result = read_spec_document("Specification/architecture/evals_architecture.md")
    assert "Evals Architecture" in result["content"]


def test_search_spec_documents_finds_request_captures() -> None:
    result = search_spec_documents("request_captures", limit=10)
    assert result["count"] > 0


def test_get_topic_index_has_eval_engine() -> None:
    result = get_topic_index()
    assert "eval_engine" in result["topics"]


def test_get_topic_sources_returns_request_capture_sources() -> None:
    result = get_topic_sources("request_capture")
    assert "contracts" in result
    assert any(path.endswith("request_capture.md") for path in result["contracts"])


def test_find_source_of_truth_finds_dense_ingest() -> None:
    result = find_source_of_truth("dense_ingest")
    assert result["topic"] == "dense_ingest"


def test_find_source_of_truth_finds_retrieval_topic_with_new_docs() -> None:
    result = find_source_of_truth("retrieval")
    assert result["topic"] == "retrieval"
    codegen = result["sources"]["codegen"]
    assert "Specification/codegen/rag_runtime/retrieve/integration.md" in codegen
    assert "Specification/codegen/rag_runtime/retrieve/dense_retrieval.md" in codegen
    assert "Specification/codegen/rag_runtime/retrieve/hybrid_retrieval.md" in codegen

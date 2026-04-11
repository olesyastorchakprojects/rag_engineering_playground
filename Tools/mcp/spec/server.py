from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parents[3]
SPEC_ROOT = REPO_ROOT / "Specification"
SCHEMA_ROOTS = [
    REPO_ROOT / "Execution" / "schemas",
    REPO_ROOT / "Execution" / "ingest" / "schemas",
    REPO_ROOT / "Execution" / "rag_runtime" / "schemas",
    REPO_ROOT / "Execution" / "parsing" / "schemas",
    REPO_ROOT / "Execution" / "parsing" / "common",
    REPO_ROOT / "Execution" / "docker",
    REPO_ROOT / "Execution" / "docker" / "postgres" / "init",
    REPO_ROOT / "Execution" / "otel_runtime_smoke",
    REPO_ROOT / "Measurement" / "observability",
    REPO_ROOT / "Measurement" / "evals",
]

ALLOWED_ROOTS = [SPEC_ROOT, *SCHEMA_ROOTS]
ALLOWED_SUFFIXES = {".md", ".json", ".sql", ".yaml", ".yml", ".toml", ".py", ".rs"}
SPEC_INDEX_PATH = Path(__file__).resolve().parent / "spec_index.yaml"

mcp = FastMCP("spec")


def _to_repo_relative(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _iter_allowed_files() -> list[Path]:
    files: list[Path] = []
    for root in ALLOWED_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if any(part in {"target", "__pycache__"} for part in path.parts):
                continue
            if path.is_file() and path.suffix in ALLOWED_SUFFIXES:
                files.append(path)
    return sorted(files)


def _resolve_allowed_path(path: str) -> Path:
    candidate = (REPO_ROOT / path).resolve()
    if any(part in {"target", "__pycache__"} for part in candidate.parts):
        raise ValueError(f"Path points to excluded build/cache output: {path}")
    for root in ALLOWED_ROOTS:
        root_resolved = root.resolve()
        if candidate == root_resolved or root_resolved in candidate.parents:
            if candidate.is_file() and candidate.suffix in ALLOWED_SUFFIXES:
                return candidate
            raise ValueError(f"Path is not an allowed spec/schema file: {path}")
    raise ValueError(f"Path is outside allowed spec/schema roots: {path}")


def _load_spec_index() -> dict[str, Any]:
    with SPEC_INDEX_PATH.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError("spec_index.yaml must contain a top-level mapping")
    return data


def _get_topic_entry(topic: str) -> dict[str, Any]:
    data = _load_spec_index()
    topics = data.get("topics", {})
    if topic not in topics:
        raise ValueError(f"Unknown topic: {topic}")
    return topics[topic]


def _collect_kind_documents(kind: str) -> list[dict[str, Any]]:
    data = _load_spec_index()
    topics = data.get("topics", {})
    documents: list[dict[str, Any]] = []
    for topic_name, topic_data in topics.items():
        values = topic_data.get(kind, [])
        if not isinstance(values, list):
            continue
        for path in values:
            documents.append(
                {
                    "topic": topic_name,
                    "path": path,
                }
            )
    return documents


@mcp.tool
def get_spec_roots() -> dict[str, Any]:
    """Return canonical spec and schema roots."""
    return {
        "specification_root": _to_repo_relative(SPEC_ROOT),
        "schema_roots": [_to_repo_relative(root) for root in SCHEMA_ROOTS if root.exists()],
    }


@mcp.tool
def get_topic_index() -> dict[str, Any]:
    """Return the curated topic index for repository specs and schemas."""
    data = _load_spec_index()
    topics = sorted(data.get("topics", {}).keys())
    return {
        "topics": topics,
        "count": len(topics),
    }


@mcp.tool
def list_spec_documents(prefix: str = "") -> dict[str, Any]:
    """
    List spec and schema documents.
    If prefix is provided, only return repo-relative paths starting with that prefix.
    """
    prefix = prefix.strip()
    documents = []
    for path in _iter_allowed_files():
        relative = _to_repo_relative(path)
        if prefix and not relative.startswith(prefix):
            continue
        documents.append(relative)
    return {
        "prefix": prefix,
        "documents": documents,
        "count": len(documents),
    }


@mcp.tool
def read_spec_document(path: str) -> dict[str, Any]:
    """Read one allowed spec or schema document by repo-relative path."""
    resolved = _resolve_allowed_path(path)
    content = resolved.read_text(encoding="utf-8")
    return {
        "path": _to_repo_relative(resolved),
        "content": content,
    }


@mcp.tool
def get_topic_sources(topic: str) -> dict[str, Any]:
    """Return curated spec, contract, schema, and related sources for one topic."""
    topic_data = _get_topic_entry(topic)
    legacy_contracts: list[str] = []
    for key in [
        "data_contracts",
        "storage_contracts",
        "config_contracts",
        "env_contracts",
        "external_service_contracts",
    ]:
        values = topic_data.get(key, [])
        if isinstance(values, list):
            legacy_contracts.extend(values)
    return {
        "topic": topic,
        "contracts": legacy_contracts,
        **topic_data,
    }


@mcp.tool
def find_source_of_truth(name: str) -> dict[str, Any]:
    """
    Return the best curated source-of-truth mapping for a topic-like name.
    Exact topic-name match is preferred; otherwise fall back to simple substring matching.
    """
    data = _load_spec_index()
    topics = data.get("topics", {})
    lowered = name.strip().lower()

    if lowered in topics:
        return {
            "query": name,
            "match_type": "exact_topic",
            "topic": lowered,
            "sources": topics[lowered],
        }

    for topic_name, topic_data in topics.items():
        if lowered in topic_name.lower():
            return {
                "query": name,
                "match_type": "substring_topic",
                "topic": topic_name,
                "sources": topic_data,
            }

    raise ValueError(f"No curated source-of-truth topic found for: {name}")


@mcp.tool
def find_related_docs(topic: str) -> dict[str, Any]:
    """Return related documents for one known topic grouped by document kind."""
    data = get_topic_sources(topic)
    related = {}
    for key, value in data.items():
        if key in {"topic", "description"}:
            continue
        related[key] = value
    return {
        "topic": topic,
        "description": data.get("description"),
        "related": related,
    }


@mcp.tool
def list_documents_by_kind(kind: str) -> dict[str, Any]:
    """
    Return all curated documents of one kind across topics.
    Example kinds: data_contracts, config_schemas, test_specs, implementation_references.
    """
    kind = kind.strip()
    if not kind:
        raise ValueError("kind must not be empty")

    documents = _collect_kind_documents(kind)
    return {
        "kind": kind,
        "documents": documents,
        "count": len(documents),
    }


@mcp.tool
def get_generation_context(topic: str) -> dict[str, Any]:
    """
    Return the curated minimum document set most relevant for code generation for one topic.
    """
    topic_data = _get_topic_entry(topic)
    ordered_keys = [
        "primary_source_of_truth",
        "architecture",
        "codegen",
        "data_contracts",
        "storage_contracts",
        "config_contracts",
        "env_contracts",
        "external_service_contracts",
        "prompt_specs",
        "data_schemas",
        "storage_schemas",
        "config_schemas",
        "env_schemas",
        "runtime_metadata",
        "validators",
        "strong_references",
        "secondary_references",
        "implementation_references",
    ]

    primary_docs: list[str] = []
    supporting_docs: list[str] = []
    for key in ordered_keys:
        values = topic_data.get(key, [])
        if not isinstance(values, list) or not values:
            continue
        if key in {
            "primary_source_of_truth",
            "architecture",
            "codegen",
            "data_contracts",
            "storage_contracts",
            "config_contracts",
            "env_contracts",
            "external_service_contracts",
            "prompt_specs",
        }:
            primary_docs.extend(values)
        else:
            supporting_docs.extend(values)

    return {
        "topic": topic,
        "description": topic_data.get("description"),
        "related_topics": topic_data.get("related_topics", []),
        "primary_docs": primary_docs,
        "supporting_docs": supporting_docs,
    }


@mcp.tool
def get_validation_context(topic: str) -> dict[str, Any]:
    """
    Return the curated minimum document set most relevant for validating generated output for one topic.
    """
    topic_data = _get_topic_entry(topic)
    ordered_keys = [
        "primary_source_of_truth",
        "test_specs",
        "data_schemas",
        "storage_schemas",
        "config_schemas",
        "env_schemas",
        "validators",
        "strong_references",
        "secondary_references",
        "implementation_references",
        "incident_reports",
    ]

    primary_docs: list[str] = []
    supporting_docs: list[str] = []
    for key in ordered_keys:
        values = topic_data.get(key, [])
        if not isinstance(values, list) or not values:
            continue
        if key in {
            "primary_source_of_truth",
            "test_specs",
            "data_schemas",
            "storage_schemas",
            "config_schemas",
            "env_schemas",
            "validators",
        }:
            primary_docs.extend(values)
        else:
            supporting_docs.extend(values)

    return {
        "topic": topic,
        "description": topic_data.get("description"),
        "related_topics": topic_data.get("related_topics", []),
        "validation_risks": topic_data.get("validation_risks", []),
        "primary_docs": primary_docs,
        "supporting_docs": supporting_docs,
    }


@mcp.tool
def search_spec_documents(query: str, limit: int = 20) -> dict[str, Any]:
    """
    Search spec and schema documents by repo-relative path fragment or text content.
    """
    lowered = query.strip().lower()
    if not lowered:
        return {"query": query, "results": [], "count": 0}

    results = []
    for path in _iter_allowed_files():
        relative = _to_repo_relative(path)
        content = path.read_text(encoding="utf-8")
        haystacks = [relative.lower(), content.lower()]
        if any(lowered in haystack for haystack in haystacks):
            results.append(
                {
                    "path": relative,
                    "matched_path": lowered in relative.lower(),
                    "matched_content": lowered in content.lower(),
                }
            )
        if len(results) >= limit:
            break

    return {
        "query": query,
        "results": results,
        "count": len(results),
    }


if __name__ == "__main__":
    mcp.run()

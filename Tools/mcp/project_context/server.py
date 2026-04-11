from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastmcp import FastMCP

ROOT = Path(__file__).resolve().parent
CONTEXT_PATH = ROOT / "context.yaml"

mcp = FastMCP("project-context")


def load_context() -> dict[str, Any]:
    with CONTEXT_PATH.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError("context.yaml must contain a top-level mapping")
    return data


@mcp.tool
def get_project_context() -> dict[str, Any]:
    """Return the full project operating context."""
    return load_context()


@mcp.tool
def get_system_roles() -> dict[str, Any]:
    """Return service roles and responsibilities."""
    return load_context()["system_roles"]


@mcp.tool
def get_operational_defaults() -> dict[str, Any]:
    """Return default local runtime and deployment assumptions."""
    return load_context()["operational_defaults"]


@mcp.tool
def get_data_flow() -> list[dict[str, Any]]:
    """Return the canonical high-level data flow."""
    return load_context()["data_flow"]


@mcp.tool
def get_debugging_defaults() -> dict[str, Any]:
    """Return default debugging and observability priorities."""
    return load_context()["debugging_defaults"]


@mcp.tool
def get_language_boundaries() -> dict[str, Any]:
    """Return preferred Rust/Python ownership boundaries."""
    return load_context()["language_boundaries"]


@mcp.tool
def get_storage_owner(name: str) -> dict[str, Any]:
    """
    Return which system or module operationally owns a given storage concern.
    Examples: qdrant, postgres, request_captures, request_summaries, chunks.
    """
    context = load_context()
    system_roles = context["system_roles"]
    lowered = name.strip().lower()

    def _record_matches(record: Any) -> bool:
        if not isinstance(record, dict):
            return False
        candidates = [
            record.get("name", ""),
            record.get("logical_name", ""),
        ]
        return any(candidate.lower() == lowered for candidate in candidates if candidate)

    for system_name, details in system_roles.items():
        stores = any(_record_matches(item) for item in details.get("stores", []))
        writes = any(_record_matches(item) for item in details.get("writes", []))
        reads = any(_record_matches(item) for item in details.get("reads", []))
        if (
            lowered == system_name.lower()
            or stores
            or writes
            or reads
        ):
            return {
                "query": name,
                "owner": system_name,
                "details": details,
            }

    return {
        "query": name,
        "owner": None,
        "details": None,
        "note": "No owner found in project context",
    }


@mcp.tool
def get_routing_policy() -> dict[str, Any]:
    """Return which MCP should be consulted first for different question types."""
    return load_context()["decision_rules"]


if __name__ == "__main__":
    mcp.run()

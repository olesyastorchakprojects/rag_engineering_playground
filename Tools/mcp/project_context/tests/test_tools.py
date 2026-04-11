from __future__ import annotations

from server import (
    get_operational_defaults,
    get_routing_policy,
    get_storage_owner,
    load_context,
)


def test_context_has_system_roles() -> None:
    data = load_context()
    assert "system_roles" in data
    assert "qdrant" in data["system_roles"]
    assert "postgres" in data["system_roles"]


def test_context_has_operational_defaults() -> None:
    defaults = get_operational_defaults()
    assert "local_observability_stack" in defaults
    assert defaults["local_observability_stack"]["source_path"] == "Execution/docker"
    assert defaults["agent_runtime_environment"]["known_default_env"]["RUST_LOG"] == "warn"


def test_get_storage_owner_matches_logical_name() -> None:
    owner = get_storage_owner("primary_chunk_collection")
    assert owner["owner"] == "dense_ingest"


def test_routing_policy_comes_from_context() -> None:
    routing = get_routing_policy()
    assert "when_question_is_about" in routing
    assert routing["when_question_is_about"]["service_roles"] == "project_context_mcp"


def test_debugging_defaults_include_cli_trace_visibility_rule() -> None:
    data = load_context()
    debugging = data["debugging_defaults"]
    assert debugging["cli_trace_visibility"]["default_agent_rust_log"] == "warn"
    assert "rag_runtime=info" in debugging["cli_trace_visibility"]["suggested_values"]


def test_debugging_defaults_capture_sparse_metrics_limitation() -> None:
    data = load_context()
    limitation = data["debugging_defaults"]["local_metrics_limitations"]
    assert limitation["known_tail_example_ms"] == 2500
    assert "Phoenix traces" in limitation["interpretation_rule"]

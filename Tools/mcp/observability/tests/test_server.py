from __future__ import annotations

from Tools.mcp.observability.server import (
    get_collector_pipeline_summary,
    get_dashboard_details,
    get_dashboard_catalog,
    get_datasource_configs,
    get_observability_roots,
    get_runtime_endpoints,
)


def test_roots_present() -> None:
    roots = get_observability_roots()
    assert "Measurement/observability" in roots["roots"]
    assert "Measurement/evals" in roots["roots"]
    assert "Execution/docker" in roots["roots"]


def test_dashboard_catalog_non_empty() -> None:
    catalog = get_dashboard_catalog()
    assert catalog["count"] >= 1


def test_datasources_non_empty() -> None:
    datasources = get_datasource_configs()
    assert datasources["count"] >= 1


def test_runtime_endpoints_include_tempo() -> None:
    endpoints = get_runtime_endpoints()
    assert "tempo_http" in endpoints["endpoints"]
    assert endpoints["derived_from"] == "Execution/docker/compose.yaml"


def test_dashboard_details_by_uid() -> None:
    details = get_dashboard_details("rag-request-overview")
    assert details["uid"] == "rag-request-overview"
    assert details["source_group"] == "runtime"
    assert details["panel_count"] >= 1


def test_dashboard_catalog_includes_eval_dashboards() -> None:
    catalog = get_dashboard_catalog()
    assert any(entry["source_group"] == "evals" for entry in catalog["dashboards"])


def test_collector_pipeline_summary_contains_traces_pipeline() -> None:
    summary = get_collector_pipeline_summary()
    assert "traces" in summary["pipelines"]
    assert "otlp/tempo" in summary["exporters"]

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml
from fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parents[3]
OBS_ROOTS = [
    REPO_ROOT / "Measurement" / "observability",
    REPO_ROOT / "Measurement" / "evals",
    REPO_ROOT / "Execution" / "docker",
]
ALLOWED_ROOTS = OBS_ROOTS
ALLOWED_SUFFIXES = {".md", ".json", ".yaml", ".yml"}
EXCLUDED_DIRS = {"__pycache__", "target", ".git"}

DOCKER_COMPOSE_PATH = REPO_ROOT / "Execution" / "docker" / "compose.yaml"
OTEL_COLLECTOR_CONFIG_PATH = REPO_ROOT / "Execution" / "docker" / "otel" / "otel-collector-config.yaml"
TEMPO_CONFIG_PATH = REPO_ROOT / "Measurement" / "observability" / "tempo" / "tempo.yaml"
GRAFANA_DASHBOARD_DIRS = [
    REPO_ROOT / "Measurement" / "observability" / "grafana" / "dashboards",
    REPO_ROOT / "Measurement" / "evals" / "grafana" / "dashboards",
]
GRAFANA_DATASOURCE_DIRS = [
    REPO_ROOT / "Measurement" / "observability" / "grafana" / "provisioning" / "datasources",
    REPO_ROOT / "Measurement" / "evals" / "grafana" / "provisioning" / "datasources",
]

LIVE_ENDPOINTS = {
    "tempo_ready": "http://localhost:3200/ready",
    "grafana_health": "http://localhost:3001/api/health",
    "prometheus_ready": "http://localhost:9090/-/ready",
    "prometheus_targets": "http://localhost:9090/api/v1/targets",
    "phoenix_root": "http://localhost:6006/",
}

STARTUP_ASSUMPTIONS = {
    "recommended_order": [
        "tempo",
        "phoenix",
        "otel-collector",
        "prometheus",
        "grafana",
    ],
    "collector_dependency_rule": "otel-collector should start after Phoenix and Tempo are up.",
    "prometheus_dependency_rule": "prometheus scrapes otel-collector metrics and can start after the collector is available.",
    "tempo_warmup": {
        "service": "tempo",
        "wait_seconds": 15,
        "reason": "Tempo needs warmup time before readiness and trace ingestion checks are reliable.",
    },
}

mcp = FastMCP("observability")


def _to_repo_relative(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _iter_allowed_files() -> list[Path]:
    files: list[Path] = []
    for root in ALLOWED_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if any(part in EXCLUDED_DIRS for part in path.parts):
                continue
            if path.is_file() and path.suffix in ALLOWED_SUFFIXES:
                files.append(path)
    return sorted(files)


def _resolve_allowed_path(path: str) -> Path:
    candidate = (REPO_ROOT / path).resolve()
    if any(part in EXCLUDED_DIRS for part in candidate.parts):
        raise ValueError(f"Path points to excluded build/cache output: {path}")
    for root in ALLOWED_ROOTS:
        root_resolved = root.resolve()
        if candidate == root_resolved or root_resolved in candidate.parents:
            if candidate.is_file() and candidate.suffix in ALLOWED_SUFFIXES:
                return candidate
            raise ValueError(f"Path is not an allowed observability file: {path}")
    raise ValueError(f"Path is outside allowed observability roots: {path}")


def _read_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_document(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _service_port_map(compose: dict[str, Any]) -> dict[str, list[str]]:
    services = compose.get("services", {}) or {}
    mapped: dict[str, list[str]] = {}
    for service_name, service in services.items():
        ports = service.get("ports", []) or []
        service_ports: list[str] = []
        for port in ports:
            if isinstance(port, str):
                service_ports.append(port)
        mapped[service_name] = service_ports
    return mapped


def _host_port_for(compose: dict[str, Any], service_name: str, container_port: int) -> int | None:
    for mapping in _service_port_map(compose).get(service_name, []):
        parts = mapping.split(":")
        if len(parts) < 2:
            continue
        host_part = parts[0].strip().strip('"')
        container_part = parts[-1].strip().strip('"')
        try:
            if int(container_part) == container_port:
                return int(host_part)
        except ValueError:
            continue
    return None


def _collector_exporter_endpoints(collector: dict[str, Any]) -> dict[str, Any]:
    exporters = collector.get("exporters", {}) or {}
    summary: dict[str, Any] = {}
    for exporter_name, config in exporters.items():
        if not isinstance(config, dict):
            continue
        summary[exporter_name] = {
            "endpoint": config.get("endpoint"),
            "tls_insecure": (config.get("tls") or {}).get("insecure"),
        }
    return summary


def _derived_live_endpoints() -> dict[str, str]:
    if not DOCKER_COMPOSE_PATH.exists():
        return dict(LIVE_ENDPOINTS)

    compose = _read_yaml(DOCKER_COMPOSE_PATH) or {}
    derived = dict(LIVE_ENDPOINTS)

    tempo_port = _host_port_for(compose, "tempo", 3200)
    grafana_port = _host_port_for(compose, "grafana", 3000)
    prometheus_port = _host_port_for(compose, "prometheus", 9090)
    phoenix_ui_port = _host_port_for(compose, "phoenix", 6006)

    if tempo_port is not None:
        derived["tempo_ready"] = f"http://localhost:{tempo_port}/ready"
    if grafana_port is not None:
        derived["grafana_health"] = f"http://localhost:{grafana_port}/api/health"
    if prometheus_port is not None:
        derived["prometheus_ready"] = f"http://localhost:{prometheus_port}/-/ready"
        derived["prometheus_targets"] = f"http://localhost:{prometheus_port}/api/v1/targets"
    if phoenix_ui_port is not None:
        derived["phoenix_root"] = f"http://localhost:{phoenix_ui_port}/"

    return derived


def _http_get(url: str, accept: str = "application/json") -> dict[str, Any]:
    request = Request(url, headers={"Accept": accept, "User-Agent": "prompt-gen-observability-mcp/1.0"})
    try:
        with urlopen(request, timeout=2.5) as response:
            body = response.read().decode("utf-8", errors="replace")
            return {
                "ok": True,
                "status_code": getattr(response, "status", 200),
                "body": body,
                "headers": dict(response.headers.items()),
            }
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {
            "ok": False,
            "status_code": exc.code,
            "error": str(exc),
            "body": body,
        }
    except URLError as exc:
        return {
            "ok": False,
            "status_code": None,
            "error": str(exc),
        }
    except Exception as exc:  # pragma: no cover - defensive runtime fallback
        return {
            "ok": False,
            "status_code": None,
            "error": str(exc),
        }


def _maybe_parse_json(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return None


def _prometheus_target_for_job(targets_payload: dict[str, Any], job_name: str) -> dict[str, Any] | None:
    data = targets_payload.get("data", {}) if isinstance(targets_payload, dict) else {}
    active = data.get("activeTargets", []) if isinstance(data, dict) else []
    for target in active:
        labels = target.get("labels", {}) if isinstance(target, dict) else {}
        if labels.get("job") == job_name:
            return target
    return None


def _flatten_panel_titles(panels: list[dict[str, Any]]) -> list[str]:
    titles: list[str] = []
    for panel in panels:
        if not isinstance(panel, dict):
            continue
        title = panel.get("title")
        if isinstance(title, str) and title.strip():
            titles.append(title.strip())
        nested = panel.get("panels")
        if isinstance(nested, list):
            titles.extend(_flatten_panel_titles(nested))
    return titles


def _dashboard_catalog_entries() -> list[dict[str, Any]]:
    dashboards = []
    for dashboard_dir in GRAFANA_DASHBOARD_DIRS:
        if not dashboard_dir.exists():
            continue
        for path in sorted(dashboard_dir.glob("*.json")):
            payload = _read_json(path)
            title = payload.get("title")
            uid = payload.get("uid")
            tags = payload.get("tags", [])
            panels = payload.get("panels", [])
            panel_titles = _flatten_panel_titles(panels)
            dashboards.append(
                {
                    "path": _to_repo_relative(path),
                    "title": title,
                    "uid": uid,
                    "tags": tags,
                    "panel_count": len(panel_titles),
                    "panel_titles": panel_titles,
                    "payload": payload,
                    "source_group": "evals" if "Measurement/evals/" in _to_repo_relative(path) else "runtime",
                }
            )
    return dashboards


def _flatten_panels_with_queries(panels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for panel in panels:
        if not isinstance(panel, dict):
            continue
        targets = panel.get("targets", [])
        queries = []
        if isinstance(targets, list):
            for target in targets:
                if not isinstance(target, dict):
                    continue
                queries.append(
                    {
                        "ref_id": target.get("refId"),
                        "expr": target.get("expr"),
                        "legend": target.get("legendFormat"),
                    }
                )
        flat.append(
            {
                "title": panel.get("title"),
                "type": panel.get("type"),
                "datasource": panel.get("datasource"),
                "queries": queries,
            }
        )
        nested = panel.get("panels")
        if isinstance(nested, list):
            flat.extend(_flatten_panels_with_queries(nested))
    return flat


def _extract_active_targets(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    active = data.get("activeTargets", []) if isinstance(data, dict) else []
    return active if isinstance(active, list) else []


def _normalize_prometheus_target(target: dict[str, Any]) -> dict[str, Any]:
    labels = target.get("labels", {}) if isinstance(target, dict) else {}
    discovered = target.get("discoveredLabels", {}) if isinstance(target, dict) else {}
    return {
        "job": labels.get("job"),
        "scrape_url": target.get("scrapeUrl"),
        "health": target.get("health"),
        "last_error": target.get("lastError"),
        "last_scrape": target.get("lastScrape"),
        "labels": labels,
        "discovered_labels": discovered,
    }


def _extract_trace_search_hits(payload: Any) -> list[dict[str, Any]]:
    candidates: list[Any] = []
    if isinstance(payload, dict):
        if isinstance(payload.get("traces"), list):
            candidates = payload["traces"]
        else:
            data = payload.get("data")
            if isinstance(data, dict) and isinstance(data.get("traces"), list):
                candidates = data["traces"]
            elif isinstance(data, list):
                candidates = data
    elif isinstance(payload, list):
        candidates = payload

    hits: list[dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        hits.append(
            {
                "trace_id": item.get("traceID") or item.get("traceId") or item.get("id"),
                "root_name": item.get("rootTraceName") or item.get("rootName") or item.get("name"),
                "root_service_name": item.get("rootServiceName") or item.get("serviceName"),
                "start_time_unix_nano": item.get("startTimeUnixNano") or item.get("start_time_unix_nano"),
                "duration_ms": item.get("durationMs") or item.get("duration_ms"),
                "span_sets": item.get("spanSets"),
            }
        )
    return hits


@mcp.tool
def get_observability_roots() -> dict[str, Any]:
    """Return canonical observability roots in the repository and expected live endpoints."""
    return {
        "roots": [_to_repo_relative(root) for root in OBS_ROOTS if root.exists()],
        "grafana_dashboard_roots": [
            _to_repo_relative(root) for root in GRAFANA_DASHBOARD_DIRS if root.exists()
        ],
        "grafana_datasource_roots": [
            _to_repo_relative(root) for root in GRAFANA_DATASOURCE_DIRS if root.exists()
        ],
        "live_endpoints": _derived_live_endpoints(),
        "startup_assumptions": STARTUP_ASSUMPTIONS,
    }


@mcp.tool
def list_observability_documents(prefix: str = "") -> dict[str, Any]:
    """List observability config and asset documents under known roots."""
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
def read_observability_document(path: str) -> dict[str, Any]:
    """Read one allowed observability document by repo-relative path."""
    resolved = _resolve_allowed_path(path)
    return {
        "path": _to_repo_relative(resolved),
        "content": _read_document(resolved),
    }


@mcp.tool
def get_runtime_endpoints() -> dict[str, Any]:
    """Return the canonical local endpoints for the observability stack."""
    compose = _read_yaml(DOCKER_COMPOSE_PATH)
    services = compose.get("services", {})
    endpoints = {
        "tempo_http": None,
        "grafana_http": None,
        "prometheus_http": None,
        "phoenix_http": None,
        "otel_grpc": None,
        "otel_http": None,
        "prometheus_scrape_target_api": None,
    }

    tempo_port = _host_port_for(compose, "tempo", 3200)
    grafana_port = _host_port_for(compose, "grafana", 3000)
    prometheus_port = _host_port_for(compose, "prometheus", 9090)
    phoenix_ui_port = _host_port_for(compose, "phoenix", 6006)
    otel_grpc_port = _host_port_for(compose, "otel-collector", 4317)
    otel_http_port = _host_port_for(compose, "otel-collector", 4318)

    if tempo_port is not None:
        endpoints["tempo_http"] = f"http://localhost:{tempo_port}"
    if grafana_port is not None:
        endpoints["grafana_http"] = f"http://localhost:{grafana_port}"
    if prometheus_port is not None:
        endpoints["prometheus_http"] = f"http://localhost:{prometheus_port}"
    if phoenix_ui_port is not None:
        endpoints["phoenix_http"] = f"http://localhost:{phoenix_ui_port}"
    if otel_grpc_port is not None:
        endpoints["otel_grpc"] = f"http://localhost:{otel_grpc_port}"
    if otel_http_port is not None:
        endpoints["otel_http"] = f"http://localhost:{otel_http_port}"
    if prometheus_port is not None:
        endpoints["prometheus_scrape_target_api"] = f"http://localhost:{prometheus_port}/api/v1/targets"
    return {
        "endpoints": endpoints,
        "compose_services": sorted(services.keys()),
        "derived_from": _to_repo_relative(DOCKER_COMPOSE_PATH),
    }


@mcp.tool
def get_stack_config_summary() -> dict[str, Any]:
    """Return a compact summary of compose wiring, Tempo config, and OTEL collector exporters."""
    compose = _read_yaml(DOCKER_COMPOSE_PATH)
    tempo = _read_yaml(TEMPO_CONFIG_PATH)
    collector = _read_yaml(OTEL_COLLECTOR_CONFIG_PATH)

    services_summary = {}
    for service_name, service in compose.get("services", {}).items():
        services_summary[service_name] = {
            "container_name": service.get("container_name"),
            "ports": service.get("ports", []),
            "depends_on": service.get("depends_on", []),
            "volumes": service.get("volumes", []),
        }

    exporters = sorted((collector.get("exporters") or {}).keys())
    pipelines = collector.get("service", {}).get("pipelines", {})
    tempo_path = tempo.get("storage", {}).get("trace", {}).get("local", {}).get("path")
    tempo_http_port = tempo.get("server", {}).get("http_listen_port")

    return {
        "compose_path": _to_repo_relative(DOCKER_COMPOSE_PATH),
        "otel_collector_config_path": _to_repo_relative(OTEL_COLLECTOR_CONFIG_PATH),
        "tempo_config_path": _to_repo_relative(TEMPO_CONFIG_PATH),
        "services": services_summary,
        "collector_exporters": exporters,
        "collector_exporter_endpoints": _collector_exporter_endpoints(collector),
        "collector_pipelines": pipelines,
        "tempo_http_port": tempo_http_port,
        "tempo_local_trace_path": tempo_path,
        "startup_assumptions": STARTUP_ASSUMPTIONS,
    }


@mcp.tool
def get_dashboard_catalog() -> dict[str, Any]:
    """Return the curated Grafana dashboard catalog with lightweight metadata."""
    dashboards = []
    for entry in _dashboard_catalog_entries():
        dashboards.append(
            {
                "path": entry["path"],
                "title": entry["title"],
                "uid": entry["uid"],
                "tags": entry["tags"],
                "source_group": entry["source_group"],
                "panel_count": entry["panel_count"],
                "panel_titles": entry["panel_titles"],
            }
        )
    return {
        "dashboards": dashboards,
        "count": len(dashboards),
    }


@mcp.tool
def get_datasource_configs() -> dict[str, Any]:
    """Return Grafana datasource provisioning files and a compact datasource summary."""
    files = []
    datasources = []
    for datasource_dir in GRAFANA_DATASOURCE_DIRS:
        if not datasource_dir.exists():
            continue
        for path in sorted(datasource_dir.glob("*.y*ml")):
            payload = _read_yaml(path) or {}
            files.append(_to_repo_relative(path))
            for ds in payload.get("datasources", []) or []:
                datasources.append(
                    {
                        "file": _to_repo_relative(path),
                        "name": ds.get("name"),
                        "type": ds.get("type"),
                        "uid": ds.get("uid"),
                        "url": ds.get("url"),
                        "source_group": "evals" if "Measurement/evals/" in _to_repo_relative(path) else "runtime",
                    }
                )
    return {
        "files": files,
        "datasources": datasources,
        "count": len(datasources),
    }


@mcp.tool
def get_dashboard_details(uid_or_title: str) -> dict[str, Any]:
    """Return one Grafana dashboard plus flattened panel/query details by uid, title, or path fragment."""
    query = uid_or_title.strip().lower()
    if not query:
        raise ValueError("uid_or_title must not be empty")

    catalog = _dashboard_catalog_entries()
    exact_uid = next((d for d in catalog if str(d.get("uid", "")).lower() == query), None)
    exact_title = next((d for d in catalog if str(d.get("title", "")).lower() == query), None)
    path_match = next((d for d in catalog if query in d["path"].lower()), None)
    matched = exact_uid or exact_title or path_match
    if not matched:
        raise ValueError(f"No dashboard found for {uid_or_title!r}")

    payload = matched["payload"]
    panels = _flatten_panels_with_queries(payload.get("panels", []))
    datasources = []
    for panel in panels:
        datasource = panel.get("datasource")
        if datasource not in datasources:
            datasources.append(datasource)
    return {
        "query": uid_or_title,
        "matched_by": "uid" if exact_uid else "title" if exact_title else "path",
        "path": matched["path"],
        "title": matched["title"],
        "uid": matched["uid"],
        "tags": matched["tags"],
        "source_group": matched["source_group"],
        "panels": panels,
        "panel_count": len(panels),
        "datasources": datasources,
    }


@mcp.tool
def get_collector_pipeline_summary() -> dict[str, Any]:
    """Return a focused summary of OTEL collector receivers, processors, exporters, and pipelines."""
    collector = _read_yaml(OTEL_COLLECTOR_CONFIG_PATH) or {}
    return {
        "config_path": _to_repo_relative(OTEL_COLLECTOR_CONFIG_PATH),
        "receivers": sorted((collector.get("receivers") or {}).keys()),
        "processors": sorted((collector.get("processors") or {}).keys()),
        "exporters": sorted((collector.get("exporters") or {}).keys()),
        "exporter_endpoints": _collector_exporter_endpoints(collector),
        "pipelines": collector.get("service", {}).get("pipelines", {}),
        "startup_assumptions": STARTUP_ASSUMPTIONS,
    }


@mcp.tool
def get_prometheus_target_status(job_name: str = "") -> dict[str, Any]:
    """Return Prometheus scrape target health, optionally filtered by one job name."""
    job_name = job_name.strip()
    live_endpoints = _derived_live_endpoints()
    raw = _http_get(live_endpoints["prometheus_targets"])
    payload = _maybe_parse_json(raw.get("body", "")) if raw.get("ok") else None
    active_targets = _extract_active_targets(payload if isinstance(payload, dict) else {})

    targets = []
    for target in active_targets:
        normalized = _normalize_prometheus_target(target)
        if job_name and normalized.get("job") != job_name:
            continue
        targets.append(normalized)

    return {
        "job_name": job_name or None,
        "ok": raw.get("ok", False),
        "status_code": raw.get("status_code"),
        "target_count": len(targets),
        "targets": targets,
        "url": live_endpoints["prometheus_targets"],
        "error": raw.get("error"),
        "body_preview": None if payload is not None else raw.get("body", "")[:500],
    }


@mcp.tool
def get_live_stack_status() -> dict[str, Any]:
    """Check local observability HTTP surfaces; this is availability-oriented, not full telemetry-path validation."""
    live_endpoints = _derived_live_endpoints()
    prometheus_targets_raw = _http_get(live_endpoints["prometheus_targets"])
    prometheus_targets_payload = (
        _maybe_parse_json(prometheus_targets_raw.get("body", "")) if prometheus_targets_raw.get("ok") else None
    )
    otel_prometheus_target = (
        _prometheus_target_for_job(prometheus_targets_payload, "otel-collector")
        if isinstance(prometheus_targets_payload, dict)
        else None
    )
    checks = {
        "tempo": _http_get(live_endpoints["tempo_ready"], accept="text/plain"),
        "grafana": _http_get(live_endpoints["grafana_health"]),
        "prometheus": _http_get(live_endpoints["prometheus_ready"], accept="text/plain"),
        "otel_collector": {
            "ok": bool(otel_prometheus_target and otel_prometheus_target.get("health") == "up"),
            "status_code": prometheus_targets_raw.get("status_code"),
            "body": prometheus_targets_raw.get("body", ""),
            "error": prometheus_targets_raw.get("error"),
            "target": otel_prometheus_target,
        },
        "phoenix": _http_get(live_endpoints["phoenix_root"], accept="text/html"),
    }

    normalized = {}
    for name, result in checks.items():
        entry = {
            "ok": result.get("ok", False),
            "status_code": result.get("status_code"),
        }
        if "error" in result:
            entry["error"] = result["error"]
        body = result.get("body", "")
        if name == "grafana":
            parsed = _maybe_parse_json(body)
            if isinstance(parsed, dict):
                entry["health"] = parsed
        elif name in {"tempo", "prometheus"}:
            entry["body_preview"] = body[:120]
        elif name == "otel_collector":
            target = result.get("target")
            if isinstance(target, dict):
                entry["target"] = {
                    "scrape_url": target.get("scrapeUrl"),
                    "health": target.get("health"),
                    "last_error": target.get("lastError"),
                    "last_scrape": target.get("lastScrape"),
                }
            entry["body_preview"] = body[:240]
        else:
            entry["body_preview"] = body[:120]
        if name == "tempo":
            entry["check_semantics"] = "Tempo HTTP readiness endpoint; does not prove spans were ingested."
        elif name == "grafana":
            entry["check_semantics"] = "Grafana HTTP health endpoint; does not prove dashboards loaded expected data."
        elif name == "prometheus":
            entry["check_semantics"] = "Prometheus readiness endpoint; does not prove expected series are present."
        elif name == "otel_collector":
            entry["check_semantics"] = "Prometheus scrape health for otel-collector metrics target; does not prove OTLP exporters successfully delivered telemetry."
        elif name == "phoenix":
            entry["check_semantics"] = "Phoenix UI/root availability only; does not prove spans or traces are queryable."
        normalized[name] = entry

    return {
        "checks": normalized,
        "note": "Use get_tempo_trace(trace_id) for concrete trace verification when you already have a trace id.",
        "startup_assumptions": STARTUP_ASSUMPTIONS,
        "checked_endpoints": live_endpoints,
    }


@mcp.tool
def get_tempo_trace(trace_id: str) -> dict[str, Any]:
    """Fetch one trace payload from local Tempo by trace id."""
    trace_id = trace_id.strip()
    if not trace_id:
        raise ValueError("trace_id must not be empty")

    runtime_endpoints = get_runtime_endpoints().get("endpoints", {})
    tempo_http = runtime_endpoints.get("tempo_http") or "http://localhost:3200"
    url = f"{tempo_http}/api/traces/{trace_id}"
    result = _http_get(url)
    payload = _maybe_parse_json(result.get("body", "")) if result.get("ok") else None
    return {
        "trace_id": trace_id,
        "ok": result.get("ok", False),
        "status_code": result.get("status_code"),
        "url": url,
        "payload": payload,
        "error": result.get("error"),
        "body_preview": None if payload is not None else result.get("body", "")[:500],
    }


@mcp.tool
def find_trace_by_attribute(attribute: str, value: str) -> dict[str, Any]:
    """Best-effort Tempo trace search by attribute/value; strongest for request_id, weaker for other attributes."""
    attribute = attribute.strip()
    value = value.strip()
    if not attribute:
        raise ValueError("attribute must not be empty")
    if not value:
        raise ValueError("value must not be empty")

    if attribute == "trace_id":
        direct = get_tempo_trace(value)
        return {
            "attribute": attribute,
            "value": value,
            "supported_strength": "exact_trace_lookup",
            "note": "trace_id uses direct Tempo trace fetch rather than search",
            "attempts": [{"strategy": "direct_trace_fetch", "url": direct["url"], "ok": direct["ok"]}],
            "matches": [{"trace_id": value}] if direct.get("ok") and direct.get("payload") is not None else [],
            "direct_result": direct,
        }

    runtime_endpoints = get_runtime_endpoints().get("endpoints", {})
    tempo_http = runtime_endpoints.get("tempo_http") or "http://localhost:3200"
    attempts: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []

    search_urls: list[tuple[str, str]]
    if attribute == "request_id":
        search_urls = [
            ("tag_search", f"{tempo_http}/api/search?tags={quote(f'{attribute}={value}')}"),
        ]
    else:
        traceql_query = quote(f'{{ {attribute}="{value}" }}')
        search_urls = [
            ("tag_search", f"{tempo_http}/api/search?tags={quote(f'{attribute}={value}')}"),
            ("traceql_search_v2", f"{tempo_http}/api/search?q={traceql_query}"),
            ("traceql_search_legacy", f"{tempo_http}/api/v2/search?q={traceql_query}"),
        ]

    for strategy, url in search_urls:
        result = _http_get(url)
        payload = _maybe_parse_json(result.get("body", "")) if result.get("ok") else None
        hits = _extract_trace_search_hits(payload)
        attempts.append(
            {
                "strategy": strategy,
                "url": url,
                "ok": result.get("ok", False),
                "status_code": result.get("status_code"),
                "error": result.get("error"),
                "match_count": len(hits),
                "body_preview": None if payload is not None else result.get("body", "")[:240],
            }
        )
        if hits:
            matches = hits
            break

    return {
        "attribute": attribute,
        "value": value,
        "supported_strength": "strong_for_request_id" if attribute == "request_id" else "best_effort",
        "note": (
            "Tempo dedicated-column search is strongest for request_id; other attributes depend on backend search support."
        ),
        "attempts": attempts,
        "matches": matches,
        "match_count": len(matches),
    }


if __name__ == "__main__":
    mcp.run()

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parents[3]
CHECKS_PATH = Path(__file__).resolve().parent / "checks.yaml"
BACKLOG_PATH = REPO_ROOT / "BACKLOG.md"

mcp = FastMCP("spec_conformance")


def _read_repo_file(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _repo_file_exists(path: str) -> bool:
    return (REPO_ROOT / path).is_file()


def _normalize_repo_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    if normalized.startswith("/"):
        repo_relative = str(Path(normalized).resolve().relative_to(REPO_ROOT))
        return repo_relative.replace("\\", "/")
    return normalized


def _load_checks_manifest() -> dict[str, Any]:
    with CHECKS_PATH.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError("checks.yaml must contain a top-level mapping")
    return data


def _load_backlog_items() -> list[str]:
    if not BACKLOG_PATH.is_file():
        return []
    lines = BACKLOG_PATH.read_text(encoding="utf-8").splitlines()
    items = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
    return items


def _iter_module_checks(module: str) -> list[dict[str, Any]]:
    manifest = _load_checks_manifest()
    modules = manifest.get("modules", {})
    if module not in modules:
        raise ValueError(f"Unknown module: {module}")
    checks = modules[module].get("checks", [])
    if not isinstance(checks, list):
        raise ValueError(f"checks for module {module!r} must be a list")
    return checks


def _module_description(module: str) -> str:
    manifest = _load_checks_manifest()
    modules = manifest.get("modules", {})
    if module not in modules:
        raise ValueError(f"Unknown module: {module}")
    return str(modules[module].get("description", ""))


def _matches_patterns(path: str, rule: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    evidence: list[dict[str, Any]] = []
    exists_expected = rule.get("exists", True)
    exists_actual = _repo_file_exists(path)
    if exists_expected and not exists_actual:
        evidence.append(
            {
                "path": path,
                "kind": "code_or_spec",
                "detail": "Expected file is missing.",
            }
        )
        return False, evidence
    if not exists_actual:
        return True, evidence

    content = _read_repo_file(path)
    contains_all = rule.get("contains_all", [])
    contains_none = rule.get("contains_none", [])

    for needle in contains_all:
        if needle not in content:
            evidence.append(
                {
                    "path": path,
                    "kind": "code_or_spec",
                    "detail": f"Required pattern not found: {needle}",
                }
            )
            return False, evidence

    for needle in contains_none:
        if needle in content:
            evidence.append(
                {
                    "path": path,
                    "kind": "code_or_spec",
                    "detail": f"Forbidden pattern found: {needle}",
                }
            )
            return False, evidence

    if contains_all or contains_none or exists_expected:
        evidence.append(
            {
                "path": path,
                "kind": "code_or_spec",
                "detail": "Rule matched expected file/pattern state.",
            }
        )
    return True, evidence


def _evaluate_rule_set(rule_set: list[dict[str, Any]], default_kind: str) -> tuple[bool, list[dict[str, Any]]]:
    ok = True
    evidence: list[dict[str, Any]] = []
    for rule in rule_set:
        path = rule["path"]
        rule_ok, rule_evidence = _matches_patterns(path, rule)
        for item in rule_evidence:
            item["kind"] = default_kind
        evidence.extend(rule_evidence)
        ok = ok and rule_ok
    return ok, evidence


def _evaluate_test_coverage(check: dict[str, Any]) -> dict[str, Any]:
    test_paths = check.get("test_paths", [])
    if not test_paths:
        return {
            "coverage_status": "missing",
            "missing_paths": [],
            "covered_paths": [],
            "summary": "No curated test coverage is mapped for this check.",
        }
    covered_paths = [path for path in test_paths if _repo_file_exists(path)]
    missing_paths = [path for path in test_paths if not _repo_file_exists(path)]
    mode = check.get("test_mode", "any")
    covered = bool(covered_paths) if mode == "any" else not missing_paths
    return {
        "coverage_status": "covered" if covered else "missing",
        "missing_paths": missing_paths,
        "covered_paths": covered_paths,
        "summary": (
            "Curated test coverage paths exist."
            if covered
            else "Curated test coverage paths are missing or not mapped."
        ),
    }


def _match_backlog(check: dict[str, Any]) -> list[str]:
    items = _load_backlog_items()
    keywords = [keyword.lower() for keyword in check.get("backlog_keywords", [])]
    if not keywords:
        return []
    matches = []
    for item in items:
        lowered = item.lower()
        if any(keyword in lowered for keyword in keywords):
            matches.append(item)
    return matches


def _status_bucket(status: str) -> str:
    if status == "conforms":
        return "ok"
    if status in {"violates_spec", "undocumented_code"}:
        return "mismatch"
    return "needs_review"


def _evaluate_check(module: str, check: dict[str, Any]) -> dict[str, Any]:
    code_ok, code_evidence = _evaluate_rule_set(check.get("code_rules", []), "code")
    spec_ok, spec_evidence = _evaluate_rule_set(check.get("spec_rules", []), "spec")
    test_coverage = _evaluate_test_coverage(check)
    backlog_matches = _match_backlog(check)
    direction = check["direction"]

    if direction == "requirement":
        if not code_ok:
            status = "violates_spec"
            summary = check["status_text"]["violates_spec"]
        else:
            status = "conforms"
            summary = check["status_text"]["conforms"]
    elif direction == "capability":
        if not code_ok:
            status = "needs_review"
            summary = check["status_text"]["needs_review"]
        elif not spec_ok:
            status = "undocumented_code"
            summary = check["status_text"]["undocumented_code"]
        else:
            status = "conforms"
            summary = check["status_text"]["conforms"]
    else:
        raise ValueError(f"Unknown direction: {direction}")

    return {
        "id": check["id"],
        "module": module,
        "direction": direction,
        "category": check["category"],
        "confidence": check.get("confidence", "high"),
        "title": check["title"],
        "description": check["description"],
        "spec_paths": check.get("spec_paths", []),
        "code_paths": check.get("code_paths", []),
        "test_paths": check.get("test_paths", []),
        "status": status,
        "summary": summary,
        "evidence": [*code_evidence, *spec_evidence],
        "test_coverage": test_coverage,
        "known_issue": bool(backlog_matches),
        "backlog_matches": backlog_matches,
    }


def _render_module_checks(module: str) -> list[dict[str, Any]]:
    return [_evaluate_check(module, check) for check in _iter_module_checks(module)]


def _split_checks(entries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    requirements = [entry for entry in entries if entry["direction"] == "requirement"]
    capabilities = [entry for entry in entries if entry["direction"] == "capability"]
    return requirements, capabilities


def _find_check(check_id: str) -> tuple[str, dict[str, Any]]:
    manifest = _load_checks_manifest()
    modules = manifest.get("modules", {})
    for module, module_data in modules.items():
        for check in module_data.get("checks", []):
            if check["id"] == check_id:
                return module, check
    raise ValueError(f"Unknown check id: {check_id}")


def _change_analysis(entry: dict[str, Any], changed_files: set[str]) -> dict[str, Any]:
    code_changed = sorted(path for path in entry["code_paths"] if path in changed_files)
    spec_changed = sorted(path for path in entry["spec_paths"] if path in changed_files)
    test_changed = sorted(path for path in entry["test_paths"] if path in changed_files)
    related = bool(code_changed or spec_changed or test_changed)
    return {
        "related": related,
        "code_changed": code_changed,
        "spec_changed": spec_changed,
        "test_changed": test_changed,
        "spec_update_suspect": bool(code_changed and not spec_changed),
        "implementation_update_suspect": bool(spec_changed and not code_changed),
    }


@mcp.tool
def list_modules() -> dict[str, Any]:
    """Return modules currently covered by curated spec/code conformance checks."""
    manifest = _load_checks_manifest()
    modules = manifest.get("modules", {})
    entries = [
        {
            "module": module,
            "description": str(data.get("description", "")),
            "check_count": len(data.get("checks", [])),
        }
        for module, data in sorted(modules.items())
    ]
    return {
        "modules": entries,
        "count": len(entries),
    }


@mcp.tool
def list_spec_requirements(module: str) -> dict[str, Any]:
    """Return curated spec requirements plus current conformance state for one module."""
    requirements, _ = _split_checks(_render_module_checks(module))
    return {
        "module": module,
        "description": _module_description(module),
        "requirements": requirements,
        "count": len(requirements),
    }


@mcp.tool
def scan_code_capabilities(module: str) -> dict[str, Any]:
    """Return curated code capabilities plus documentation state for one module."""
    _, capabilities = _split_checks(_render_module_checks(module))
    return {
        "module": module,
        "description": _module_description(module),
        "capabilities": capabilities,
        "count": len(capabilities),
    }


@mcp.tool
def compare_spec_and_code(module: str) -> dict[str, Any]:
    """Compare curated spec requirements and code capabilities for one module."""
    entries = _render_module_checks(module)
    requirements, capabilities = _split_checks(entries)
    summary = {
        "ok": 0,
        "mismatch": 0,
        "needs_review": 0,
        "known_issues": 0,
        "missing_test_coverage": 0,
    }
    for entry in entries:
        summary[_status_bucket(entry["status"])] += 1
        if entry["known_issue"]:
            summary["known_issues"] += 1
        if entry["test_coverage"]["coverage_status"] != "covered":
            summary["missing_test_coverage"] += 1
    return {
        "module": module,
        "description": _module_description(module),
        "requirements": requirements,
        "capabilities": capabilities,
        "summary": summary,
        "count": len(entries),
    }


@mcp.tool
def list_known_mismatches(module: str = "") -> dict[str, Any]:
    """Return curated mismatches and undocumented code for one module or for all covered modules."""
    modules = [module] if module else [entry["module"] for entry in list_modules()["modules"]]
    mismatches: list[dict[str, Any]] = []
    for module_name in modules:
        report = compare_spec_and_code(module_name)
        for section in ("requirements", "capabilities"):
            for entry in report[section]:
                if entry["status"] in {"violates_spec", "undocumented_code"}:
                    mismatches.append(entry)
    return {
        "module": module,
        "mismatches": mismatches,
        "count": len(mismatches),
    }


@mcp.tool
def explain_check(check_id: str) -> dict[str, Any]:
    """Explain one curated check by id, including backlog and test-coverage context."""
    module, check = _find_check(check_id)
    return _evaluate_check(module, check)


@mcp.tool
def compare_changed_files(changed_files: list[str], module: str = "") -> dict[str, Any]:
    """Compare only checks touched by the supplied changed file list."""
    changed = {_normalize_repo_path(path) for path in changed_files if path.strip()}
    modules = [module] if module else [entry["module"] for entry in list_modules()["modules"]]
    affected: list[dict[str, Any]] = []
    for module_name in modules:
        for entry in _render_module_checks(module_name):
            analysis = _change_analysis(entry, changed)
            if analysis["related"]:
                affected.append(
                    {
                        **entry,
                        "change_analysis": analysis,
                    }
                )
    spec_update_suspects = [
        entry for entry in affected if entry["change_analysis"]["spec_update_suspect"]
    ]
    implementation_update_suspects = [
        entry for entry in affected if entry["change_analysis"]["implementation_update_suspect"]
    ]
    return {
        "module": module,
        "changed_files": sorted(changed),
        "affected_checks": affected,
        "spec_update_suspects": spec_update_suspects,
        "implementation_update_suspects": implementation_update_suspects,
        "count": len(affected),
    }


@mcp.tool
def find_uncovered_requirements(module: str) -> dict[str, Any]:
    """Return curated requirements/capabilities that have no mapped test coverage."""
    uncovered = []
    for entry in _render_module_checks(module):
        if entry["test_coverage"]["coverage_status"] != "covered":
            uncovered.append(entry)
    return {
        "module": module,
        "uncovered_checks": uncovered,
        "count": len(uncovered),
    }


if __name__ == "__main__":
    mcp.run()

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


DEFAULT_INPUT = Path("out/pages.jsonl")
DEFAULT_RULES = Path("data/rules/rules_metadata.json")


def fail(message: str) -> None:
    print(message)
    raise SystemExit(1)


def format_samples(values: Sequence[Any], max_samples: int) -> str:
    shown = ",".join(str(value) for value in values[:max_samples])
    suffix = ",..." if len(values) > max_samples else ""
    return f"samples=[{shown}{suffix}]"


def load_rows(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))
    except FileNotFoundError:
        fail(f"FAIL: input not found: {path}")
    except json.JSONDecodeError as exc:
        fail(f"FAIL: invalid JSONL: {exc}")
    if not rows:
        fail("FAIL: JSONL is empty")
    for row in rows:
        try:
            int(row["page"])
        except (KeyError, TypeError, ValueError):
            fail("FAIL: invalid page field")
    return rows


def load_rules(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        fail(f"FAIL: rules-metadata not found: {path}")
    except json.JSONDecodeError as exc:
        fail(f"FAIL: invalid rules-metadata JSON: {exc}")
    if not isinstance(payload, dict):
        fail("FAIL: rules-metadata root must be an object")
    rules = payload.get("rules")
    if not isinstance(rules, dict):
        fail("FAIL: rules-metadata.rules must be an object")
    return payload


def collapse_ws_lower(text: str) -> str:
    return " ".join((text or "").split()).lower()


def iter_enabled_rules(rules_metadata: Mapping[str, Any]) -> Iterable[Tuple[str, Mapping[str, Any]]]:
    rules = rules_metadata.get("rules", {})
    if not isinstance(rules, dict):
        return []
    skipped_rule_names = {"footer_page_number", "bottom_footnotes_after_separator_hrule"}
    for section in ("line", "block", "text"):
        section_rules = rules.get(section, [])
        if not isinstance(section_rules, list):
            continue
        for rule in section_rules:
            if (
                isinstance(rule, dict)
                and isinstance(rule.get("name"), str)
                and rule.get("enabled") is True
                and rule["name"] not in skipped_rule_names
            ):
                yield section, rule


def metric_hits_for_line_rule(rule: Mapping[str, Any], text: str) -> int:
    lines = text.splitlines() or [text]
    rule_type = rule.get("type")
    if rule_type == "line_prefix":
        count = 0
        for line in lines:
            stripped = line.lstrip()
            if any(stripped.startswith(prefix) for prefix in rule.get("prefixes", [])):
                count += 1
        return count
    if rule_type == "line_regex":
        regex = re.compile(rule["pattern"], re.I if rule.get("flags") == "i" else 0)
        return sum(1 for line in lines if regex.search(line))
    if rule_type == "line_equals":
        count = 0
        for line in lines:
            if rule.get("normalize") == "collapse_ws_lower":
                if collapse_ws_lower(line) == collapse_ws_lower(rule.get("value", "")):
                    count += 1
            elif line == rule.get("value"):
                count += 1
        return count
    return 0


def metric_hits_for_text_rule(rule: Mapping[str, Any], text: str) -> int:
    regex = re.compile(rule["pattern"], re.I if rule.get("flags") == "i" else 0)
    return sum(1 for _ in regex.finditer(text))


def metric_hits_for_block_rule(rule: Mapping[str, Any], text: str) -> Tuple[int, str]:
    anchor = rule.get("anchor")
    if not isinstance(anchor, dict):
        return 0, "unsupported"
    if anchor.get("kind") != "text_line_regex":
        return 0, "unsupported"
    where = anchor.get("where")
    if not isinstance(where, dict):
        return 0, "unsupported"
    if not isinstance(where.get("pattern"), str):
        return 0, "unsupported"
    if not isinstance(where.get("flags"), str):
        return 0, "unsupported"
    regex = re.compile(where["pattern"], re.I if where["flags"] == "i" else 0)
    lines = text.splitlines() or [text]
    return sum(1 for line in lines if regex.search(line)), "anchor_regex"


def metric_hits(section: str, rule: Mapping[str, Any], text: str) -> Tuple[int, str]:
    if section == "line":
        return metric_hits_for_line_rule(rule, text), "line_rule"
    if section == "text":
        return metric_hits_for_text_rule(rule, text), "regex"
    if section == "block":
        return metric_hits_for_block_rule(rule, text)
    return 0, "unsupported"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--rules-metadata", type=Path, default=DEFAULT_RULES)
    parser.add_argument("--field", choices=["clean_text", "raw_text"], default="clean_text")
    parser.add_argument("--max-samples", type=int, default=10)
    parser.add_argument("--show-mode", action="store_true")
    args = parser.parse_args()

    rows = load_rows(args.input)
    rules_metadata = load_rules(args.rules_metadata)

    print(f"pages={len(rows)}")
    print(f"field={args.field}")
    for section, rule in iter_enabled_rules(rules_metadata):
        matches = 0
        sample_pages: List[int] = []
        mode = "unsupported"
        for row in rows:
            page = int(row["page"])
            text = row.get(args.field)
            if not isinstance(text, str):
                continue
            page_matches, page_mode = metric_hits(section, rule, text)
            if page_mode != "unsupported":
                mode = page_mode
            matches += page_matches
            if page_matches > 0:
                sample_pages.extend([page] * page_matches)
        line = f"{rule['name']}: {matches} {format_samples(sample_pages, args.max_samples)}"
        if args.show_mode:
            line += f" mode={mode}"
        print(line)


if __name__ == "__main__":
    main()

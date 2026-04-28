#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import pdfplumber


DOUBLE_ESCAPED_PATTERN = re.compile(r"\\\\[dDsSwWbB]")


@dataclass(frozen=True)
class Word:
    text: str
    top: float
    x0: float
    size: float
    bottom: float


@dataclass(frozen=True)
class Line:
    words: Tuple[Word, ...]
    line_top: float
    line_bottom: float
    line_text: str


@dataclass(frozen=True)
class TextLineAnchor:
    line: Line
    match: re.Match[str]


@dataclass(frozen=True)
class HorizontalLineAnchor:
    top: float


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def require(condition: bool, field_name: str) -> None:
    if not condition:
        fail(f"invalid rules-metadata field: {field_name}")


def ensure_only_keys(value: Mapping[str, Any], allowed: Sequence[str], field_name: str) -> None:
    require(set(value.keys()) == set(allowed), field_name)


def ensure_optional_keys(value: Mapping[str, Any], allowed: Sequence[str], required: Sequence[str], field_name: str) -> None:
    keys = set(value.keys())
    require(keys <= set(allowed), field_name)
    require(set(required) <= keys, field_name)


def load_json_file(path: Path, label: str) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        fail(f"{label} not found: {path}")
    except json.JSONDecodeError as exc:
        fail(f"{label} JSON decode error: {exc}")
    except OSError as exc:
        fail(f"{label} read error: {exc}")


def validate_flags(value: Any, field_name: str) -> str:
    require(isinstance(value, str), field_name)
    require(value in {"", "i"}, field_name)
    return value


def regex_flags(flags_value: str) -> int:
    return re.I if flags_value == "i" else 0


def validate_pattern(value: Any, field_name: str, flags_value: str = "") -> str:
    require(isinstance(value, str), field_name)
    require(DOUBLE_ESCAPED_PATTERN.search(value) is None, field_name)
    try:
        re.compile(value, regex_flags(flags_value))
    except re.error:
        fail(f"invalid rules-metadata field: {field_name}")
    return value


def normalize_line(text: str) -> str:
    return " ".join((text or "").replace("\x00", "").split())


def collapse_ws_lower(text: str) -> str:
    return " ".join((text or "").split()).lower()


def safe_cleanup(text: str) -> str:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    lines = [" ".join(line.split()) for line in normalized.split("\n")]
    return "\n".join(lines)


def final_canonicalize(text: str) -> str:
    return " ".join((text or "").split())


def median_or_zero(values: Sequence[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def validate_line_rule(rule: Any, field_name: str) -> None:
    require(isinstance(rule, dict), field_name)
    rule_type = rule.get("type")
    if rule_type == "line_prefix":
        ensure_only_keys(rule, ["name", "type", "enabled", "scope", "prefixes"], field_name)
        prefixes = rule.get("prefixes")
        require(isinstance(prefixes, list) and all(isinstance(item, str) for item in prefixes), f"{field_name}.prefixes")
    elif rule_type == "line_regex":
        ensure_only_keys(rule, ["name", "type", "enabled", "scope", "pattern", "flags"], field_name)
        validate_flags(rule.get("flags"), f"{field_name}.flags")
        validate_pattern(rule.get("pattern"), f"{field_name}.pattern", rule["flags"])
    elif rule_type == "line_equals":
        ensure_only_keys(rule, ["name", "type", "enabled", "scope", "value", "normalize"], field_name)
        require(isinstance(rule.get("value"), str), f"{field_name}.value")
        require(rule.get("normalize") in {"none", "collapse_ws_lower"}, f"{field_name}.normalize")
    else:
        fail(f"invalid rules-metadata field: {field_name}.type")
    require(isinstance(rule.get("name"), str), f"{field_name}.name")
    require(isinstance(rule.get("enabled"), bool), f"{field_name}.enabled")
    scope = rule.get("scope")
    require(isinstance(scope, dict), f"{field_name}.scope")
    ensure_only_keys(scope, ["band"], f"{field_name}.scope")
    require(scope.get("band") in {"top", "bottom", "any"}, f"{field_name}.scope.band")


def validate_text_rule(rule: Any, field_name: str) -> None:
    require(isinstance(rule, dict), field_name)
    ensure_only_keys(rule, ["name", "type", "enabled", "pattern", "flags", "repl"], field_name)
    require(isinstance(rule.get("name"), str), f"{field_name}.name")
    require(rule.get("type") == "regex_sub", f"{field_name}.type")
    require(isinstance(rule.get("enabled"), bool), f"{field_name}.enabled")
    validate_flags(rule.get("flags"), f"{field_name}.flags")
    validate_pattern(rule.get("pattern"), f"{field_name}.pattern", rule["flags"])
    require(isinstance(rule.get("repl"), str), f"{field_name}.repl")


def validate_anchor(anchor: Any, field_name: str) -> None:
    require(isinstance(anchor, dict), field_name)
    kind = anchor.get("kind")
    if kind == "text_line_regex":
        ensure_only_keys(anchor, ["kind", "where", "select"], field_name)
        where = anchor["where"]
        require(isinstance(where, dict), f"{field_name}.where")
        ensure_only_keys(where, ["pattern", "flags"], f"{field_name}.where")
        validate_flags(where["flags"], f"{field_name}.where.flags")
        validate_pattern(where["pattern"], f"{field_name}.where.pattern", where["flags"])
        require(anchor["select"] in {"first", "all"}, f"{field_name}.select")
        return
    if kind == "horizontal_line":
        ensure_only_keys(anchor, ["kind", "source", "where", "select"], field_name)
        require(anchor["source"] == "page.lines", f"{field_name}.source")
        require(anchor["select"] == "lowest", f"{field_name}.select")
        where = anchor["where"]
        require(isinstance(where, dict), f"{field_name}.where")
        ensure_only_keys(where, ["top_gte_pct", "x0_lte", "width_gte", "width_lte", "linewidth_lte"], f"{field_name}.where")
        for key in ("top_gte_pct", "x0_lte", "width_gte", "width_lte", "linewidth_lte"):
            require(isinstance(where[key], (int, float)), f"{field_name}.where.{key}")
        return
    fail(f"invalid rules-metadata field: {field_name}.kind")


def validate_candidate_region(candidate_region: Any, field_name: str) -> None:
    require(isinstance(candidate_region, dict), field_name)
    kind = candidate_region.get("kind")
    if kind == "lines_from_anchor_following_until":
        ensure_only_keys(candidate_region, ["kind", "max_lines", "stop_when_any"], field_name)
        require(isinstance(candidate_region["max_lines"], int), f"{field_name}.max_lines")
        require(isinstance(candidate_region["stop_when_any"], list), f"{field_name}.stop_when_any")
        for index, item in enumerate(candidate_region["stop_when_any"]):
            prefix = f"{field_name}.stop_when_any[{index}]"
            require(isinstance(item, dict), prefix)
            ensure_only_keys(item, ["kind", "reference", "value"], prefix)
            require(item["kind"] == "next_line_gap_gte_ratio", f"{prefix}.kind")
            require(isinstance(item["reference"], str), f"{prefix}.reference")
            require(isinstance(item["value"], (int, float)), f"{prefix}.value")
        return
    if kind == "region_below_anchor_to_page_bottom":
        ensure_only_keys(candidate_region, ["kind", "offset"], field_name)
        require(isinstance(candidate_region["offset"], (int, float)), f"{field_name}.offset")
        return
    fail(f"invalid rules-metadata field: {field_name}.kind")


def validate_when_expr(node: Any, field_name: str) -> None:
    require(isinstance(node, dict), field_name)
    if set(node.keys()) & {"all", "any", "not"}:
        validate_when(node, field_name)
        return
    kind = node.get("kind")
    if kind == "anchor_capture_int_eq_context":
        ensure_only_keys(node, ["kind", "capture_group", "context"], field_name)
        require(isinstance(node["capture_group"], int), f"{field_name}.capture_group")
        require(node["context"] == "page_to_chapter", f"{field_name}.context")
        return
    if kind == "candidate_line_count_gte":
        ensure_only_keys(node, ["kind", "value"], field_name)
        require(isinstance(node["value"], int), f"{field_name}.value")
        return
    if kind == "word_below_anchor_regex_at_index":
        ensure_only_keys(node, ["kind", "pattern", "word_index"], field_name)
        validate_pattern(node["pattern"], f"{field_name}.pattern")
        require(isinstance(node["word_index"], int), f"{field_name}.word_index")
        return
    if kind == "word_below_anchor_size_lte_at_index":
        ensure_only_keys(node, ["kind", "value", "word_index"], field_name)
        require(isinstance(node["value"], (int, float)), f"{field_name}.value")
        require(isinstance(node["word_index"], int), f"{field_name}.word_index")
        return
    if kind == "all_words_below_anchor_size_ratio_lte":
        ensure_only_keys(node, ["kind", "reference", "value", "ignore_first_word_if_matches"], field_name)
        require(isinstance(node["reference"], str), f"{field_name}.reference")
        require(isinstance(node["value"], (int, float)), f"{field_name}.value")
        validate_pattern(node["ignore_first_word_if_matches"], f"{field_name}.ignore_first_word_if_matches")
        return
    fail(f"invalid rules-metadata field: {field_name}.kind")


def validate_when(node: Any, field_name: str) -> None:
    require(isinstance(node, dict), field_name)
    if "all" in node:
        ensure_only_keys(node, ["all"], field_name)
        require(isinstance(node["all"], list), f"{field_name}.all")
        for index, item in enumerate(node["all"]):
            validate_when_expr(item, f"{field_name}.all[{index}]")
        return
    if "any" in node:
        ensure_only_keys(node, ["any"], field_name)
        require(isinstance(node["any"], list), f"{field_name}.any")
        for index, item in enumerate(node["any"]):
            validate_when_expr(item, f"{field_name}.any[{index}]")
        return
    if "not" in node:
        ensure_only_keys(node, ["not"], field_name)
        validate_when_expr(node["not"], f"{field_name}.not")
        return
    fail(f"invalid rules-metadata field: {field_name}")


def validate_block_rule(rule: Any, field_name: str) -> None:
    require(isinstance(rule, dict), field_name)
    ensure_optional_keys(
        rule,
        ["name", "type", "enabled", "stage", "target", "references", "anchor", "candidate_region", "when", "action"],
        ["name", "type", "enabled", "stage", "target", "anchor", "candidate_region", "action"],
        field_name,
    )
    require(isinstance(rule.get("name"), str), f"{field_name}.name")
    require(rule.get("type") == "region_rule", f"{field_name}.type")
    require(isinstance(rule.get("enabled"), bool), f"{field_name}.enabled")
    require(rule.get("stage") in {"pre_line_rules", "post_line_rules"}, f"{field_name}.stage")
    require(rule.get("target") == "words", f"{field_name}.target")
    references = rule.get("references", [])
    require(isinstance(references, list), f"{field_name}.references")
    seen: set[str] = set()
    for index, reference in enumerate(references):
        prefix = f"{field_name}.references[{index}]"
        require(isinstance(reference, dict), prefix)
        ensure_only_keys(reference, ["name", "kind", "fallback"], prefix)
        require(isinstance(reference["name"], str), f"{prefix}.name")
        require(reference["name"] not in seen, f"{prefix}.name")
        seen.add(reference["name"])
        require(reference["kind"] in {"median_gap", "median_word_font_size_above_anchor"}, f"{prefix}.kind")
        require(isinstance(reference["fallback"], (int, float)), f"{prefix}.fallback")
    validate_anchor(rule["anchor"], f"{field_name}.anchor")
    validate_candidate_region(rule["candidate_region"], f"{field_name}.candidate_region")
    if "when" in rule:
        validate_when(rule["when"], f"{field_name}.when")
    action = rule["action"]
    require(isinstance(action, dict), f"{field_name}.action")
    ensure_only_keys(action, ["type"], f"{field_name}.action")
    require(action.get("type") == "drop_region", f"{field_name}.action.type")


def validate_rules_metadata(payload: Any) -> Dict[str, Any]:
    require(isinstance(payload, dict), "root")
    ensure_optional_keys(payload, ["profile_version", "profile_name", "params", "rules"], ["profile_version", "params", "rules"], "root")
    require(payload["profile_version"] == 1, "profile_version")
    if "profile_name" in payload:
        require(isinstance(payload["profile_name"], str), "profile_name")
    params = payload["params"]
    rules = payload["rules"]
    require(isinstance(params, dict), "params")
    require(isinstance(rules, dict), "rules")
    ensure_only_keys(params, ["y_tol", "top_band_pct", "bottom_band_pct", "superscript", "captions", "footnotes", "layout"], "params")
    ensure_optional_keys(rules, ["context", "line", "block", "text"], [], "rules")
    for key in ("y_tol", "top_band_pct", "bottom_band_pct"):
        require(isinstance(params[key], (int, float)), f"params.{key}")

    superscript = params["superscript"]
    require(isinstance(superscript, dict), "params.superscript")
    ensure_only_keys(superscript, ["enabled", "max_digits", "size_ratio"], "params.superscript")
    require(isinstance(superscript["enabled"], bool), "params.superscript.enabled")
    require(isinstance(superscript["max_digits"], int), "params.superscript.max_digits")
    require(isinstance(superscript["size_ratio"], (int, float)), "params.superscript.size_ratio")

    captions = params["captions"]
    require(isinstance(captions, dict), "params.captions")
    ensure_only_keys(captions, ["enabled", "start_pattern", "flags", "chapter_aware", "max_cont_lines", "max_line_len", "empty_lines_required"], "params.captions")
    require(isinstance(captions["enabled"], bool), "params.captions.enabled")
    validate_flags(captions["flags"], "params.captions.flags")
    validate_pattern(captions["start_pattern"], "params.captions.start_pattern", captions["flags"])
    require(isinstance(captions["chapter_aware"], bool), "params.captions.chapter_aware")
    require(isinstance(captions["max_cont_lines"], int), "params.captions.max_cont_lines")
    require(isinstance(captions["max_line_len"], int), "params.captions.max_line_len")
    require(isinstance(captions["empty_lines_required"], int), "params.captions.empty_lines_required")

    footnotes = params["footnotes"]
    require(isinstance(footnotes, dict), "params.footnotes")
    ensure_only_keys(footnotes, ["enabled", "start_y_pct", "size_ratio", "marker_patterns"], "params.footnotes")
    require(isinstance(footnotes["enabled"], bool), "params.footnotes.enabled")
    require(isinstance(footnotes["start_y_pct"], (int, float)), "params.footnotes.start_y_pct")
    require(isinstance(footnotes["size_ratio"], (int, float)), "params.footnotes.size_ratio")
    require(isinstance(footnotes["marker_patterns"], list), "params.footnotes.marker_patterns")
    for index, pattern in enumerate(footnotes["marker_patterns"]):
        validate_pattern(pattern, f"params.footnotes.marker_patterns[{index}]")

    layout = params["layout"]
    require(isinstance(layout, dict), "params.layout")
    mode = layout.get("mode")
    require(mode in {"single_column", "two_column"}, "params.layout.mode")
    if mode == "two_column":
        ensure_only_keys(layout, ["mode", "column_split_x"], "params.layout")
        require(isinstance(layout.get("column_split_x"), (int, float)), "params.layout.column_split_x")
    else:
        ensure_only_keys(layout, ["mode"], "params.layout")

    context = rules.get("context", {})
    require(isinstance(context, dict), "rules.context")
    ensure_optional_keys(context, ["page_to_chapter"], [], "rules.context")
    if "page_to_chapter" in context:
        page_to_chapter = context["page_to_chapter"]
        require(isinstance(page_to_chapter, dict), "rules.context.page_to_chapter")
        require(all(isinstance(key, str) and isinstance(value, int) for key, value in page_to_chapter.items()), "rules.context.page_to_chapter")

    line_rules = rules.get("line", [])
    block_rules = rules.get("block", [])
    text_rules = rules.get("text", [])
    require(isinstance(line_rules, list), "rules.line")
    require(isinstance(block_rules, list), "rules.block")
    require(isinstance(text_rules, list), "rules.text")
    for index, rule in enumerate(line_rules):
        validate_line_rule(rule, f"rules.line[{index}]")
    for index, rule in enumerate(block_rules):
        validate_block_rule(rule, f"rules.block[{index}]")
    for index, rule in enumerate(text_rules):
        validate_text_rule(rule, f"rules.text[{index}]")
    return payload


def validate_terms_metadata(payload: Any) -> Dict[str, Any]:
    require(isinstance(payload, dict), "terms-metadata.root")
    ensure_only_keys(payload, ["dictionary_name", "version", "description", "entry_description", "entries"], "terms-metadata.root")
    require(isinstance(payload["entries"], list), "terms-metadata.entries")
    seen_words: set[str] = set()
    seen_variants: set[str] = set()
    for index, entry in enumerate(payload["entries"]):
        prefix = f"terms-metadata.entries[{index}]"
        require(isinstance(entry, dict), prefix)
        ensure_only_keys(entry, ["word", "split_variants"], prefix)
        require(isinstance(entry["word"], str), f"{prefix}.word")
        require(entry["word"] not in seen_words, f"{prefix}.word")
        seen_words.add(entry["word"])
        split_variants = entry["split_variants"]
        require(isinstance(split_variants, list) and split_variants, f"{prefix}.split_variants")
        for variant_index, variant in enumerate(split_variants):
            require(isinstance(variant, str), f"{prefix}.split_variants[{variant_index}]")
            require(variant not in seen_variants, f"{prefix}.split_variants[{variant_index}]")
            seen_variants.add(variant)
    return payload


def load_clean_text_overrides(path: Optional[Path]) -> Dict[int, str]:
    if path is None:
        return {}
    payload = load_json_file(path, "clean-text-metadata")
    require(isinstance(payload, dict), "clean-text-metadata.root")
    ensure_optional_keys(payload, ["source_file", "description", "pages"], ["pages"], "clean-text-metadata.root")
    require(isinstance(payload["pages"], list), "clean-text-metadata.pages")
    result: Dict[int, str] = {}
    for index, item in enumerate(payload["pages"]):
        prefix = f"clean-text-metadata.pages[{index}]"
        require(isinstance(item, dict), prefix)
        ensure_only_keys(item, ["page", "clean_text"], prefix)
        require(isinstance(item["page"], int), f"{prefix}.page")
        require(isinstance(item["clean_text"], str), f"{prefix}.clean_text")
        result[item["page"]] = item["clean_text"]
    return result


def make_words(raw_words: Iterable[Mapping[str, Any]]) -> List[Word]:
    result: List[Word] = []
    for item in raw_words:
        text = item.get("text")
        top = item.get("top")
        x0 = item.get("x0")
        size = item.get("size")
        bottom = item.get("bottom")
        require(isinstance(text, str), "word.text")
        require(isinstance(top, (int, float)), "word.top")
        require(isinstance(x0, (int, float)), "word.x0")
        require(isinstance(size, (int, float)), "word.size")
        if not isinstance(bottom, (int, float)):
            bottom = float(top) + float(size)
        result.append(Word(text=text, top=float(top), x0=float(x0), size=float(size), bottom=float(bottom)))
    return result


def filter_superscripts(words: Sequence[Word], rules_metadata: Mapping[str, Any]) -> List[Word]:
    superscript = rules_metadata["params"]["superscript"]
    if not superscript["enabled"]:
        return list(words)
    median_size = median_or_zero([word.size for word in words if word.text.strip()])
    if median_size <= 0:
        return list(words)
    digit_re = re.compile(r"^\d{1," + str(superscript["max_digits"]) + r"}$")
    result: List[Word] = []
    for word in words:
        if digit_re.search(word.text) and word.size <= median_size * float(superscript["size_ratio"]):
            continue
        result.append(word)
    return result


def group_words_into_lines(words: Sequence[Word], y_tol: float) -> List[Line]:
    ordered = sorted(words, key=lambda item: (item.top, item.x0, item.text))
    groups: List[List[Word]] = []
    for word in ordered:
        if not groups:
            groups.append([word])
            continue
        current = groups[-1]
        current_top = min(item.top for item in current)
        if abs(word.top - current_top) <= y_tol:
            current.append(word)
        else:
            groups.append([word])
    lines: List[Line] = []
    for group in groups:
        sorted_group = tuple(sorted(group, key=lambda item: (item.x0, item.top, item.text)))
        lines.append(
            Line(
                words=sorted_group,
                line_top=min(item.top for item in sorted_group),
                line_bottom=max(item.bottom for item in sorted_group),
                line_text=" ".join(item.text for item in sorted_group),
            )
        )
    return lines


def compute_gap(curr: Line, next_line: Line) -> float:
    value = next_line.line_top - curr.line_bottom
    return value if value > 0 else 0.0


def compute_reference_values(
    references: Sequence[Mapping[str, Any]],
    lines: Sequence[Line],
    words: Sequence[Word],
    anchor: Optional[object],
) -> Dict[str, float]:
    values: Dict[str, float] = {}
    for reference in references:
        name = reference["name"]
        fallback = float(reference["fallback"])
        if reference["kind"] == "median_gap":
            gaps = [compute_gap(lines[index], lines[index + 1]) for index in range(len(lines) - 1)]
            positive = [gap for gap in gaps if gap > 0]
            values[name] = median_or_zero(positive) if positive else fallback
        else:
            anchor_top = float("inf")
            if isinstance(anchor, HorizontalLineAnchor):
                anchor_top = anchor.top
            sizes = [word.size for word in words if word.top < anchor_top]
            values[name] = median_or_zero(sizes) if sizes else fallback
    return values


def select_text_line_anchors(lines: Sequence[Line], anchor_spec: Mapping[str, Any]) -> List[TextLineAnchor]:
    pattern = re.compile(anchor_spec["where"]["pattern"], regex_flags(anchor_spec["where"]["flags"]))
    matches: List[TextLineAnchor] = []
    for line in lines:
        match = pattern.search(line.line_text)
        if match is not None:
            matches.append(TextLineAnchor(line=line, match=match))
    return matches[:1] if anchor_spec["select"] == "first" else matches


def select_horizontal_line_anchors(page_lines: Sequence[Mapping[str, Any]], page_height: float, anchor_spec: Mapping[str, Any]) -> List[HorizontalLineAnchor]:
    where = anchor_spec["where"]
    candidates: List[HorizontalLineAnchor] = []
    for item in page_lines:
        top = item.get("top")
        x0 = item.get("x0")
        x1 = item.get("x1")
        linewidth = item.get("linewidth")
        if not all(isinstance(value, (int, float)) for value in (top, x0, x1, linewidth)):
            continue
        width = float(x1) - float(x0)
        if float(top) < float(where["top_gte_pct"]) * page_height:
            continue
        if float(x0) > float(where["x0_lte"]):
            continue
        if width < float(where["width_gte"]) or width > float(where["width_lte"]):
            continue
        if float(linewidth) > float(where["linewidth_lte"]):
            continue
        candidates.append(HorizontalLineAnchor(top=float(top)))
    if not candidates:
        return []
    return [max(candidates, key=lambda item: item.top)]


def evaluate_when(
    node: Mapping[str, Any],
    page_num: int,
    anchor: object,
    candidate_lines: Sequence[Line],
    candidate_words: Sequence[Word],
    references: Mapping[str, float],
    context: Mapping[str, Any],
) -> bool:
    if "all" in node:
        return all(evaluate_when_expr(item, page_num, anchor, candidate_lines, candidate_words, references, context) for item in node["all"])
    if "any" in node:
        return any(evaluate_when_expr(item, page_num, anchor, candidate_lines, candidate_words, references, context) for item in node["any"])
    return not evaluate_when_expr(node["not"], page_num, anchor, candidate_lines, candidate_words, references, context)


def evaluate_when_expr(
    node: Mapping[str, Any],
    page_num: int,
    anchor: object,
    candidate_lines: Sequence[Line],
    candidate_words: Sequence[Word],
    references: Mapping[str, float],
    context: Mapping[str, Any],
) -> bool:
    if set(node.keys()) & {"all", "any", "not"}:
        return evaluate_when(node, page_num, anchor, candidate_lines, candidate_words, references, context)
    kind = node["kind"]
    if kind == "anchor_capture_int_eq_context":
        if not isinstance(anchor, TextLineAnchor):
            return False
        try:
            captured = int(anchor.match.group(int(node["capture_group"])))
        except (IndexError, ValueError):
            return False
        page_to_chapter = context.get("page_to_chapter", {})
        expected = page_to_chapter.get(str(page_num))
        return isinstance(expected, int) and captured == expected
    if kind == "candidate_line_count_gte":
        return len(candidate_lines) >= int(node["value"])
    if kind == "word_below_anchor_regex_at_index":
        index = int(node["word_index"])
        if index < 0 or index >= len(candidate_words):
            return False
        return re.compile(node["pattern"]).search(candidate_words[index].text) is not None
    if kind == "word_below_anchor_size_lte_at_index":
        index = int(node["word_index"])
        if index < 0 or index >= len(candidate_words):
            return False
        return candidate_words[index].size <= float(node["value"])
    baseline = float(references.get(node["reference"], 0.0))
    if baseline <= 0:
        return False
    ignore_first = re.compile(node["ignore_first_word_if_matches"])
    for index, word in enumerate(candidate_words):
        if index == 0 and ignore_first.search(word.text):
            continue
        if word.size > baseline * float(node["value"]):
            return False
    return True


def build_candidate_lines(
    lines: Sequence[Line],
    anchor_line: Line,
    candidate_region: Mapping[str, Any],
    references: Mapping[str, float],
) -> List[Line]:
    start = next(index for index, line in enumerate(lines) if line == anchor_line)
    selected = [anchor_line]
    while len(selected) < int(candidate_region["max_lines"]) and start + len(selected) < len(lines):
        current = selected[-1]
        next_line = lines[start + len(selected)]
        should_stop = False
        for stop_rule in candidate_region["stop_when_any"]:
            baseline = float(references.get(stop_rule["reference"], 0.0))
            if baseline > 0 and compute_gap(current, next_line) >= baseline * float(stop_rule["value"]):
                should_stop = True
                break
        if should_stop:
            break
        selected.append(next_line)
    return selected


def words_below_anchor(words: Sequence[Word], anchor: HorizontalLineAnchor, offset: float) -> List[Word]:
    return [word for word in sorted(words, key=lambda item: (item.top, item.x0, item.text)) if word.top >= anchor.top + offset]


def apply_block_rules_stage(
    words: Sequence[Word],
    page_lines: Sequence[Mapping[str, Any]],
    page_height: float,
    page_num: int,
    rules_metadata: Mapping[str, Any],
    stage: str,
) -> List[Word]:
    current_words = list(words)
    y_tol = float(rules_metadata["params"]["y_tol"])
    context = rules_metadata["rules"].get("context", {})
    for rule in rules_metadata["rules"].get("block", []):
        if not rule["enabled"] or rule["stage"] != stage:
            continue
        if rule["anchor"]["kind"] == "text_line_regex":
            while True:
                lines = group_words_into_lines(current_words, y_tol)
                anchors = select_text_line_anchors(lines, rule["anchor"])
                if not anchors:
                    break
                deleted_any = False
                for anchor in anchors:
                    lines = group_words_into_lines(current_words, y_tol)
                    if anchor.line not in lines:
                        continue
                    current_anchor = next(item for item in select_text_line_anchors(lines, rule["anchor"]) if item.line == anchor.line)
                    references = compute_reference_values(rule.get("references", []), lines, current_words, current_anchor)
                    candidate_lines = build_candidate_lines(lines, current_anchor.line, rule["candidate_region"], references)
                    candidate_words: List[Word] = []
                    should_apply = True
                    if "when" in rule:
                        should_apply = evaluate_when(rule["when"], page_num, current_anchor, candidate_lines, candidate_words, references, context)
                    if should_apply:
                        remove_words = {word for line in candidate_lines for word in line.words}
                        current_words = [word for word in current_words if word not in remove_words]
                        deleted_any = True
                        break
                if not deleted_any:
                    break
        else:
            anchors = select_horizontal_line_anchors(page_lines, page_height, rule["anchor"])
            if not anchors:
                continue
            anchor = anchors[0]
            lines = group_words_into_lines(current_words, y_tol)
            references = compute_reference_values(rule.get("references", []), lines, current_words, anchor)
            candidate_words = words_below_anchor(current_words, anchor, float(rule["candidate_region"]["offset"]))
            candidate_lines: List[Line] = []
            should_apply = True
            if "when" in rule:
                should_apply = evaluate_when(rule["when"], page_num, anchor, candidate_lines, candidate_words, references, context)
            if should_apply:
                remove_words = set(candidate_words)
                current_words = [word for word in current_words if word not in remove_words]
    return current_words


def line_in_band(line: Line, band: str, params: Mapping[str, Any], page_height: float) -> bool:
    if band == "top":
        return line.line_top < float(params["top_band_pct"]) * page_height
    if band == "bottom":
        return line.line_top > float(params["bottom_band_pct"]) * page_height
    return True


def should_remove_line(line: Line, rule: Mapping[str, Any], params: Mapping[str, Any], page_height: float) -> bool:
    if not line_in_band(line, rule["scope"]["band"], params, page_height):
        return False
    if rule["type"] == "line_prefix":
        stripped = line.line_text.lstrip()
        return any(stripped.startswith(prefix) for prefix in rule["prefixes"])
    if rule["type"] == "line_regex":
        return re.compile(rule["pattern"], regex_flags(rule["flags"])).search(line.line_text) is not None
    if rule["normalize"] == "collapse_ws_lower":
        return collapse_ws_lower(line.line_text) == collapse_ws_lower(rule["value"])
    return line.line_text == rule["value"]


def apply_line_rules(words: Sequence[Word], page_height: float, rules_metadata: Mapping[str, Any]) -> List[Word]:
    lines = group_words_into_lines(words, float(rules_metadata["params"]["y_tol"]))
    result: List[Word] = []
    for line in lines:
        remove = False
        for rule in rules_metadata["rules"].get("line", []):
            if rule["enabled"] and should_remove_line(line, rule, rules_metadata["params"], page_height):
                remove = True
                break
        if not remove:
            result.extend(line.words)
    return result


def apply_text_rules(text: str, rules_metadata: Mapping[str, Any]) -> str:
    current = text
    for rule in rules_metadata["rules"].get("text", []):
        if not rule["enabled"]:
            continue
        current = re.compile(rule["pattern"], regex_flags(rule["flags"])).sub(rule["repl"], current)
    return current


def apply_terms_metadata(text: str, terms_metadata: Optional[Mapping[str, Any]]) -> str:
    if terms_metadata is None:
        return text
    current = text
    for entry in terms_metadata["entries"]:
        for variant in entry["split_variants"]:
            current = current.replace(variant, entry["word"])
    return current


def apply_cleanup_pipeline(
    words: Sequence[Mapping[str, Any]],
    page_height: float,
    page_num: int,
    rules_metadata: Mapping[str, Any],
    page_lines: Sequence[Mapping[str, Any]],
) -> str:
    """Steps 2–9: superscript filter, block rules, line rules, assemble text, text rules, safe cleanup."""
    current_words = filter_superscripts(make_words(words), rules_metadata)
    current_words = apply_block_rules_stage(current_words, page_lines, page_height, page_num, rules_metadata, "pre_line_rules")
    current_words = apply_line_rules(current_words, page_height, rules_metadata)
    current_words = apply_block_rules_stage(current_words, page_lines, page_height, page_num, rules_metadata, "post_line_rules")
    lines = group_words_into_lines(current_words, float(rules_metadata["params"]["y_tol"]))
    text = "\n".join(line.line_text for line in lines)
    text = apply_text_rules(text, rules_metadata)
    return safe_cleanup(text)


def clean_page_text(
    words: Sequence[Mapping[str, Any]],
    page_height: float,
    page_num: int,
    rules_metadata: Mapping[str, Any],
    page_lines: Sequence[Mapping[str, Any]],
    terms_metadata: Optional[Mapping[str, Any]] = None,
) -> str:
    layout = rules_metadata["params"]["layout"]
    if layout["mode"] == "two_column":
        split_x = float(layout["column_split_x"])
        left_words = [w for w in words if float(w.get("x0", 0)) < split_x]
        right_words = [w for w in words if float(w.get("x0", 0)) >= split_x]
        left_text = apply_cleanup_pipeline(left_words, page_height, page_num, rules_metadata, page_lines)
        right_text = apply_cleanup_pipeline(right_words, page_height, page_num, rules_metadata, page_lines)
        text = "\n".join(t for t in [left_text, right_text] if t)
    else:
        text = apply_cleanup_pipeline(words, page_height, page_num, rules_metadata, page_lines)
    text = apply_terms_metadata(text, terms_metadata)
    return final_canonicalize(text)


def read_page_words(page: Any) -> List[Dict[str, Any]]:
    return page.extract_words(x_tolerance=1, y_tolerance=1, extra_attrs=["size"])


def read_raw_text(page: Any) -> str:
    extracted = page.extract_text(x_tolerance=1, y_tolerance=1)
    return extracted if extracted is not None else ""


def build_rows(
    pdf_path: Path,
    rules_metadata_path: Path,
    clean_text_metadata_path: Optional[Path],
    terms_metadata_path: Optional[Path],
) -> List[Dict[str, Any]]:
    rules_metadata = validate_rules_metadata(load_json_file(rules_metadata_path, "rules-metadata"))
    clean_text_overrides = load_clean_text_overrides(clean_text_metadata_path)
    terms_metadata = None
    if terms_metadata_path is not None:
        terms_metadata = validate_terms_metadata(load_json_file(terms_metadata_path, "terms-metadata"))
    rows: List[Dict[str, Any]] = []
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                raw_text = read_raw_text(page)
                if page_num in clean_text_overrides:
                    clean_text = final_canonicalize(clean_text_overrides[page_num])
                else:
                    page_words = read_page_words(page)
                    clean_text = clean_page_text(page_words, float(page.height), page_num, rules_metadata, page.lines, terms_metadata)
                rows.append({"page": page_num, "raw_text": raw_text, "clean_text": clean_text})
    except Exception as exc:
        fail(f"pdf open/extract error: {exc}")
    return rows


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    try:
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as exc:
        fail(f"output write error: {exc}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--rules-metadata", type=Path, required=True)
    parser.add_argument("--clean-text-metadata", type=Path)
    parser.add_argument("--terms-metadata", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = build_rows(args.pdf, args.rules_metadata, args.clean_text_metadata, args.terms_metadata)
    write_jsonl(args.out, rows)


if __name__ == "__main__":
    main()

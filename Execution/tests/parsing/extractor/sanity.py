#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


DEFAULT_INPUT = Path("out/pages.jsonl")
DEFAULT_METADATA = Path("data/content/book_content_metadata.json")


def fail(message: str) -> None:
    print(message)
    raise SystemExit(1)


def load_rows(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    if not rows:
        fail("FAIL: no rows")
    return rows


def load_expected_pages_count(path: Optional[Path]) -> Optional[int]:
    if path is None:
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    value = payload.get("expected_pages_count")
    return value if isinstance(value, int) else None


def format_percent(value: float) -> str:
    return f"{value * 100:.1f}"


def pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def format_samples(values: Sequence[Any], max_samples: int) -> str:
    shown = ",".join(str(value) for value in values[:max_samples])
    suffix = ",..." if len(values) > max_samples else ""
    return f"samples=[{shown}{suffix}]"


def normalize_for_hash(text: str) -> str:
    return " ".join((text or "").split())


def is_toc_like(raw_text: str, clean_text: str) -> bool:
    text = clean_text or raw_text
    lines = [line for line in (text or "").splitlines() if line.strip()]
    if not lines:
        return False
    dot_leader = 0
    numbered_tail = 0
    toc_hits = 0
    dot_entry_hits = 0
    toc_word_re = re.compile(r"\b(contents|chapter|part)\b", re.I)
    dot_entry_re = re.compile(r"\.{2,}\s*(?:\d{1,3}|[ivxlcdm]+)\b", re.I)
    for line in lines:
        if re.search(r"\.{2,}", line):
            dot_leader += 1
        if re.search(r"\b\d{1,3}\s*$", line):
            numbered_tail += 1
        toc_hits += len(toc_word_re.findall(line))
        if dot_entry_re.search(line):
            dot_entry_hits += 1
    return (
        (dot_leader >= 2 and numbered_tail >= 2)
        or (numbered_tail >= 4 and len(lines) >= 6)
        or (toc_hits >= 2 and numbered_tail >= 2)
        or (toc_hits >= 1 and dot_entry_hits >= 5)
    )


def is_figure_table_heavy(raw_text: str, clean_text: str) -> bool:
    pattern = re.compile(r"(figure|fig\.|table|diagram|chart|illustration|listing)\s*(\d+(?:[.\-]\d+)*)\s*:", re.I)
    unique_hits = {(match.group(1).lower(), match.group(2)) for match in pattern.finditer(raw_text or "")}
    raw_len = len((raw_text or "").strip())
    clean_len = len((clean_text or "").strip())
    removed_most_text = raw_len >= 120 and clean_len <= 40 and clean_len <= raw_len * 0.2
    return len(unique_hits) >= 1 and removed_most_text


def is_separator_like(raw_text: str) -> bool:
    return (raw_text or "").strip() == ""


def add_label(labels: List[str], label: str) -> None:
    if label not in labels:
        labels.append(label)


def threshold_status(value: float, threshold: Optional[float], fail_label: str, ok_label: str) -> str:
    if threshold is None:
        return ok_label
    return ok_label if value < threshold else fail_label


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--expected-pages-count", type=int)
    parser.add_argument("--tiny-threshold", type=int, default=120)
    parser.add_argument("--text-neighbor-threshold", type=int, default=300)
    parser.add_argument("--empty-core-warn", "--empty-warn", dest="empty_core_warn", type=float, default=0.05)
    parser.add_argument("--tiny-core-warn", "--tiny-warn", dest="tiny_core_warn", type=float, default=0.08)
    parser.add_argument("--empty-total-warn", type=float, default=0.05)
    parser.add_argument("--tiny-total-warn", type=float)
    parser.add_argument("--unexpected-empty-core-warn", type=float, default=0.05)
    parser.add_argument("--unexpected-empty-core-fail", type=float, default=0.10)
    parser.add_argument("--len-factor", type=float, default=1.10)
    parser.add_argument("--len-core-warn", "--len-warn", dest="len_core_warn", type=float, default=0.10)
    parser.add_argument("--len-core-fail", "--len-fail", dest="len_core_fail", type=float, default=0.50)
    parser.add_argument("--len-total-warn", type=float)
    parser.add_argument("--len-total-fail", type=float)
    parser.add_argument("--len-whitespace-only-factor", type=float, default=1.50)
    parser.add_argument("--dup-warn", type=float, default=0.01)
    parser.add_argument("--dup-fail", type=float, default=0.03)
    parser.add_argument("--max-samples", type=int, default=10)
    args = parser.parse_args()

    rows = load_rows(args.input)
    pages = [row.get("page") for row in rows]
    expected_pages = list(range(1, len(rows) + 1))
    if pages != expected_pages:
        fail("FAIL: pages must be sequential 1..N")

    expected = args.expected_pages_count
    if expected is None:
        expected = load_expected_pages_count(args.metadata)
    if expected is not None and len(rows) != expected:
        fail(f"FAIL: expected pages count mismatch: expected={expected} actual={len(rows)}")

    for row in rows:
        if not isinstance(row.get("raw_text"), str):
            fail(f"FAIL: page {row.get('page')} has invalid raw_text")
        if not isinstance(row.get("clean_text"), str):
            fail(f"FAIL: page {row.get('page')} has invalid clean_text")

    labels_by_page: Dict[int, List[str]] = {}
    clean_len: Dict[int, int] = {}
    raw_len: Dict[int, int] = {}
    for row in rows:
        page = row["page"]
        raw_text = row["raw_text"]
        clean_text = row["clean_text"]
        clean_len[page] = len(clean_text.strip())
        raw_len[page] = len(raw_text.strip())
        labels: List[str] = []
        if is_toc_like(raw_text, clean_text):
            add_label(labels, "toc-like")
        if is_figure_table_heavy(raw_text, clean_text):
            add_label(labels, "figure/table-heavy")
        if is_separator_like(raw_text):
            add_label(labels, "separator-like")
        labels_by_page[page] = labels

    pages_with_labels = [page for page, labels in labels_by_page.items() if labels]
    figure_pages = [page for page, labels in labels_by_page.items() if "figure/table-heavy" in labels]
    toc_pages = [page for page, labels in labels_by_page.items() if "toc-like" in labels]
    separator_pages = [page for page, labels in labels_by_page.items() if "separator-like" in labels]
    figure_table_heavy_empty = sum(1 for page in figure_pages if clean_len[page] == 0)
    figure_table_heavy_tiny = sum(1 for page in figure_pages if 0 < clean_len[page] <= args.tiny_threshold)

    pages_all_empty_samples = [
        page
        for page in expected_pages
        if clean_len[page] == 0 and "separator-like" not in labels_by_page[page] and "figure/table-heavy" not in labels_by_page[page]
    ]
    tiny_total_samples = [page for page in expected_pages if 0 < clean_len[page] <= args.tiny_threshold]
    unexpected_empty_pages_samples = [
        page
        for page in expected_pages
        if clean_len[page] == 0
        and "separator-like" not in labels_by_page[page]
        and "figure/table-heavy" not in labels_by_page[page]
        and page != 1
        and page != len(rows)
        and clean_len[page - 1] >= args.text_neighbor_threshold
        and clean_len[page + 1] >= args.text_neighbor_threshold
    ]

    core_pages_list = [page for page in expected_pages if not labels_by_page[page]]
    empty_core_pages_samples = [page for page in core_pages_list if clean_len[page] == 0]
    tiny_core_pages_samples = [page for page in core_pages_list if 0 < clean_len[page] <= args.tiny_threshold]
    unexpected_empty_core_samples = [
        page
        for page in core_pages_list
        if clean_len[page] == 0
        and page != 1
        and page != len(rows)
        and clean_len[page - 1] >= args.text_neighbor_threshold
        and clean_len[page + 1] >= args.text_neighbor_threshold
        and not labels_by_page[page - 1]
        and not labels_by_page[page + 1]
    ]

    length_violations_total_samples: List[int] = []
    length_violations_core_samples: List[int] = []
    length_violations_whitespace_only_total_samples: List[int] = []
    length_violations_whitespace_only_core_samples: List[int] = []
    for row in rows:
        page = row["page"]
        raw_text = row["raw_text"].strip()
        clean_text = row["clean_text"].strip()
        if len(raw_text) < 200:
            continue
        raw_no_ws = re.sub(r"\s+", "", raw_text)
        clean_no_ws = re.sub(r"\s+", "", clean_text)
        is_violation = len(clean_no_ws) > len(raw_no_ws) * args.len_factor
        is_violation_with_ws = len(clean_text) > len(raw_text) * args.len_whitespace_only_factor
        is_ws_only = is_violation_with_ws and not is_violation
        if is_violation:
            length_violations_total_samples.append(page)
            if not labels_by_page[page]:
                length_violations_core_samples.append(page)
        if is_ws_only:
            length_violations_whitespace_only_total_samples.append(page)
            if not labels_by_page[page]:
                length_violations_whitespace_only_core_samples.append(page)

    eligible_pages = [page for page in expected_pages if len(rows[page - 1]["clean_text"]) > args.tiny_threshold]
    duplicate_groups: Dict[str, List[int]] = {}
    for page in eligible_pages:
        normalized = normalize_for_hash(rows[page - 1]["clean_text"])
        digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()
        duplicate_groups.setdefault(digest, []).append(page)
    duplicate_groups_count = sum(1 for group in duplicate_groups.values() if len(group) > 1)
    duplicate_hash_extra_pages = sum(len(group) - 1 for group in duplicate_groups.values() if len(group) > 1)

    pages_count = len(rows)
    core_pages = len(core_pages_list)
    pages_all_empty_pages = len(pages_all_empty_samples)
    tiny_total_pages = len(tiny_total_samples)
    unexpected_empty_pages = len(unexpected_empty_pages_samples)
    empty_core_pages = len(empty_core_pages_samples)
    tiny_core_pages = len(tiny_core_pages_samples)
    unexpected_empty_core_pages = len(unexpected_empty_core_samples)
    length_violations_total_metric = len(length_violations_total_samples)
    length_violations_core_metric = len(length_violations_core_samples)
    length_violations_whitespace_only_total_metric = len(length_violations_whitespace_only_total_samples)
    length_violations_whitespace_only_core_metric = len(length_violations_whitespace_only_core_samples)
    eligible_pages_count = len(eligible_pages)

    pages_all_empty_pcnt = pct(pages_all_empty_pages, pages_count)
    tiny_total_pcnt = pct(tiny_total_pages, pages_count)
    unexpected_empty_pages_pcnt = pct(unexpected_empty_pages, pages_count)
    core_pages_pcnt = pct(core_pages, pages_count)
    empty_core_pages_pcnt = pct(empty_core_pages, core_pages)
    tiny_core_pages_pcnt = pct(tiny_core_pages, core_pages)
    unexpected_empty_core_pages_pcnt = pct(unexpected_empty_core_pages, core_pages)
    duplicate_hash_extra_pcnt = pct(duplicate_hash_extra_pages, eligible_pages_count)
    duplicate_hash_extra_total_pct_of_all_pages = pct(duplicate_hash_extra_pages, pages_count)

    len_core_warn_val = pct(length_violations_core_metric, core_pages)
    len_total_warn_val = pct(length_violations_total_metric, pages_count)
    len_ws_only_total_warn_val = pct(length_violations_whitespace_only_total_metric, pages_count)

    print(f"pages={pages_count} expected={expected if expected is not None else '?'}")
    print("--- pages_with_labels ---")
    print(f"all={len(pages_with_labels)}")
    print(
        f"figure/table-heavy: pages={len(figure_pages)} empty={figure_table_heavy_empty} tiny={figure_table_heavy_tiny} "
        f"{format_samples(figure_pages, args.max_samples)}"
    )
    print(f"toc-like: pages={len(toc_pages)} {format_samples(toc_pages, args.max_samples)}")
    print(f"separator-like: pages={len(separator_pages)} {format_samples(separator_pages, args.max_samples)}")
    print("--- pages (all) ---")
    print(
        f"empty={pages_all_empty_pages} ({format_percent(pages_all_empty_pcnt)}%) "
        f"[excluding separator-like + figure/table-heavy] {format_samples(pages_all_empty_samples, args.max_samples)}"
    )
    print(
        f"tiny_total(0<len<={args.tiny_threshold})={tiny_total_pages} ({format_percent(tiny_total_pcnt)}%) "
        f"{format_samples(tiny_total_samples, args.max_samples)}"
    )
    print(
        f"unexpected_empty(neighbors>={args.text_neighbor_threshold})={unexpected_empty_pages} "
        f"({format_percent(unexpected_empty_pages_pcnt)}%) {format_samples(unexpected_empty_pages_samples, args.max_samples)}"
    )
    print("--- core (pages without labels) ---")
    print(f"core_pages = {core_pages} ({format_percent(core_pages_pcnt)}% of total pages)")
    print(
        f"empty_core = {empty_core_pages} ({format_percent(empty_core_pages_pcnt)}% of core pages) "
        f"{format_samples(empty_core_pages_samples, args.max_samples)}"
    )
    print(
        f"tiny_core(0<len<={args.tiny_threshold}) = {tiny_core_pages} ({format_percent(tiny_core_pages_pcnt)}% of core pages) "
        f"{format_samples(tiny_core_pages_samples, args.max_samples)}"
    )
    print(
        f"unexpected_empty_core(neighbors>={args.text_neighbor_threshold}) = {unexpected_empty_core_pages} "
        f"({format_percent(unexpected_empty_core_pages_pcnt)}%) {format_samples(unexpected_empty_core_samples, args.max_samples)}"
    )
    print("--- length_violations (clean_text expansion over raw_text on text-heavy pages) ---")
    print("text-heavy pages: raw text >= 200")
    print(f"length_violations_total={length_violations_total_metric} (factor=1.1) {format_samples(length_violations_total_samples, args.max_samples)}")
    print(f"length_violations_core={length_violations_core_metric} {format_samples(length_violations_core_samples, args.max_samples)}")
    print(
        f"length_violations_whitespace_only_total={length_violations_whitespace_only_total_metric} (factor=1.5) "
        f"{format_samples(length_violations_whitespace_only_total_samples, args.max_samples)}"
    )
    print(
        f"length_violations_whitespace_only_core={length_violations_whitespace_only_core_metric} "
        f"{format_samples(length_violations_whitespace_only_core_samples, args.max_samples)}"
    )
    print("--- duplicate ---")
    print(f"eligible pages: clean text > {args.tiny_threshold}")
    print(
        f"duplicate_hash_extra={duplicate_hash_extra_pages} ({format_percent(duplicate_hash_extra_pcnt)}% of eligible) "
        f"eligible_pages={eligible_pages_count} duplicate_groups={duplicate_groups_count}"
    )
    print(f"duplicate_hash_extra_total_pct_of_all_pages={format_percent(duplicate_hash_extra_total_pct_of_all_pages)}%")
    print("--- WARNINGS ---")
    warning_rows = [
        ("empty_total_warn", pages_all_empty_pcnt, args.empty_total_warn),
        ("tiny_total_warn", tiny_total_pcnt, args.tiny_total_warn),
        ("empty_core_warn", empty_core_pages_pcnt, args.empty_core_warn),
        ("tiny_core_warn", tiny_core_pages_pcnt, args.tiny_core_warn),
        ("unexpected_empty_core_warn", unexpected_empty_core_pages_pcnt, args.unexpected_empty_core_warn),
        ("len_core_warn", len_core_warn_val, args.len_core_warn),
        ("len_total_warn", len_total_warn_val, args.len_total_warn),
        ("len_ws_only_total_warn", len_ws_only_total_warn_val, 0.50),
        ("duplicate_warn", duplicate_hash_extra_pcnt, args.dup_warn),
    ]
    any_warn = False
    for name, value, threshold in warning_rows:
        status = threshold_status(value, threshold, "WARN", "OK")
        if status == "WARN":
            any_warn = True
        threshold_text = "None" if threshold is None else f"{threshold:.2f}"
        print(f"{name:<30} status={status:<4} value={format_percent(value)}% threshold={threshold_text}")
    print("--- FAILS ---")
    fail_rows = [
        ("unexpected_empty_core_fail", unexpected_empty_core_pages_pcnt, args.unexpected_empty_core_fail),
        ("len_core_fail", len_core_warn_val, args.len_core_fail),
        ("len_total_fail", len_total_warn_val, args.len_total_fail),
        ("duplicate_fail", duplicate_hash_extra_pcnt, args.dup_fail),
    ]
    any_fail = False
    for name, value, threshold in fail_rows:
        status = threshold_status(value, threshold, "FAIL", "OK")
        if status == "FAIL":
            any_fail = True
        threshold_text = "None" if threshold is None else f"{threshold:.2f}"
        print(f"{name:<30} status={status:<4} value={format_percent(value)}% threshold={threshold_text}")

    if any_fail:
        print("FAIL: sanity checks failed")
        raise SystemExit(1)
    if any_warn:
        print("WARN: sanity checks degraded")
        raise SystemExit(0)
    print("OK: sanity checks passed")
    raise SystemExit(0)


if __name__ == "__main__":
    main()

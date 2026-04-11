#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple


def load_jsonl(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def strip_heading_prefix(chunk_text: str, section_path) -> str:
    text = norm_ws(chunk_text)
    if isinstance(section_path, list):
        parts = [str(p).strip() for p in section_path if str(p).strip()]
    else:
        parts = [p.strip() for p in str(section_path or "").split("/") if p.strip()]
    heading = ""
    if len(parts) >= 1:
        heading = parts[-1]
    if not heading:
        return text
    pat = rf"^{re.escape(heading)}(?:\s*[:\-]\s*|\s+)"
    return re.sub(pat, "", text, count=1, flags=re.I)


def word_anchor_patterns(text: str, width: int = 10) -> Tuple[str, str]:
    words = re.findall(r"[A-Za-z0-9']+", norm_ws(text))
    if not words:
        return "", ""
    if len(words) <= width:
        pat = r"\b" + r"\W+".join(map(re.escape, words)) + r"\b"
        return pat, pat
    start = words[:width]
    end = words[-width:]
    p_start = r"\b" + r"\W+".join(map(re.escape, start)) + r"\b"
    p_end = r"\b" + r"\W+".join(map(re.escape, end)) + r"\b"
    return p_start, p_end


def locate_span(source: str, text: str, cursor: int) -> Tuple[Optional[int], Optional[int], str]:
    if not text:
        return None, None, "empty"

    pos = source.find(text, max(0, cursor))
    if pos >= 0:
        return pos, pos + len(text), "exact"

    for width in (12, 10, 8, 6):
        p_start, p_end = word_anchor_patterns(text, width=width)
        if not p_start:
            continue
        m1 = re.search(p_start, source[max(0, cursor):], flags=re.I)
        if not m1:
            continue
        abs_start = max(0, cursor) + m1.start()
        probe_from = max(0, cursor) + m1.end()
        m2 = re.search(p_end, source[probe_from:], flags=re.I)
        if not m2:
            continue
        abs_end = probe_from + m2.end()
        if abs_end <= abs_start:
            continue
        return abs_start, abs_end, "anchor"

    return None, None, "missing"


def search_floor(prev_end: int, text: str) -> int:
    """Allow overlap-aware matching by searching slightly before prev_end.

    Fixed chunks may legally start inside the suffix of the previous chunk.
    Searching from ``prev_end`` only works for near-partitioning chunkers and
    misses valid overlapped chunks. A safe lower bound is ``prev_end - len(text)``,
    because the next chunk cannot start earlier than one full current-chunk length
    before its end.
    """
    return max(0, prev_end - len(text or ""))


def is_significant_gap(gap: str) -> bool:
    g = norm_ws(gap)
    if not g:
        return False
    if len(g) <= 40:
        return False
    if not re.search(r"[A-Za-z0-9]", g):
        return False

    lead = re.sub(r"^[\W_]+", "", g)
    heading_like = bool(
        re.match(r"^(Chapter\s+\d+\b.*)$", lead, flags=re.I)
        or re.match(r"^(Part\s+[IVXLCDM]+\b.*)$", lead, flags=re.I)
        or re.match(r"^(\d+\.\d+(?:\.\d+)?\s+[A-Z].*)$", lead)
    )
    if heading_like and len(lead) <= 320:
        return False
    return True


def merge_intervals(intervals: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    if not intervals:
        return []
    iv = sorted(intervals)
    out = [iv[0]]
    for s, e in iv[1:]:
        ps, pe = out[-1]
        if s <= pe:
            out[-1] = (ps, max(pe, e))
        else:
            out.append((s, e))
    return out


def build_source_with_page_spans(pages_scope) -> Tuple[str, List[Tuple[int, int, int]]]:
    parts = []
    spans: List[Tuple[int, int, int]] = []
    cur = 0
    for r in pages_scope:
        page_no = int(r.get("page", 0))
        text = norm_ws(r.get("clean_text", "") or "")
        if not text:
            continue
        if parts:
            cur += 1
        start = cur
        parts.append(text)
        cur += len(text)
        end = cur
        spans.append((page_no, start, end))
    return " ".join(parts), spans


def charpos_to_page(pos: int, page_spans: List[Tuple[int, int, int]]) -> Optional[int]:
    for page_no, s, e in page_spans:
        if s <= pos < e:
            return page_no
    return None


def is_bad_boundary_start(text: str) -> bool:
    t = norm_ws(text)
    if not t:
        return False
    return bool(
        re.match(r"^[,;:)\]}\-]", t)
        or re.match(r"^(and|or|of|the|to)\b", t)
    )


def is_bad_boundary_end(text: str) -> bool:
    t = norm_ws(text)
    if not t:
        return False
    return bool(
        re.search(r"[(\[{\-]$", t)
        or re.search(r"\b(and|or|of|the|to)$", t)
    )


def min_threshold_status(value: float, threshold: float, fail_label: str, ok_label: str) -> str:
    return ok_label if value >= threshold else fail_label


def max_threshold_status(value: float, threshold: float, fail_label: str, ok_label: str) -> str:
    return ok_label if value <= threshold else fail_label


def main() -> None:
    p = argparse.ArgumentParser(description="Fixed chunk page mapping: holes, coverage, page ranges")
    p.add_argument("--pages", type=Path, required=True)
    p.add_argument("--chunks", type=Path, required=True)
    p.add_argument("--scope", choices=("chunk-pages", "all-pages"), default="chunk-pages")
    p.add_argument("--min-coverage", type=float, default=0.98)
    p.add_argument("--min-coverage-warn", type=float, default=0.99)
    p.add_argument("--ignore-leading-gap", action="store_true")
    p.add_argument("--max-page-start-delta", type=int, default=1)
    p.add_argument("--max-page-end-delta", type=int, default=1)
    p.add_argument("--boundary-warn-ratio", type=float, default=0.10)
    p.add_argument("--report-only", action="store_true")
    args = p.parse_args()

    pages = load_jsonl(args.pages)
    chunks = load_jsonl(args.chunks)
    if not pages:
        print(f"FAIL: no pages in {args.pages}")
        sys.exit(1)
    if not chunks:
        print(f"FAIL: no chunks in {args.chunks}")
        sys.exit(1)

    chunks = sorted(chunks, key=lambda r: int(r.get("chunk_index", 0)))
    idxs = [int(r.get("chunk_index", -1)) for r in chunks]
    if idxs != list(range(len(chunks))):
        print("FAIL: chunk_index is not strictly increasing 0..N-1")
        sys.exit(1)

    pages_sorted = sorted(pages, key=lambda x: int(x.get("page", 0)))
    min_chunk_page = min(int(r.get("page_start", 0)) for r in chunks)
    max_chunk_page = max(int(r.get("page_end", 0)) for r in chunks)
    if args.scope == "chunk-pages":
        pages_scope = [
            r for r in pages_sorted if min_chunk_page <= int(r.get("page", 0)) <= max_chunk_page
        ]
    else:
        pages_scope = pages_sorted
    if not pages_scope:
        print(f"FAIL: no scoped pages for scope={args.scope}")
        sys.exit(1)

    min_scope_page = min(int(r.get("page", 0)) for r in pages_scope)
    max_scope_page = max(int(r.get("page", 0)) for r in pages_scope)

    source, page_spans = build_source_with_page_spans(pages_scope)
    source_len = len(source)

    prev_end = 0
    spans: List[Tuple[int, int]] = []
    misses = []
    hole_viol = []
    order_viol = []
    page_viol = []
    boundary_warn = []
    method_counts = {"exact": 0, "anchor": 0, "empty": 0, "exact_unstripped": 0, "anchor_unstripped": 0}
    prev_start = -1
    prev_page_start = -1

    for r in chunks:
        idx = int(r.get("chunk_index", 0))
        path = r.get("section_path", [])
        raw_text = norm_ws(r.get("text", ""))
        stripped_text = strip_heading_prefix(raw_text, path)
        floor = search_floor(prev_end, stripped_text)
        s, e, method = locate_span(source, stripped_text, floor)
        if (s is None or e is None) and raw_text and raw_text != stripped_text:
            floor = search_floor(prev_end, raw_text)
            s2, e2, method2 = locate_span(source, raw_text, floor)
            if s2 is not None and e2 is not None:
                s, e, method = s2, e2, f"{method2}_unstripped"
        method_counts[method] = method_counts.get(method, 0) + 1
        if s is None or e is None:
            misses.append((idx, path, stripped_text[:140], raw_text[:140]))
            continue

        if s < prev_start:
            order_viol.append((idx, prev_start, s, path))

        page_start = charpos_to_page(s, page_spans)
        page_end = charpos_to_page(max(s, e - 1), page_spans)
        chunk_page_start = int(r.get("page_start", 0))
        chunk_page_end = int(r.get("page_end", 0))
        if page_start is None or page_end is None:
            page_viol.append((idx, chunk_page_start, chunk_page_end, page_start, page_end, path))
        elif abs(chunk_page_start - page_start) > args.max_page_start_delta:
            page_viol.append((idx, chunk_page_start, chunk_page_end, page_start, page_end, path))
        elif abs(chunk_page_end - page_end) > args.max_page_end_delta:
            page_viol.append((idx, chunk_page_start, chunk_page_end, page_start, page_end, path))
        elif page_start < prev_page_start:
            page_viol.append((idx, chunk_page_start, chunk_page_end, page_start, page_end, path))
        if page_start is not None:
            prev_page_start = page_start

        if is_bad_boundary_start(raw_text) or is_bad_boundary_end(raw_text):
            boundary_warn.append((idx, path, raw_text[:120]))

        if s > prev_end:
            gap = source[prev_end:s]
            is_leading_gap = (not spans and prev_end == 0)
            if is_significant_gap(gap) and not (is_leading_gap and args.ignore_leading_gap):
                hole_viol.append((idx, len(gap), gap[:120]))

        spans.append((s, e))
        prev_start = s
        prev_end = max(prev_end, e)

    merged = merge_intervals(spans)
    covered_chars = sum(e - s for s, e in merged)
    coverage_raw = (covered_chars / source_len) if source_len else 0.0
    significant_gap_chars = sum(glen for _, glen, _ in hole_viol)
    coverage_effective = ((source_len - significant_gap_chars) / source_len) if source_len else 0.0
    boundary_warn_ratio = (len(boundary_warn) / len(chunks)) if chunks else 0.0

    method_width = max(len(name) for name in method_counts)
    violation_counts = {
        "order_violations": len(order_viol),
        "hole_violations": len(hole_viol),
        "page_violations": len(page_viol),
        "boundary_warnings": len(boundary_warn),
    }
    violation_width = max(len(name) for name in violation_counts)
    status_name_width = max(
        len("coverage_effective_warn"),
        len("boundary_warning_ratio_warn"),
        len("coverage_effective_fail"),
    )

    def print_status_row(name: str, status: str, value: float, threshold: float) -> None:
        print(
            f"{name:<{status_name_width}} "
            f"{'status':<9}= {status:<4} "
            f"{'value':<9}= {value:<8.4f} "
            f"{'threshold':<9}= {threshold:<8.4f}"
        )

    print("--- corpus ---")
    print(
        f"pages_total={len(pages)} pages_scope={len(pages_scope)} chunks={len(chunks)} "
        f"scope_page_span={min_scope_page}..{max_scope_page} scope={args.scope}"
    )
    print("--- chunks ---")
    print(f"matched_chunks={len(spans)}/{len(chunks)}")
    print("methods:")
    method_order = ["exact", "anchor", "empty", "exact_unstripped", "anchor_unstripped"]
    for name in method_order:
        print(f"  {name:<{method_width}} = {method_counts.get(name, 0)}")
    if "missing" in method_counts:
        print(f"  {'missing':<{method_width}} = {method_counts['missing']}")
    print("violations:")
    violation_order = [
        "order_violations",
        "hole_violations",
        "page_violations",
        "boundary_warnings",
    ]
    for name in violation_order:
        print(f"  {name:<{violation_width}} = {violation_counts[name]}")
    print("--- coverage ---")
    print(
        f"coverage_raw={coverage_raw:.4f} "
        f"coverage_effective={coverage_effective:.4f} significant_gap_chars={significant_gap_chars}"
    )
    print("--- warnings ---")
    print_status_row(
        "coverage_effective_warn",
        min_threshold_status(coverage_effective, args.min_coverage_warn, "WARN", "OK"),
        coverage_effective,
        args.min_coverage_warn,
    )
    print_status_row(
        "boundary_warning_ratio_warn",
        max_threshold_status(boundary_warn_ratio, args.boundary_warn_ratio, "WARN", "OK"),
        boundary_warn_ratio,
        args.boundary_warn_ratio,
    )
    print("--- fails ---")
    print_status_row(
        "coverage_effective_fail",
        min_threshold_status(coverage_effective, args.min_coverage, "FAIL", "OK"),
        coverage_effective,
        args.min_coverage,
    )

    any_warn = (
        coverage_effective < args.min_coverage_warn
        or boundary_warn_ratio > args.boundary_warn_ratio
    )

    fail = False
    if misses:
        fail = True
    if hole_viol:
        fail = True
    if order_viol:
        fail = True
    if page_viol:
        fail = True
    if coverage_effective < args.min_coverage:
        fail = True

    if fail:
        if args.report_only:
            return
        print("FAIL: fixed page mapping test failed")
        sys.exit(1)

    if any_warn:
        print("WARN: fixed page mapping checks degraded")
        return

    print("OK: fixed page mapping checks passed")


if __name__ == "__main__":
    main()

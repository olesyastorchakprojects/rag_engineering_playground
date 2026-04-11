#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Execution.parsing.common.book_metadata_validation import load_and_validate_book_content_metadata


def load_jsonl(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def load_metadata(path: Path) -> dict:
    return load_and_validate_book_content_metadata(path)


def metadata_union_pages(metadata: dict) -> Set[int]:
    pages: Set[int] = set()
    for key in ("parts", "chapters", "sections", "subsections"):
        for entry in metadata.get(key) or []:
            ranges = entry.get("ranges") if isinstance(entry, dict) else None
            pdf = ranges.get("pdf") if isinstance(ranges, dict) else None
            start = pdf.get("start") if isinstance(pdf, dict) else None
            end = pdf.get("end") if isinstance(pdf, dict) else None
            if isinstance(start, int) and isinstance(end, int):
                pages.update(range(start, end + 1))
    return pages


def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def strip_heading_prefix(chunk_text: str, section_path) -> str:
    text = norm_ws(chunk_text)
    if isinstance(section_path, list):
        parts = [str(p).strip() for p in section_path if str(p).strip()]
    else:
        parts = [p.strip() for p in str(section_path or "").split("/") if p.strip()]
    heading = ""
    if len(parts) >= 4 and parts[-1] != "Overview":
        heading = parts[-1]
    elif len(parts) >= 3 and parts[-1] != "Overview":
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

    # First try exact substring from cursor.
    pos = source.find(text, max(0, cursor))
    if pos >= 0:
        return pos, pos + len(text), "exact"

    # Fallback: flexible word-anchor start/end in order.
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
            cur += 1  # join separator " "
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
        or re.match(r"^(and|or|of|the|to)\b", t, flags=re.I)
    )


def is_bad_boundary_end(text: str) -> bool:
    t = norm_ws(text)
    if not t:
        return False
    return bool(
        re.search(r"[(\[{\-]$", t)
        or re.search(r"\b(and|or|of|the|to)$", t, flags=re.I)
    )


def min_threshold_status(value: float, threshold: float, fail_label: str, ok_label: str) -> str:
    return ok_label if value >= threshold else fail_label


def max_threshold_status(value: float, threshold: float, fail_label: str, ok_label: str) -> str:
    return ok_label if value <= threshold else fail_label


def main() -> None:
    p = argparse.ArgumentParser(
        description="Chunk span quality: overlap, holes, coverage"
    )
    p.add_argument("--pages", type=Path, required=True)
    p.add_argument("--chunks", type=Path, required=True)
    p.add_argument("--metadata", type=Path, required=True)
    p.add_argument("--scope", choices=("metadata-union", "chunk-pages", "all-pages"), default="metadata-union")
    p.add_argument("--overlap-mode", choices=("off", "on"), default="off")
    p.add_argument("--expected-overlap", type=int, default=0, help="Expected overlap in chars when overlap-mode=on")
    p.add_argument("--overlap-tolerance", type=int, default=30, help="+/- tolerance for expected overlap")
    p.add_argument(
        "--max-overlap",
        type=int,
        default=40,
        help="Hard cap on overlap in chars (off mode default allows small boundary jitter)",
    )
    p.add_argument("--min-coverage", type=float, default=0.98, help="Minimum covered source fraction")
    p.add_argument(
        "--min-coverage-warn",
        type=float,
        default=0.99,
        help="Warning threshold for effective covered source fraction",
    )
    p.add_argument(
        "--ignore-leading-gap",
        action="store_true",
        help="Ignore the gap before first matched chunk (useful when source contains front matter not chunked)",
    )
    p.add_argument(
        "--max-page-start-delta",
        type=int,
        default=1,
        help="Allowed |chunk.page_start - inferred_page_start| delta",
    )
    p.add_argument(
        "--boundary-warn-ratio",
        type=float,
        default=0.10,
        help="Warn if suspicious chunk boundaries exceed this ratio",
    )
    p.add_argument("--report-only", action="store_true")
    args = p.parse_args()

    pages = load_jsonl(args.pages)
    chunks = load_jsonl(args.chunks)
    metadata = load_metadata(args.metadata)
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
    if args.scope == "metadata-union":
        metadata_pages = metadata_union_pages(metadata)
        pages_scope = [r for r in pages_sorted if int(r.get("page", 0)) in metadata_pages]
    elif args.scope == "chunk-pages":
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

    cursor = 0
    prev_end = 0
    spans: List[Tuple[int, int]] = []
    misses = []
    overlap_viol = []
    hole_viol = []
    order_viol = []
    page_viol = []
    boundary_warn = []
    method_counts = {"exact": 0, "anchor": 0, "empty": 0, "exact_unstripped": 0, "anchor_unstripped": 0}
    prev_start = -1
    prev_page_start = -1

    for r in chunks:
        idx = int(r.get("chunk_index", 0))
        path = r.get("section_path", "")
        raw_text = norm_ws(r.get("text", ""))
        stripped_text = strip_heading_prefix(raw_text, path)
        s, e, method = locate_span(source, stripped_text, cursor)
        if (s is None or e is None) and raw_text and raw_text != stripped_text:
            s2, e2, method2 = locate_span(source, raw_text, cursor)
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
        elif chunk_page_end != page_end:
            page_viol.append((idx, chunk_page_start, chunk_page_end, page_start, page_end, path))
        elif page_start < prev_page_start:
            page_viol.append((idx, chunk_page_start, chunk_page_end, page_start, page_end, path))
        if page_start is not None:
            prev_page_start = page_start

        if is_bad_boundary_start(raw_text) or is_bad_boundary_end(raw_text):
            boundary_warn.append((idx, path, raw_text[:120]))

        overlap = max(0, prev_end - s)
        if args.overlap_mode == "off":
            if overlap > args.max_overlap:
                overlap_viol.append((idx, overlap, path))
        else:
            lo = max(0, args.expected_overlap - args.overlap_tolerance)
            hi = args.expected_overlap + args.overlap_tolerance
            if not (lo <= overlap <= hi) and overlap > args.max_overlap:
                overlap_viol.append((idx, overlap, path))

        if s > prev_end:
            gap = source[prev_end:s]
            # Significant gap: contains alnum content, not just separators.
            is_leading_gap = (not spans and prev_end == 0)
            if is_significant_gap(gap) and not (is_leading_gap and args.ignore_leading_gap):
                hole_viol.append((idx, len(gap), gap[:120]))

        spans.append((s, e))
        prev_start = s
        prev_end = max(prev_end, e)
        cursor = max(cursor, e)

    merged = merge_intervals(spans)
    covered_chars = sum(e - s for s, e in merged)
    coverage = (covered_chars / source_len) if source_len else 0.0
    significant_gap_chars = sum(glen for _, glen, _ in hole_viol)
    effective_coverage = ((source_len - significant_gap_chars) / source_len) if source_len else 0.0
    boundary_warn_ratio = (len(boundary_warn) / len(chunks)) if chunks else 0.0
    method_width = max(len(name) for name in method_counts)
    violation_counts = {
        "order_violations": len(order_viol),
        "overlap_violations": len(overlap_viol),
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
    for name, value in method_counts.items():
        print(f"  {name:<{method_width}} = {value}")
    print("violations:")
    for name, value in violation_counts.items():
        print(f"  {name:<{violation_width}} = {value}")
    print("--- coverage ---")
    print(
        f"coverage_raw={coverage:.4f} "
        f"coverage_effective={effective_coverage:.4f} significant_gap_chars={significant_gap_chars}"
    )
    print("--- warnings ---")
    print_status_row(
        "coverage_effective_warn",
        min_threshold_status(effective_coverage, args.min_coverage_warn, "WARN", "OK"),
        effective_coverage,
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
        min_threshold_status(effective_coverage, args.min_coverage, "FAIL", "OK"),
        effective_coverage,
        args.min_coverage,
    )
    any_warn = (
        effective_coverage < args.min_coverage_warn
        or boundary_warn_ratio > args.boundary_warn_ratio
    )

    fail = False
    if misses:
        fail = True
    if overlap_viol:
        fail = True
    if hole_viol:
        fail = True
    if order_viol:
        fail = True
    if page_viol:
        fail = True
    if effective_coverage < args.min_coverage:
        fail = True

    if fail:
        if args.report_only:
            return
        print("FAIL: span quality test failed")
        sys.exit(1)

    if any_warn:
        print("WARN: span quality checks degraded")
        return

    print("OK: span quality checks passed")


if __name__ == "__main__":
    main()

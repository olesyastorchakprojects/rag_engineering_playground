#!/usr/bin/env python3
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Set

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Execution.parsing.common.book_metadata_validation import load_and_validate_book_content_metadata

PLAIN_TOKEN_RE = re.compile(r"[A-Za-z0-9']+")
# Tech tokenizer keeps common technical separators inside a token, so totals can be
# lower than plain tokenization on the same text (for example, "node_id" stays whole).
TECH_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_:\-./']*")


def load_jsonl(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def load_json(path: Path):
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


def normalize_text(s: str) -> str:
    # Keep comparison deterministic and separator-independent.
    return re.sub(r"\s+", " ", (s or "").strip())


def tokenize_plain(s: str):
    return PLAIN_TOKEN_RE.findall(s.lower())


def tokenize_tech(s: str):
    return TECH_TOKEN_RE.findall(s.lower())


def projection_metrics(src_text: str, chk_text: str, tokenizer) -> dict:
    src_tokens = Counter(tokenizer(src_text))
    chk_tokens = Counter(tokenizer(chk_text))
    overlap = sum(min(v, chk_tokens.get(k, 0)) for k, v in src_tokens.items())
    src_total = sum(src_tokens.values())
    chk_total = sum(chk_tokens.values())
    recall = (overlap / src_total) if src_total else 0.0
    precision = (overlap / chk_total) if chk_total else 0.0
    token_ratio = (chk_total / src_total) if src_total else 0.0
    dup_excess = sum(
        max(0, chk_tokens.get(tok, 0) - src_cnt)
        for tok, src_cnt in src_tokens.items()
    )
    # Tokens that exist only in chunks are also duplication/hallucination excess.
    dup_excess += sum(
        cnt for tok, cnt in chk_tokens.items() if tok not in src_tokens
    )
    dup_factor = (dup_excess / src_total) if src_total else 0.0
    src_unique = len(src_tokens)
    chk_unique = len(chk_tokens)
    unique_overlap = len(set(src_tokens.keys()) & set(chk_tokens.keys()))
    unique_recall = (unique_overlap / src_unique) if src_unique else 0.0
    unique_precision = (unique_overlap / chk_unique) if chk_unique else 0.0
    return {
        "src_total": src_total,
        "chk_total": chk_total,
        "overlap": overlap,
        "recall": recall,
        "precision": precision,
        "token_ratio": token_ratio,
        "dup_excess": dup_excess,
        "dup_factor": dup_factor,
        "src_unique": src_unique,
        "chk_unique": chk_unique,
        "unique_overlap": unique_overlap,
        "unique_recall": unique_recall,
        "unique_precision": unique_precision,
    }


def min_threshold_status(value: float, threshold: float, fail_label: str, ok_label: str) -> str:
    return ok_label if value >= threshold else fail_label


def max_threshold_status(value: float, threshold: float, fail_label: str, ok_label: str) -> str:
    return ok_label if value <= threshold else fail_label


def main() -> None:
    p = argparse.ArgumentParser(
        description="Chunker truth test: compare chunks text to joined page clean_text"
    )
    p.add_argument("--pages", type=Path, required=True)
    p.add_argument("--chunks", type=Path, required=True)
    p.add_argument("--metadata", type=Path, required=True)
    p.add_argument("--sep", type=str, default="\n\n", help="Join separator for source/chunks")
    p.add_argument(
        "--scope",
        choices=("metadata-union", "chunk-pages", "all-pages"),
        default="metadata-union",
        help="Source scope: chunk page span or all pages",
    )
    p.add_argument(
        "--min-recall",
        type=float,
        default=0.94,
        help="Minimum token recall overlap vs source",
    )
    p.add_argument(
        "--min-recall-warn",
        type=float,
        default=0.955,
        help="Warning threshold for token recall overlap vs source",
    )
    p.add_argument(
        "--min-precision",
        type=float,
        default=0.992,
        help="Minimum token precision overlap vs chunks",
    )
    p.add_argument(
        "--min-precision-warn",
        type=float,
        default=0.994,
        help="Warning threshold for token precision overlap vs chunks",
    )
    p.add_argument(
        "--min-char-ratio",
        type=float,
        default=0.90,
        help="Minimum chunk/source char ratio (normalized text length)",
    )
    p.add_argument(
        "--min-char-ratio-warn",
        type=float,
        default=0.93,
        help="Warning threshold for minimum chunk/source char ratio",
    )
    p.add_argument(
        "--max-char-ratio",
        type=float,
        default=1.03,
        help="Maximum chunk/source char ratio (normalized text length)",
    )
    p.add_argument(
        "--max-char-ratio-warn",
        type=float,
        default=1.02,
        help="Warning threshold for maximum chunk/source char ratio",
    )
    p.add_argument(
        "--max-dup-factor",
        type=float,
        default=0.02,
        help="Maximum duplication factor (plain projection): dup_excess / total_source_tokens",
    )
    p.add_argument(
        "--max-dup-factor-warn",
        type=float,
        default=0.01,
        help="Warning threshold for duplication factor (plain projection)",
    )
    p.add_argument(
        "--min-recall-tech",
        type=float,
        default=0.90,
        help="Minimum token recall overlap vs source (tech projection)",
    )
    p.add_argument(
        "--min-recall-tech-warn",
        type=float,
        default=0.93,
        help="Warning threshold for token recall overlap vs source (tech projection)",
    )
    p.add_argument(
        "--min-precision-tech",
        type=float,
        default=0.955,
        help="Minimum token precision overlap vs chunks (tech projection)",
    )
    p.add_argument(
        "--min-precision-tech-warn",
        type=float,
        default=0.97,
        help="Warning threshold for token precision overlap vs chunks (tech projection)",
    )
    p.add_argument(
        "--max-dup-factor-tech",
        type=float,
        default=0.045,
        help="Maximum duplication factor (tech projection)",
    )
    p.add_argument(
        "--max-dup-factor-tech-warn",
        type=float,
        default=0.025,
        help="Warning threshold for duplication factor (tech projection)",
    )
    p.add_argument("--report-only", action="store_true", help="Do not fail on mismatch")
    args = p.parse_args()

    pages = load_jsonl(args.pages)
    chunks = load_jsonl(args.chunks)
    metadata = load_json(args.metadata)
    if not pages:
        print(f"FAIL: no pages in {args.pages}")
        sys.exit(1)
    if not chunks:
        print(f"FAIL: no chunks in {args.chunks}")
        sys.exit(1)

    pages = sorted(pages, key=lambda r: int(r.get("page", 0)))
    chunks = sorted(chunks, key=lambda r: int(r.get("chunk_index", 0)))

    min_chunk_page = min(int(r.get("page_start", 0)) for r in chunks)
    max_chunk_page = max(int(r.get("page_end", 0)) for r in chunks)
    if args.scope == "metadata-union":
        metadata_pages = metadata_union_pages(metadata)
        pages_scope = [r for r in pages if int(r.get("page", 0)) in metadata_pages]
    elif args.scope == "chunk-pages":
        pages_scope = [
            r for r in pages if min_chunk_page <= int(r.get("page", 0)) <= max_chunk_page
        ]
    else:
        pages_scope = pages
    if not pages_scope:
        print(f"FAIL: no scoped pages for scope={args.scope}")
        sys.exit(1)
    excluded_pages = len(pages) - len(pages_scope)
    min_scope_page = min(int(r.get("page", 0)) for r in pages_scope)
    max_scope_page = max(int(r.get("page", 0)) for r in pages_scope)

    full_clean_text = args.sep.join((r.get("clean_text", "") or "").strip() for r in pages_scope)
    full_chunks_text = args.sep.join((r.get("text", "") or "").strip() for r in chunks)

    clean_norm = normalize_text(full_clean_text)
    chunks_norm = normalize_text(full_chunks_text)

    ratio = (len(chunks_norm) / len(clean_norm)) if clean_norm else 0.0
    plain = projection_metrics(clean_norm, chunks_norm, tokenize_plain)
    tech = projection_metrics(clean_norm, chunks_norm, tokenize_tech)

    metric_width = len("excluded_pages")
    metric_cell_width = 28

    def print_metric(name: str, value: object) -> None:
        print(f"{name:<{metric_width}} = {value}")

    def format_metric(name: str, value: object) -> str:
        return f"{name:<{metric_width}} = {value:<{metric_cell_width - metric_width - 3}}"

    def print_status_row(name: str, status: str, value: float, threshold: float) -> None:
        print(
            f"{name:<30} "
            f"{'status':<9}= {status:<4} "
            f"{'value':<9}= {value:<8.4f} "
            f"{'threshold':<9}= {threshold:<8.4f}"
        )

    print("--- corpus ---")
    print(
        f"{format_metric('pages_total', len(pages))}"
        f"{format_metric('pages_scope', len(pages_scope))}"
        f"{format_metric('excluded_pages', excluded_pages)}"
    )
    print_metric("chunks", len(chunks))
    print_metric("scope_page_span", f"{min_scope_page}..{max_scope_page}")
    print(
        f"{format_metric('source_chars', len(clean_norm))}"
        f"{format_metric('chunk_chars', len(chunks_norm))}"
        f"{format_metric('char_ratio', f'{ratio:.4f}')}"
    )
    print("--- plain ---")
    print(
        format_metric("token_source", plain["src_total"])
        + format_metric("token_chunks", plain["chk_total"])
        + format_metric("overlap", plain["overlap"])
        + format_metric("token_ratio", f"{plain['token_ratio']:.4f}")
    )
    print_metric("recall", f"{plain['recall']:.4f}")
    print_metric("precision", f"{plain['precision']:.4f}")
    print_metric("dup_excess", plain['dup_excess'])
    print_metric("dup_factor", f"{plain['dup_factor']:.4f}")
    print(
        format_metric("unique_source", plain["src_unique"])
        + format_metric("unique_chunks", plain["chk_unique"])
        + format_metric("unique_overlap", plain["unique_overlap"])
    )
    print(
        format_metric("unique_recall", f"{plain['unique_recall']:.4f}")
        + format_metric("unique_precision", f"{plain['unique_precision']:.4f}")
    )
    print("--- tech ---")
    print(
        format_metric("token_source", tech["src_total"])
        + format_metric("token_chunks", tech["chk_total"])
        + format_metric("overlap", tech["overlap"])
        + format_metric("token_ratio", f"{tech['token_ratio']:.4f}")
    )
    print_metric("recall", f"{tech['recall']:.4f}")
    print_metric("precision", f"{tech['precision']:.4f}")
    print_metric("dup_excess", tech["dup_excess"])
    print_metric("dup_factor", f"{tech['dup_factor']:.4f}")
    print(
        format_metric("unique_source", tech["src_unique"])
        + format_metric("unique_chunks", tech["chk_unique"])
        + format_metric("unique_overlap", tech["unique_overlap"])
    )
    print(
        format_metric("unique_recall", f"{tech['unique_recall']:.4f}")
        + format_metric("unique_precision", f"{tech['unique_precision']:.4f}")
    )

    print("--- WARNINGS ---")
    warning_rows = [
        ("plain_recall_warn", min_threshold_status(plain["recall"], args.min_recall_warn, "WARN", "OK"), plain["recall"], args.min_recall_warn),
        ("plain_precision_warn", min_threshold_status(plain["precision"], args.min_precision_warn, "WARN", "OK"), plain["precision"], args.min_precision_warn),
        ("plain_dup_factor_warn", max_threshold_status(plain["dup_factor"], args.max_dup_factor_warn, "WARN", "OK"), plain["dup_factor"], args.max_dup_factor_warn),
        ("tech_recall_warn", min_threshold_status(tech["recall"], args.min_recall_tech_warn, "WARN", "OK"), tech["recall"], args.min_recall_tech_warn),
        ("tech_precision_warn", min_threshold_status(tech["precision"], args.min_precision_tech_warn, "WARN", "OK"), tech["precision"], args.min_precision_tech_warn),
        ("tech_dup_factor_warn", max_threshold_status(tech["dup_factor"], args.max_dup_factor_tech_warn, "WARN", "OK"), tech["dup_factor"], args.max_dup_factor_tech_warn),
        ("char_ratio_min_warn", min_threshold_status(ratio, args.min_char_ratio_warn, "WARN", "OK"), ratio, args.min_char_ratio_warn),
        ("char_ratio_max_warn", max_threshold_status(ratio, args.max_char_ratio_warn, "WARN", "OK"), ratio, args.max_char_ratio_warn),
    ]
    any_warn = False
    for name, status, value, threshold in warning_rows:
        if status == "WARN":
            any_warn = True
        print_status_row(name, status, value, threshold)

    print("--- FAILS ---")
    fail_rows = [
        ("plain_recall_fail", min_threshold_status(plain["recall"], args.min_recall, "FAIL", "OK"), plain["recall"], args.min_recall),
        ("plain_precision_fail", min_threshold_status(plain["precision"], args.min_precision, "FAIL", "OK"), plain["precision"], args.min_precision),
        ("plain_dup_factor_fail", max_threshold_status(plain["dup_factor"], args.max_dup_factor, "FAIL", "OK"), plain["dup_factor"], args.max_dup_factor),
        ("tech_recall_fail", min_threshold_status(tech["recall"], args.min_recall_tech, "FAIL", "OK"), tech["recall"], args.min_recall_tech),
        ("tech_precision_fail", min_threshold_status(tech["precision"], args.min_precision_tech, "FAIL", "OK"), tech["precision"], args.min_precision_tech),
        ("tech_dup_factor_fail", max_threshold_status(tech["dup_factor"], args.max_dup_factor_tech, "FAIL", "OK"), tech["dup_factor"], args.max_dup_factor_tech),
        ("char_ratio_min_fail", min_threshold_status(ratio, args.min_char_ratio, "FAIL", "OK"), ratio, args.min_char_ratio),
        ("char_ratio_max_fail", max_threshold_status(ratio, args.max_char_ratio, "FAIL", "OK"), ratio, args.max_char_ratio),
    ]
    any_fail = False
    for name, status, value, threshold in fail_rows:
        if status == "FAIL":
            any_fail = True
        print_status_row(name, status, value, threshold)

    if not any_fail and not any_warn:
        print("OK: chunk/source consistency is within configured thresholds")
        return

    if any_warn and not any_fail:
        print("WARN: truth consistency degraded")
        return

    if args.report_only:
        print("WARN: report-only mode, mismatch is non-blocking")
        return

    print("FAIL: truth consistency metrics out of bounds")
    sys.exit(1)


if __name__ == "__main__":
    main()

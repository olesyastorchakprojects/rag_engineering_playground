#!/usr/bin/env python3
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Execution.parsing.common.book_metadata_validation import load_and_validate_book_content_metadata

TOKEN_RE = re.compile(r"[A-Za-z0-9']+")


def load_rows(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def format_samples(values, max_samples: int = 5) -> str:
    shown = ",".join(str(v) for v in values[:max_samples])
    suffix = ",..." if len(values) > max_samples else ""
    return f"samples=[{shown}{suffix}]"


def pct(values, p: float) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    k = (len(xs) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    w = k - lo
    return xs[lo] * (1 - w) + xs[hi] * w


def normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def token_count(s: str) -> int:
    return len(TOKEN_RE.findall(s))


def sentence_dupe_score(s: str) -> int:
    # Catch repeated sentence-like fragments (header/footer leaks or concat bugs).
    parts = [normalize_text(x) for x in re.split(r"[.!?;:]\s+", s)]
    parts = [x for x in parts if len(x) >= 30]
    c = Counter(parts)
    return sum(v - 1 for v in c.values() if v > 1)


def load_json(path: Path):
    return load_and_validate_book_content_metadata(path)


def title_tokens(s: str):
    return TOKEN_RE.findall((s or "").lower())


def path_parts(value):
    if isinstance(value, list):
        return [str(part).strip() for part in value if str(part).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split("/") if part.strip()]
    return []


def titles_compatible(tail: str, expected_title: str) -> bool:
    tail_toks = title_tokens(tail)
    expected_toks = title_tokens(expected_title)
    if not tail_toks or not expected_toks:
        return False
    if len(tail_toks) <= len(expected_toks):
        return tail_toks == expected_toks[: len(tail_toks)]
    return expected_toks == tail_toks[: len(expected_toks)]


def build_page_title_index(metadata: dict) -> dict:
    by_page = {}
    for key in ("parts", "chapters", "sections", "subsections"):
        for entry in metadata.get(key) or []:
            title = normalize_text(entry.get("title", ""))
            pdf_ranges = (entry.get("ranges") or {}).get("pdf") or {}
            start = pdf_ranges.get("start")
            end = pdf_ranges.get("end")
            if not isinstance(start, int) or not isinstance(end, int):
                continue
            for page in range(start, end + 1):
                by_page.setdefault(page, set()).add(title)
    return by_page


def metrics(
    rows,
    tiny_chars: int,
    huge_chars: int,
    page_title_index: dict,
):
    texts = [normalize_text(r.get("text", "")) for r in rows]
    char_lens = [len(t) for t in texts]
    tok_lens = [token_count(t) for t in texts]
    n = len(texts)

    tiny = sum(1 for x in char_lens if x < tiny_chars)
    huge = sum(1 for x in char_lens if x > huge_chars)
    repeated = sum(1 for t in texts if sentence_dupe_score(t) > 0)

    # Mid-word boundary heuristic focused on hyphenation artifacts.
    start_mid = 0
    end_mid = 0
    for t in texts:
        if not t:
            continue
        if re.match(r"^-?[A-Za-z]{2,}-[A-Za-z]{2,}\b", t):
            start_mid += 1
        if re.match(r"^-?\s*[A-Za-z]{2,}\b", t) and re.search(r"[A-Za-z]{2,}-$", t[:20]):
            start_mid += 1
        if re.search(r"[A-Za-z]{2,}-$", t):
            end_mid += 1

    chunk_name_mismatch = 0
    chunk_name_mismatch_examples = []
    for r in rows:
        parts = path_parts(r.get("section_path", []))
        if not parts:
            continue
        tail = parts[-1]
        page = int(r.get("page_start", 0) or 0)
        expected_titles = page_title_index.get(page, set())
        if not expected_titles or not any(titles_compatible(tail, title) for title in expected_titles):
            chunk_name_mismatch += 1
            if len(chunk_name_mismatch_examples) < 10:
                chunk_name_mismatch_examples.append(tail)

    return {
        "chunks": n,
        "chars_min": min(char_lens) if char_lens else 0,
        "chars_max": max(char_lens) if char_lens else 0,
        "chars_p50": pct(char_lens, 0.50),
        "chars_p90": pct(char_lens, 0.90),
        "chars_p95": pct(char_lens, 0.95),
        "chars_p99": pct(char_lens, 0.99),
        "tiny_chars": tiny,
        "tiny_ratio": (tiny / n) if n else 0.0,
        "huge_chars": huge,
        "huge_ratio": (huge / n) if n else 0.0,
        "repeated_sentence_chunks": repeated,
        "repeated_sentence_ratio": (repeated / n) if n else 0.0,
        "midword_ratio": ((start_mid + end_mid) / (2 * n)) if n else 0.0,
        "chunk_name_mismatch": chunk_name_mismatch,
        "chunk_name_mismatch_ratio": (chunk_name_mismatch / n) if n else 0.0,
        "chunk_name_mismatch_examples": chunk_name_mismatch_examples,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Chunk sanitation checks (size distribution + anomaly heuristics)")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--metadata", type=Path, required=True)
    p.add_argument("--tiny-chars", type=int, default=250)
    p.add_argument("--huge-chars", type=int, default=12000)
    p.add_argument("--tiny-ratio-warn", type=float, default=0.10)
    p.add_argument("--tiny-ratio-fail", type=float, default=0.20)
    p.add_argument("--huge-ratio-warn", type=float, default=0.02)
    p.add_argument("--huge-ratio-fail", type=float, default=0.05)
    p.add_argument("--repeated-ratio-warn", type=float, default=0.04)
    p.add_argument("--repeated-ratio-fail", type=float, default=0.08)
    p.add_argument("--midword-ratio-warn", type=float, default=0.05)
    p.add_argument("--midword-ratio-abs-fail", type=float, default=0.10)
    p.add_argument("--chunk-name-mismatch-ratio-warn", type=float, default=0.01)
    p.add_argument("--chunk-name-mismatch-ratio-fail", type=float, default=0.02)
    p.add_argument("--report-only", action="store_true")
    args = p.parse_args()

    rows = load_rows(args.input)
    metadata = load_json(args.metadata)
    if not rows:
        print(f"FAIL: no chunks in {args.input}")
        sys.exit(1)
    page_title_index = build_page_title_index(metadata)

    cur = metrics(
        rows,
        tiny_chars=args.tiny_chars,
        huge_chars=args.huge_chars,
        page_title_index=page_title_index,
    )
    print(f"chunks={cur['chunks']}")
    print("chunk length distribution:")
    shared_label_width = max(
        len("min"),
        len("p50"),
        len("p90"),
        len("p95"),
        len("p99"),
        len("max"),
        len(f"tiny (<{args.tiny_chars})"),
        len(f"huge (>{args.huge_chars})"),
        len("repeated_sentence"),
        len("midword_ratio"),
        len("chunk_name_mismatch"),
    )
    print(f"  {'min':<{shared_label_width}} = {cur['chars_min']}")
    print(f"  {'p50':<{shared_label_width}} = {cur['chars_p50']:.1f}")
    print(f"  {'p90':<{shared_label_width}} = {cur['chars_p90']:.1f}")
    print(f"  {'p95':<{shared_label_width}} = {cur['chars_p95']:.1f}")
    print(f"  {'p99':<{shared_label_width}} = {cur['chars_p99']:.1f}")
    print(f"  {'max':<{shared_label_width}} = {cur['chars_max']}")
    print(
        f"  {f'tiny (<{args.tiny_chars})':<{shared_label_width}} = "
        f"{cur['tiny_chars']} ({cur['tiny_ratio']:.1%})"
    )
    print(
        f"  {f'huge (>{args.huge_chars})':<{shared_label_width}} = "
        f"{cur['huge_chars']} ({cur['huge_ratio']:.1%})"
    )
    print("violations:")
    print(
        f"  {'repeated_sentence':<{shared_label_width}} = "
        f"{cur['repeated_sentence_chunks']}"
    )
    print(
        f"  {'midword_ratio':<{shared_label_width}} = "
        f"{cur['midword_ratio']:.1%}"
    )
    print(
        f"  {'chunk_name_mismatch':<{shared_label_width}} = "
        f"{cur['chunk_name_mismatch']} {format_samples(cur['chunk_name_mismatch_examples'])}"
    )

    fail = False
    warn = False
    warning_rows = []
    fail_rows = []

    def threshold_row(name: str, value: float, threshold: float, *, mode: str = "max", bad_status: str = "FAIL"):
        ok = value <= threshold if mode == "max" else value >= threshold
        status = "OK" if ok else bad_status
        return {
            "name": name,
            "status": status,
            "value": value,
            "threshold": threshold,
        }, (not ok)

    def print_threshold_section(title: str, rows) -> None:
        print(f"{title}:")
        name_width = max((len(row["name"]) for row in rows), default=1)
        status_width = max((len(row["status"]) for row in rows), default=2)
        for row in rows:
            print(
                f"  {row['name']:<{name_width}} "
                f"status = {row['status']:<{status_width}} "
                f"value = {row['value']:.4f} "
                f"threshold = {row['threshold']:.4f}"
            )

    # Absolute caps (sanity guards).
    for name, value, warn_threshold, fail_threshold in [
        ("tiny_ratio", cur["tiny_ratio"], args.tiny_ratio_warn, args.tiny_ratio_fail),
        ("huge_ratio", cur["huge_ratio"], args.huge_ratio_warn, args.huge_ratio_fail),
        ("repeated_sentence_ratio", cur["repeated_sentence_ratio"], args.repeated_ratio_warn, args.repeated_ratio_fail),
        ("midword_ratio", cur["midword_ratio"], args.midword_ratio_warn, args.midword_ratio_abs_fail),
        (
            "chunk_name_mismatch_ratio",
            cur["chunk_name_mismatch_ratio"],
            args.chunk_name_mismatch_ratio_warn,
            args.chunk_name_mismatch_ratio_fail,
        ),
    ]:
        row, breached = threshold_row(f"{name}_warn", value, warn_threshold, bad_status="WARN")
        warning_rows.append(row)
        if breached:
            warn = True
        row, breached = threshold_row(f"{name}_fail", value, fail_threshold)
        fail_rows.append(row)
        if breached:
            fail = True

    print_threshold_section("warnings", warning_rows)
    print_threshold_section("fails", fail_rows)

    if fail:
        if args.report_only:
            print("WARN: sanitation checks degraded (report-only)")
            return
        sys.exit(1)

    if warn:
        print("WARN: sanitation checks degraded")
        return

    print("OK: sanitation checks passed")


if __name__ == "__main__":
    main()

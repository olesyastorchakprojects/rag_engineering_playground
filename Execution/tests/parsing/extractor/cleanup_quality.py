#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Sequence


DEFAULT_PAGES = Path("out/pages.jsonl")
DEFAULT_CONTENT_METADATA = Path("data/content/book_content_metadata.json")
SHORT_WORDS = {"as", "to", "in", "on", "of", "by", "if", "is", "it", "an", "or", "at", "we"}


def load_rows(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_headers(path: Path) -> List[str]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []
    chapters = payload.get("chapters")
    if not isinstance(chapters, list):
        return []
    headers: List[str] = []
    for item in chapters:
        if isinstance(item, dict) and isinstance(item.get("chapter"), int) and isinstance(item.get("title"), str):
            headers.append(f"Chapter {item['chapter']}. {item['title'].strip()}")
    return headers


def format_samples(values: Sequence[Any]) -> str:
    shown = ",".join(str(value) for value in values[:10])
    suffix = ",..." if len(values) > 10 else ""
    return f"samples=[{shown}{suffix}]"


def can_segment(token: str, english_words: set[str], memo: Dict[str, bool]) -> bool:
    if token in memo:
        return memo[token]
    for split_at in range(2, min(20, len(token) - 2) + 1):
        left = token[:split_at]
        right = token[split_at:]
        if len(right) < 2:
            continue
        if left not in english_words:
            continue
        if len(left) == 2 and left not in SHORT_WORDS:
            continue
        if len(right) <= 20 and right in english_words and not (len(right) == 2 and right not in SHORT_WORDS):
            memo[token] = True
            return True
        if len(right) > 20 and can_segment(right, english_words, memo):
            memo[token] = True
            return True
    memo[token] = False
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_PAGES)
    parser.add_argument("--content-metadata", type=Path, default=DEFAULT_CONTENT_METADATA)
    parser.add_argument("--max-examples", type=int, default=0)
    parser.add_argument("--long-word-threshold", type=int, default=20)
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    rows = load_rows(args.input)
    if not rows:
        print("FAIL: no rows")
        raise SystemExit(1)

    headers = load_headers(args.content_metadata)
    url_regex = re.compile(r"https?://|www\.", re.I)
    footnote_regex = re.compile(r"\[\d{1,3}(?:\s*,\s*\d{1,3})*\]")
    math_regex = re.compile(r"[\U0001D400-\U0001D7FF]")
    token_regex = re.compile(r"[A-Za-z0-9][A-Za-z0-9'/-]*")

    english_words: set[str] = set()
    for row in rows:
        clean_text = row.get("clean_text") or ""
        english_words.update(re.findall(r"[a-z]{2,20}", clean_text.lower()))

    hits: Dict[str, List[Dict[str, Any]]] = {
        "header_leak": [],
        "url_leak": [],
        "inline_footnote_ref": [],
        "math_glyph_leak": [],
        "long_word_merge_leak": [],
    }
    memo: Dict[str, bool] = {}

    for row in rows:
        page = row["page"]
        clean_text = row.get("clean_text") or ""
        stripped = clean_text.lstrip()
        for header in headers:
            if stripped.startswith(header):
                hits["header_leak"].append({"page": page, "match": header})
                break
        url_match = url_regex.search(clean_text)
        if url_match:
            hits["url_leak"].append({"page": page, "match": url_match.group(0)})
        footnote_match = footnote_regex.search(clean_text)
        if footnote_match:
            hits["inline_footnote_ref"].append({"page": page, "match": footnote_match.group(0)})
        math_match = math_regex.search(clean_text)
        if math_match:
            hits["math_glyph_leak"].append({"page": page, "match": math_match.group(0)})
        for token in token_regex.findall(clean_text):
            if len(token) <= args.long_word_threshold:
                continue
            normalized = token.strip().lower()
            if not re.fullmatch(r"[a-z]+", normalized):
                continue
            if normalized in english_words:
                continue
            if can_segment(normalized, english_words, memo):
                hits["long_word_merge_leak"].append({"page": page, "match": token})

    print(f"pages={len(rows)}")
    for metric in ("header_leak", "url_leak", "inline_footnote_ref", "math_glyph_leak"):
        pages = [hit["page"] for hit in hits[metric]]
        print(f"{metric}: {len(hits[metric])} {format_samples(pages)}")
        if args.verbose and args.max_examples > 0:
            for hit in hits[metric][: args.max_examples]:
                print(f"page={hit['page']} match={hit['match']!r}")
    merge_samples = [hit["match"] for hit in hits["long_word_merge_leak"]]
    print(f"long_word_merge_leak: {len(hits['long_word_merge_leak'])} (len>{args.long_word_threshold}) {format_samples(merge_samples)}")
    if args.verbose and args.max_examples > 0:
        for hit in hits["long_word_merge_leak"][: args.max_examples]:
            print(f"page={hit['page']} match={hit['match']!r}")

    total_violations = sum(len(value) for value in hits.values())
    if total_violations == 0:
        print("OK: cleanup quality checks passed")
        raise SystemExit(0)
    if args.report_only:
        print("WARN: cleanup quality violations found (report-only)")
        raise SystemExit(0)
    print("FAIL: cleanup quality violations found")
    raise SystemExit(1)


if __name__ == "__main__":
    main()

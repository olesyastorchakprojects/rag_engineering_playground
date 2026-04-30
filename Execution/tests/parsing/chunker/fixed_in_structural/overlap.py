#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import tempfile
import tomllib
from collections import Counter
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[4]
CHUNKER = REPO_ROOT / "Execution/parsing/chunker/fixed_in_structural/chunker.py"


def load_jsonl(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_config(path: Path):
    with path.open("rb") as f:
        return tomllib.load(f)


def split_sentences(text: str):
    text = " ".join((text or "").split())
    if not text:
        return []
    out = []
    cur = []
    for ch in text:
        cur.append(ch)
        if ch in ".!?":
            sentence = "".join(cur).strip()
            if sentence:
                out.append(sentence)
            cur = []
    tail = "".join(cur).strip()
    if tail:
        out.append(tail)
    return out


def longest_suffix_prefix_overlap(left_sentences, right_sentences):
    max_k = min(len(left_sentences), len(right_sentences))
    for k in range(max_k, 0, -1):
        if left_sentences[-k:] == right_sentences[:k]:
            return k
    return 0


def run_chunker(input_path: Path, config_path: Path, schema_path: Path, out_path: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            str(CHUNKER),
            "--chunks",
            str(input_path),
            "--config",
            str(config_path),
            "--chunk-schema",
            str(schema_path),
            "--out",
            str(out_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def same_parent(left: dict, right: dict) -> bool:
    return (
        left.get("doc_id") == right.get("doc_id")
        and list(left.get("section_path", []) or []) == list(right.get("section_path", []) or [])
        and left.get("page_start") == right.get("page_start")
        and left.get("page_end") == right.get("page_end")
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Overlap contract test for fixed_in_structural chunker")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--schema", type=Path, required=True)
    p.add_argument("--report-only", action="store_true")
    p.add_argument("--max-errors", type=int, default=20)
    args = p.parse_args()

    config = load_config(args.config)
    overlap_ratio = float(config["chunking"]["overlap_ratio"])

    with tempfile.TemporaryDirectory(prefix="chunk_fis_overlap_") as td:
        out_path = Path(td) / "out_chunks.jsonl"
        run_chunker(args.input, args.config, args.schema, out_path)
        chunks = load_jsonl(out_path)

    invalid = 0
    checked_pairs = 0
    violation_counts = Counter()
    examples = []
    observed_overlap_pairs = 0

    for idx in range(len(chunks) - 1):
        left = chunks[idx]
        right = chunks[idx + 1]
        if not same_parent(left, right):
            continue
        checked_pairs += 1

        left_text = str(left.get("text", "") or "")
        right_text = str(right.get("text", "") or "")
        if left_text == right_text:
            invalid += 1
            violation_counts["duplicate_chunk"] += 1
            if len(examples) < args.max_errors:
                examples.append((idx, idx + 1, "duplicate_chunk", "adjacent chunks have identical text"))
            continue

        left_sentences = split_sentences(left_text)
        right_sentences = split_sentences(right_text)
        overlap_count = longest_suffix_prefix_overlap(left_sentences, right_sentences)
        if overlap_count > 0:
            observed_overlap_pairs += 1

        left_set = set(left_sentences)
        right_set = set(right_sentences)
        sentence_intersection = left_set.intersection(right_set)

        if overlap_ratio <= 0.0:
            if overlap_count > 0:
                invalid += 1
                violation_counts["unexpected_overlap"] += 1
                if len(examples) < args.max_errors:
                    examples.append((idx, idx + 1, "unexpected_overlap", "overlap_ratio=0 but adjacent pair overlaps"))
            continue

        if overlap_count <= 0:
            invalid += 1
            violation_counts["missing_overlap"] += 1
            if len(examples) < args.max_errors:
                examples.append((idx, idx + 1, "missing_overlap", "overlap_ratio>0 but no suffix/prefix overlap found"))
            continue

        if sentence_intersection and overlap_count <= 0:
            invalid += 1
            violation_counts["non_prefix_overlap"] += 1
            if len(examples) < args.max_errors:
                examples.append((idx, idx + 1, "non_prefix_overlap", "shared sentences are not arranged as suffix/prefix"))

    if overlap_ratio > 0.0 and checked_pairs > 0 and observed_overlap_pairs == 0:
        invalid += 1
        violation_counts["no_observed_overlap"] += 1
        if len(examples) < args.max_errors:
            examples.append((-1, -1, "no_observed_overlap", "no same-parent adjacent pair exhibited overlap"))

    print(f"chunks={len(chunks)} checked_pairs={checked_pairs} invalid={invalid}")
    print(f"violation_counts={dict(sorted(violation_counts.items()))}")
    if examples:
        print("Overlap mismatch examples:")
        for left_idx, right_idx, kind, reason in examples:
            print(f"  pair=<{left_idx},{right_idx}> kind={kind} reason={reason}")

    if invalid > 0:
        if args.report_only:
            print("WARN: overlap validation failed (report-only)")
            return
        print("FAIL: overlap validation failed")
        sys.exit(1)

    print("OK: overlap contract is valid")


if __name__ == "__main__":
    main()

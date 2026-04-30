#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import tempfile
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


def inheritance_key(row: dict):
    return (
        row.get("doc_id"),
        tuple(row.get("section_path", []) or []),
        row.get("page_start"),
        row.get("page_end"),
        row.get("url"),
        row.get("document_title"),
        tuple(row.get("tags", []) or []),
    )


def parent_index(rows):
    return {inheritance_key(row): row for row in rows}


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


def main() -> None:
    p = argparse.ArgumentParser(description="Inheritance contract test for fixed_in_structural chunker")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--schema", type=Path, required=True)
    p.add_argument("--report-only", action="store_true")
    p.add_argument("--max-errors", type=int, default=20)
    args = p.parse_args()

    with tempfile.TemporaryDirectory(prefix="chunk_fis_inheritance_") as td:
        out_path = Path(td) / "out_chunks.jsonl"
        run_chunker(args.input, args.config, args.schema, out_path)
        parents = load_jsonl(args.input)
        children = load_jsonl(out_path)

    if not children:
        print(f"FAIL: no chunks in {out_path}")
        sys.exit(1)

    parents_by_key = parent_index(parents)
    invalid = 0
    violation_counts = Counter()
    examples = []

    for idx, child in enumerate(children, start=1):
        key = inheritance_key(child)
        parent = parents_by_key.get(key)
        if parent is None:
            invalid += 1
            violation_counts["unknown_parent_metadata"] += 1
            if len(examples) < args.max_errors:
                examples.append(
                    {
                        "row": str(idx),
                        "kind": "unknown_parent_metadata",
                        "reason": "child metadata tuple not found in input parents",
                    }
                )
            continue

        page_start = child.get("page_start")
        page_end = child.get("page_end")
        if isinstance(page_start, int) and isinstance(page_end, int) and page_end < page_start:
            invalid += 1
            violation_counts["invalid_page_range"] += 1
            if len(examples) < args.max_errors:
                examples.append(
                    {
                        "row": str(idx),
                        "kind": "invalid_page_range",
                        "reason": f"page_end {page_end} < page_start {page_start}",
                    }
                )

        parent_path = list(parent.get("section_path", []) or [])
        child_path = list(child.get("section_path", []) or [])
        if parent_path and not child_path:
            invalid += 1
            violation_counts["missing_section_path"] += 1
            if len(examples) < args.max_errors:
                examples.append(
                    {
                        "row": str(idx),
                        "kind": "missing_section_path",
                        "reason": "child section_path is empty while parent section_path is non-empty",
                    }
                )

        if child.get("doc_id") != parent.get("doc_id"):
            invalid += 1
            violation_counts["doc_id_mismatch"] += 1
            if len(examples) < args.max_errors:
                examples.append(
                    {
                        "row": str(idx),
                        "kind": "doc_id_mismatch",
                        "reason": "child doc_id differs from matched parent doc_id",
                    }
                )

    print(f"parents={len(parents)} children={len(children)} invalid={invalid}")
    print(f"violation_counts={dict(sorted(violation_counts.items()))}")
    if examples:
        print("Inheritance mismatch examples:")
        for example in examples:
            print(f"  row={example['row']} kind={example['kind']} reason={example['reason']}")

    if invalid > 0:
        if args.report_only:
            print("WARN: inheritance validation failed (report-only)")
            return
        print("FAIL: inheritance validation failed")
        sys.exit(1)

    print("OK: child chunks preserve parent metadata")


if __name__ == "__main__":
    main()

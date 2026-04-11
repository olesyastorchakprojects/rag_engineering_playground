#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[4]
CHUNKER = REPO_ROOT / "Execution/parsing/chunker/structural/chunker.py"


def load_jsonl(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def stable_projection(rows):
    key_fn = lambda x: int(x.get("chunk_index", 0))
    out = []
    for r in sorted(rows, key=key_fn):
        out.append(
            {
                "chunk_index": int(r.get("chunk_index", 0)),
                "page_start": int(r.get("page_start", 0)),
                "page_end": int(r.get("page_end", 0)),
                "section_path": list(r.get("section_path", []) or []),
                "text": (r.get("text", "") or "").strip(),
            }
        )
    return out


def run_once(pages: Path, metadata: Path, out_jsonl: Path):
    subprocess.run(
        [
            "python3",
            str(CHUNKER),
            "--pages",
            str(pages),
            "--metadata",
            str(metadata),
            "--out",
            str(out_jsonl),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Chunker determinism test (stable fields across repeated runs)")
    p.add_argument("--pages", type=Path, required=True)
    p.add_argument("--metadata", type=Path, required=True)
    p.add_argument("--report-only", action="store_true")
    p.add_argument("--max-errors", type=int, default=10)
    args = p.parse_args()

    if not args.pages.exists():
        print(f"FAIL: pages file not found: {args.pages}")
        sys.exit(1)
    if not args.metadata.exists():
        print(f"FAIL: metadata file not found: {args.metadata}")
        sys.exit(1)

    with tempfile.TemporaryDirectory(prefix="chunk_determinism_") as td:
        root = Path(td)
        out1 = root / "chunks_run1.jsonl"
        out2 = root / "chunks_run2.jsonl"

        run_once(args.pages, args.metadata, out1)
        run_once(args.pages, args.metadata, out2)

        a = stable_projection(load_jsonl(out1))
        b = stable_projection(load_jsonl(out2))

    if len(a) != len(b):
        print(f"FAIL: chunk count differs between runs: run1={len(a)} run2={len(b)}")
        sys.exit(1)

    mismatches = []
    field_mismatch_counts = {"chunk_index": 0, "page_start": 0, "page_end": 0, "section_path": 0, "text": 0}
    for i, (ra, rb) in enumerate(zip(a, b), start=1):
        if ra != rb:
            for k in field_mismatch_counts:
                if ra.get(k) != rb.get(k):
                    field_mismatch_counts[k] += 1
            mismatches.append((i, ra, rb))
            if len(mismatches) >= args.max_errors:
                break

    print(f"chunks={len(a)} mismatches={len(mismatches)}")
    if any(field_mismatch_counts.values()):
        print(f"field_mismatch_counts={field_mismatch_counts}")

    if mismatches:
        print("Determinism mismatch examples:")
        for i, ra, rb in mismatches[: args.max_errors]:
            print(f"  row={i} run1={ra}")
            print(f"         run2={rb}")
        if args.report_only:
            print("WARN: determinism test failed (report-only)")
            return
        print("FAIL: determinism test failed")
        sys.exit(1)

    print("OK: chunker output is deterministic for stable fields")


if __name__ == "__main__":
    main()

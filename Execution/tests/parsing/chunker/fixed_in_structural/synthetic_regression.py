#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[4]
DEFAULT_CASES = REPO_ROOT / "Execution/tests/fixtures/parsing/chunker/fixed_in_structural/synthetic_chunking_cases.json"
CHUNKER = REPO_ROOT / "Execution/parsing/chunker/fixed_in_structural/chunker.py"
CHUNK_SCHEMA = REPO_ROOT / "Execution/schemas/chunk.schema.json"


def load_cases(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_toml(path: Path, payload: dict):
    lines = []
    for section, values in payload.items():
        lines.append(f"[{section}]")
        for key, value in values.items():
            if isinstance(value, str):
                lines.append(f'{key} = "{value}"')
            elif isinstance(value, bool):
                lines.append(f"{key} = {'true' if value else 'false'}")
            else:
                lines.append(f"{key} = {value}")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def load_jsonl(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def normalize_page_ranges(rows):
    return [[int(r.get("page_start", 0)), int(r.get("page_end", 0))] for r in rows]


def normalize_section_paths(rows):
    return [list(r.get("section_path", []) or []) for r in rows]


def run_case(case: dict, verbose: bool = False):
    name = case["name"]
    with tempfile.TemporaryDirectory(prefix=f"chunk_fis_{name}_") as td:
        tdp = Path(td)
        input_chunks_path = tdp / "input_chunks.jsonl"
        config_path = tdp / "chunker.toml"
        out_chunks_path = tdp / "out_chunks.jsonl"

        write_jsonl(input_chunks_path, case.get("chunks", []))
        write_toml(config_path, case["config"])

        proc = subprocess.run(
            [
                sys.executable,
                str(CHUNKER),
                "--chunks",
                str(input_chunks_path),
                "--config",
                str(config_path),
                "--chunk-schema",
                str(CHUNK_SCHEMA),
                "--out",
                str(out_chunks_path),
            ],
            capture_output=not verbose,
            text=True,
        )

        errs = []
        expected_fail = bool(case.get("expected_fail", False))
        if expected_fail:
            if proc.returncode == 0:
                errs.append("expected failure but chunker succeeded")
            return errs

        if proc.returncode != 0:
            errs.append(f"unexpected failure: returncode={proc.returncode}")
            stderr = (proc.stderr or "").strip()
            if stderr:
                errs.append(f"stderr: {stderr}")
            return errs

        rows = load_jsonl(out_chunks_path)

        expected_count = case.get("expected_chunk_count")
        if expected_count is not None and len(rows) != int(expected_count):
            errs.append(f"unexpected chunk count: expected={expected_count} actual={len(rows)}")

        expected_doc_ids = case.get("expected_doc_ids") or []
        actual_doc_ids = [row.get("doc_id") for row in rows]
        if expected_doc_ids and actual_doc_ids != expected_doc_ids:
            errs.append(f"unexpected doc_id sequence: expected={expected_doc_ids!r} actual={actual_doc_ids!r}")

        expected_page_ranges = case.get("expected_page_ranges") or []
        actual_page_ranges = normalize_page_ranges(rows)
        if expected_page_ranges and actual_page_ranges != expected_page_ranges:
            errs.append(
                f"unexpected page ranges: expected={expected_page_ranges!r} actual={actual_page_ranges!r}"
            )

        expected_section_paths = case.get("expected_section_paths") or []
        actual_section_paths = normalize_section_paths(rows)
        if expected_section_paths and actual_section_paths != expected_section_paths:
            errs.append(
                f"unexpected section paths: expected={expected_section_paths!r} actual={actual_section_paths!r}"
            )

        expected_text_contains = case.get("expected_text_contains") or []
        for anchor in expected_text_contains:
            if not any(anchor in (row.get("text", "") or "") for row in rows):
                errs.append(f"missing expected text anchor: {anchor!r}")

        forbidden_pairs = case.get("forbid_cross_parent_text_pairs") or []
        for pair in forbidden_pairs:
            left = pair["left_anchor"]
            right = pair["right_anchor"]
            if any(left in (row.get("text", "") or "") and right in (row.get("text", "") or "") for row in rows):
                errs.append(f"forbidden text merge detected: left={left!r} right={right!r}")

        return errs


def main() -> None:
    p = argparse.ArgumentParser(description="Synthetic regression tests for fixed_in_structural chunker")
    p.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    p.add_argument("--report-only", action="store_true")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    cases = load_cases(args.cases)
    total = len(cases)
    failed = 0
    for i, case in enumerate(cases, start=1):
        name = case.get("name", f"case_{i}")
        errs = run_case(case, verbose=args.verbose)
        if errs:
            failed += 1
            print(f"[FAIL] {name}")
            for err in errs:
                print(f"  - {err}")
        else:
            print(f"[OK]   {name}")

    print(f"cases={total} failed={failed}")
    if failed > 0 and not args.report_only:
        raise SystemExit("FAIL: synthetic regression failed")
    if failed > 0 and args.report_only:
        print("WARN: synthetic regression failed (report-only)")
        return
    print("OK: all synthetic regression cases passed")


if __name__ == "__main__":
    main()

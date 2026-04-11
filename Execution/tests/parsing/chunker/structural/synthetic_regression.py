#!/usr/bin/env python3
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[4]
DEFAULT_CASES = REPO_ROOT / "Execution/tests/fixtures/parsing/chunker/structural/synthetic_chunking_cases.json"
CHUNKER = REPO_ROOT / "Execution/parsing/chunker/structural/chunker.py"


def load_cases(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_pages_jsonl(path: Path, pages):
    with path.open("w", encoding="utf-8") as f:
        for p in pages:
            rec = {
                "page": int(p["page"]),
                "clean_text": p.get("clean_text", ""),
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def write_metadata_json(path: Path, metadata: dict):
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_chunks(path: Path):
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def normalize_path_value(value):
    if isinstance(value, list):
        return [str(part).strip() for part in value if str(part).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split("/") if part.strip()]
    return []


def run_case(case: dict, verbose: bool = False):
    name = case["name"]
    with tempfile.TemporaryDirectory(prefix=f"chunk_synth_{name}_") as td:
        tdp = Path(td)
        pages_path = tdp / "pages.jsonl"
        metadata_path = tdp / "metadata.json"
        chunks_path = tdp / "chunks.jsonl"

        write_pages_jsonl(pages_path, case.get("pages", []))
        write_metadata_json(metadata_path, case["metadata"])

        subprocess.run(
            [
                "python3",
                str(CHUNKER),
                "--pages",
                str(pages_path),
                "--metadata",
                str(metadata_path),
                "--out",
                str(chunks_path),
            ],
            check=True,
            capture_output=not verbose,
            text=True,
        )

        chunks = load_chunks(chunks_path)
        errs = []
        expected_paths = case.get("expected_paths") or []
        actual_paths = [normalize_path_value(c.get("section_path", [])) for c in chunks]
        expected_paths = [normalize_path_value(path) for path in expected_paths]
        if expected_paths and actual_paths != expected_paths:
            errs.append(f"unexpected path sequence: expected={expected_paths!r} actual={actual_paths!r}")

        expected_count = case.get("expected_chunk_count")
        if expected_count is not None and len(chunks) != int(expected_count):
            errs.append(f"unexpected chunk count: expected={expected_count} actual={len(chunks)}")

        forbidden_paths = {tuple(normalize_path_value(path)) for path in (case.get("forbidden_paths") or [])}
        for forbidden in forbidden_paths:
            if list(forbidden) in actual_paths:
                errs.append(f"forbidden path emitted: {list(forbidden)!r}")

        by_path = {}
        for chunk in chunks:
            by_path.setdefault(tuple(normalize_path_value(chunk.get("section_path", []))), []).append(chunk)

        for exp in case.get("checks", []):
            path = tuple(normalize_path_value(exp["section_path"]))
            a1 = exp.get("first_anchor", "")
            a2 = exp.get("last_anchor", "")
            candidates = by_path.get(path) or []
            if not candidates:
                errs.append(f"missing chunk for section_path: {list(path)!r}")
                continue
            target = None
            for candidate in candidates:
                text = candidate.get("text", "") or ""
                if (not a1 or a1 in text) and (not a2 or a2 in text):
                    target = candidate
                    break
            if target is None:
                errs.append(f"no chunk instance for {list(path)!r} matches requested anchors")
            continue
        return errs


def main() -> None:
    p = argparse.ArgumentParser(description="Synthetic chunking tests with controlled pages_clean inputs")
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
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"[OK]   {name}")

    print(f"cases={total} failed={failed}")
    if failed > 0 and not args.report_only:
        raise SystemExit("FAIL: synthetic chunking tests failed")
    if failed > 0 and args.report_only:
        print("WARN: synthetic chunking regressions (report-only)")
        return
    print("OK: synthetic chunking tests passed")


if __name__ == "__main__":
    main()

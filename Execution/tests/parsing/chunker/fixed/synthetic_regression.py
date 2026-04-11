#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[4]
DEFAULT_CASES = REPO_ROOT / "Execution/tests/fixtures/parsing/chunker/fixed/synthetic_chunking_cases.json"
CHUNKER = REPO_ROOT / "Execution/parsing/chunker/fixed/chunker.py"


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


def write_json(path: Path, payload: dict):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def load_chunks(path: Path):
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def with_book_metadata_defaults(payload: dict) -> dict:
    data = dict(payload)
    if "source_pdf" not in data:
        data["source_pdf"] = "synthetic.pdf"
    book = dict(data.get("book") or {})
    book.setdefault("title", data.get("document_title", "Synthetic Fixed Chunker Book"))
    book.setdefault("edition", "Synthetic")
    book.setdefault("version", "1.0.0")
    book.setdefault("author", "OpenAI")
    book.setdefault("date", "2026-04-01")
    data["book"] = book
    return data


def normalize_path_value(value):
    if isinstance(value, list):
        return [str(part).strip() for part in value if str(part).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split("/") if part.strip()]
    return []


def normalize_page_ranges(chunks):
    return [[int(c.get("page_start", 0)), int(c.get("page_end", 0))] for c in chunks]


def run_case(case: dict, verbose: bool = False):
    name = case["name"]
    with tempfile.TemporaryDirectory(prefix=f"fixed_chunk_synth_{name}_") as td:
        tdp = Path(td)
        pages_path = tdp / "pages.jsonl"
        book_metadata_path = tdp / "book_metadata.json"
        content_metadata_path = tdp / "content_metadata.json"
        config_path = tdp / "chunker.toml"
        chunks_path = tdp / "chunks.jsonl"

        write_pages_jsonl(pages_path, case.get("pages", []))
        write_json(book_metadata_path, with_book_metadata_defaults(case["book_metadata"]))
        write_json(content_metadata_path, case["content_metadata"])
        write_toml(config_path, case["config"])

        proc = subprocess.run(
            [
                sys.executable,
                str(CHUNKER),
                "--pages",
                str(pages_path),
                "--book-metadata",
                str(book_metadata_path),
                "--content-metadata",
                str(content_metadata_path),
                "--config",
                str(config_path),
                "--out",
                str(chunks_path),
            ],
            capture_output=not verbose,
            text=True,
        )

        errs = []
        expected_fail = bool(case.get("expected_fail", False))
        if expected_fail:
            if proc.returncode == 0:
                errs.append("expected failure, but chunker exited successfully")
            return errs

        if proc.returncode != 0:
            errs.append(f"chunker exited with code {proc.returncode}")
            if proc.stderr:
                errs.append(f"stderr: {proc.stderr.strip()}")
            return errs

        chunks = load_chunks(chunks_path)

        expected_count = case.get("expected_chunk_count")
        if expected_count is not None and len(chunks) != int(expected_count):
            errs.append(f"unexpected chunk count: expected={expected_count} actual={len(chunks)}")

        expected_page_ranges = case.get("expected_page_ranges") or []
        actual_page_ranges = normalize_page_ranges(chunks)
        if expected_page_ranges and actual_page_ranges != expected_page_ranges:
            errs.append(
                f"unexpected page ranges: expected={expected_page_ranges!r} actual={actual_page_ranges!r}"
            )

        expected_paths = [normalize_path_value(path) for path in (case.get("expected_section_paths") or [])]
        actual_paths = [normalize_path_value(c.get("section_path", [])) for c in chunks]
        if expected_paths and actual_paths != expected_paths:
            errs.append(f"unexpected section paths: expected={expected_paths!r} actual={actual_paths!r}")

        checks = case.get("expected_text_contains") or []
        for i, exp in enumerate(checks):
            if i >= len(chunks):
                errs.append(f"missing chunk for expected_text_contains index={i}")
                continue
            text = chunks[i].get("text", "") or ""
            for anchor in exp:
                if anchor not in text:
                    errs.append(f"chunk {i} missing anchor: {anchor!r}")

        expected_text_equals = case.get("expected_text_equals") or []
        for i, exp_text in enumerate(expected_text_equals):
            if i >= len(chunks):
                errs.append(f"missing chunk for expected_text_equals index={i}")
                continue
            actual_text = chunks[i].get("text", "") or ""
            if actual_text != exp_text:
                errs.append(
                    f"unexpected chunk text at index={i}: expected={exp_text!r} actual={actual_text!r}"
                )

        forbidden_text = case.get("forbidden_text_contains") or []
        for forbidden in forbidden_text:
            if any(forbidden in (chunk.get("text", "") or "") for chunk in chunks):
                errs.append(f"forbidden text emitted: {forbidden!r}")

        expected_pairwise_overlap_contains = case.get("expected_pairwise_overlap_contains") or []
        for exp in expected_pairwise_overlap_contains:
            left = int(exp["left_chunk"])
            right = int(exp["right_chunk"])
            anchors = exp.get("anchors") or []
            if left >= len(chunks) or right >= len(chunks):
                errs.append(
                    f"invalid overlap check pair: left={left} right={right} chunk_count={len(chunks)}"
                )
                continue
            left_text = chunks[left].get("text", "") or ""
            right_text = chunks[right].get("text", "") or ""
            for anchor in anchors:
                if anchor not in left_text or anchor not in right_text:
                    errs.append(
                        f"expected pairwise overlap anchor missing for chunks ({left}, {right}): {anchor!r}"
                    )

        expected_pairwise_no_overlap_contains = case.get("expected_pairwise_no_overlap_contains") or []
        for exp in expected_pairwise_no_overlap_contains:
            left = int(exp["left_chunk"])
            right = int(exp["right_chunk"])
            anchors = exp.get("anchors") or []
            if left >= len(chunks) or right >= len(chunks):
                errs.append(
                    f"invalid no-overlap check pair: left={left} right={right} chunk_count={len(chunks)}"
                )
                continue
            left_text = chunks[left].get("text", "") or ""
            right_text = chunks[right].get("text", "") or ""
            for anchor in anchors:
                if anchor in left_text and anchor in right_text:
                    errs.append(
                        f"unexpected pairwise overlap anchor present in chunks ({left}, {right}): {anchor!r}"
                    )

        return errs


def main() -> None:
    p = argparse.ArgumentParser(description="Synthetic regression tests for fixed chunker")
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
        raise SystemExit("FAIL: synthetic regression failed")
    if failed > 0 and args.report_only:
        print("WARN: synthetic regression failed (report-only)")
        return
    print("OK: all synthetic regression cases passed")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import argparse
import json
import sys
import tempfile
from pathlib import Path


THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))
import _hybrid_testlib as lib  # noqa: E402


def run_case(case: dict):
    with tempfile.TemporaryDirectory() as tmp_dir_str:
        chunks_path = Path(tmp_dir_str) / "chunks.jsonl"
        chunks_path.write_text(case["content"], encoding="utf-8")
        try:
            lines = []
            for raw_line in chunks_path.read_text(encoding="utf-8").splitlines():
                stripped = raw_line.strip()
                if stripped:
                    lines.append(json.loads(stripped))
            if case["expect"] == "fail" and len(lines) == 0:
                raise ValueError("no chunks in input")
            for chunk in lines:
                lib.validate_chunk_contract(chunk)
                if case.get("vocabulary") is not None:
                    vector = lib.build_bow_sparse_vector(case["config"], chunk["text"], case["vocabulary"])
                    if chunk["text"].strip() and len(vector["indices"]) == 0:
                        raise ValueError("empty sparse vector after normalization and vocabulary lookup")
            if case["expect"] == "pass":
                return True, {"error": ""}
            return False, {"error": "expected failure but case passed"}
        except Exception as exc:
            if case["expect"] == "fail":
                return True, {"error": str(exc)}
            return False, {"error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunk-schema", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if not args.chunk_schema.exists():
        raise SystemExit(f"chunk schema file not found path={args.chunk_schema}")

    config = lib.load_toml(args.config)
    valid_chunk = lib.build_valid_chunk()
    vocabulary = lib.build_vocabulary_artifact(config, [lib.build_valid_chunk(text="known token alpha beta")])

    cases = [
        {"name": "valid_chunk_jsonl", "content": json.dumps(valid_chunk) + "\n", "expect": "pass"},
        {"name": "empty_input", "content": "", "expect": "fail"},
        {"name": "invalid_jsonl", "content": '{"broken":\n', "expect": "fail"},
        {
            "name": "schema_mismatch_missing_text",
            "content": json.dumps({k: v for k, v in valid_chunk.items() if k != "text"}) + "\n",
            "expect": "fail",
        },
        {
            "name": "page_end_before_page_start",
            "content": json.dumps({**valid_chunk, "page_end": valid_chunk["page_start"] - 1}) + "\n",
            "expect": "fail",
        },
        {
            "name": "non_empty_text_becomes_empty_sparse_vector",
            "content": json.dumps({**valid_chunk, "text": "zzz yyy qqq"}) + "\n",
            "expect": "fail",
            "config": config,
            "vocabulary": vocabulary,
        },
    ]

    failed = 0
    passed = 0
    for case in cases:
        ok, details = run_case(case)
        if ok:
            passed += 1
            print(f"OK [{case['name']}]")
        else:
            failed += 1
            print(f"FAIL [{case['name']}]")
            print(f"error={details['error']}")
    print(f"cases={len(cases)} failed={failed} passed={passed}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

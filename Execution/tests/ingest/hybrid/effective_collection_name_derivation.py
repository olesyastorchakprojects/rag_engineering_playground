#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path


THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))
import _hybrid_testlib as lib  # noqa: E402


def run_case(name: str, fn, expect_error: bool = False):
    try:
        result = fn()
        if expect_error:
            return False, {"error": f"expected error but got {result}"}
        return True, {"result": result}
    except Exception as exc:
        if expect_error:
            return True, {"error": str(exc)}
        return False, {"error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    _ = args

    cases = [
        ("bag_of_words_suffix", lambda: lib.derive_effective_collection_name("chunks_hybrid_qwen3", "bag_of_words"), False, "chunks_hybrid_qwen3_bow"),
        ("bm25_like_suffix", lambda: lib.derive_effective_collection_name("chunks_hybrid_qwen3", "bm25_like"), False, "chunks_hybrid_qwen3_bm25"),
        ("invalid_base_name_bow", lambda: lib.derive_effective_collection_name("chunks_hybrid_bow", "bag_of_words"), True, None),
        ("invalid_base_name_bm25", lambda: lib.derive_effective_collection_name("chunks_hybrid_bm25", "bm25_like"), True, None),
        ("invalid_base_name_trailing_underscore", lambda: lib.derive_effective_collection_name("chunks_hybrid_", "bag_of_words"), True, None),
    ]

    failed = 0
    passed = 0
    for name, fn, expect_error, expected in cases:
        ok, details = run_case(name, fn, expect_error)
        if ok and not expect_error and details["result"] != expected:
            ok = False
            details = {"error": f"expected {expected} got {details['result']}"}
        if ok:
            passed += 1
            print(f"OK [{name}]")
        else:
            failed += 1
            print(f"FAIL [{name}]")
            print(f"error={details['error']}")
    print(f"cases={len(cases)} failed={failed} passed={passed}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

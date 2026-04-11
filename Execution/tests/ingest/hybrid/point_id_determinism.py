#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path


THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))
import _hybrid_testlib as lib  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    config = lib.load_toml(args.config)
    first = lib.build_valid_chunk(chunk_id="11111111-1111-1111-1111-111111111111")
    second = lib.build_valid_chunk(chunk_id="11111111-1111-1111-1111-111111111111")
    third = lib.build_valid_chunk(chunk_id="22222222-2222-2222-2222-222222222222")

    cases = [
        ("same_chunk_id_same_point_id", lib.compute_point_id(config, first) == lib.compute_point_id(config, second)),
        ("different_chunk_id_different_point_id", lib.compute_point_id(config, first) != lib.compute_point_id(config, third)),
    ]
    failed = 0
    passed = 0
    for name, ok in cases:
        if ok:
            passed += 1
            print(f"OK [{name}]")
        else:
            failed += 1
            print(f"FAIL [{name}]")
            print("error=point id determinism contract violated")
    print(f"cases={len(cases)} failed={failed} passed={passed}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

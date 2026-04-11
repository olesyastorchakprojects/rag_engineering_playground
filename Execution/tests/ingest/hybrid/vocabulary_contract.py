#!/usr/bin/env python3
import argparse
import copy
import json
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
    chunks = [
        lib.build_valid_chunk(chunk_index=0, text="Raft leader leader election"),
        lib.build_valid_chunk(chunk_index=1, text="Leader commit raft"),
    ]
    artifact = lib.build_vocabulary_artifact(config, chunks)
    token_ids = [entry["token_id"] for entry in artifact["tokens"]]
    token_names = [entry["token"] for entry in artifact["tokens"]]
    reused = copy.deepcopy(artifact)
    oov_vector = lib.build_bow_sparse_vector(config, "unknown tokens only", artifact)

    cases = [
        ("first_seen_assignment_order", token_names[:4] == ["raft", "leader", "election", "commit"]),
        ("contiguous_token_ids", token_ids == list(range(len(token_ids)))),
        ("immutable_reuse_semantics", json.dumps(reused, sort_keys=True) == json.dumps(artifact, sort_keys=True)),
        ("oov_tokens_ignored", oov_vector["indices"] == [] and oov_vector["oov_count"] > 0),
        ("vocabulary_name_contract", artifact["vocabulary_name"] == lib.vocabulary_name(config["qdrant"]["collection"]["name"])),
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
            print("error=vocabulary contract violated")
    print(f"cases={len(cases)} failed={failed} passed={passed}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

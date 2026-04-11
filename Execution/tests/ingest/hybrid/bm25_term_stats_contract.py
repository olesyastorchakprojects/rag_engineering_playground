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
    config["sparse"]["strategy"]["kind"] = "bm25_like"
    config["sparse"].pop("bag_of_words", None)
    config["sparse"]["bm25_like"] = {
        "document": "bm25_document_weight",
        "query": "bm25_query_weight",
        "k1": 1.2,
        "b": 0.75,
        "idf_smoothing": "default",
    }
    chunks = [
        lib.build_valid_chunk(chunk_index=0, text="raft leader election"),
        lib.build_valid_chunk(chunk_index=1, text="leader commit index"),
    ]
    vocabulary = lib.build_vocabulary_artifact(config, chunks)
    stats = lib.build_term_stats_artifact(config, vocabulary, chunks)
    effective_name = lib.derive_effective_collection_name(config["qdrant"]["collection"]["name"], "bm25_like")

    cases = [
        ("required_fields_present", all(key in stats for key in ["collection_name", "sparse_strategy", "vocabulary_name", "document_count", "average_document_length", "document_frequency_by_token_id", "created_at"])),
        ("collection_name_derived", stats["collection_name"] == effective_name),
        ("vocabulary_name_matches_shared_vocabulary", stats["vocabulary_name"] == vocabulary["vocabulary_name"]),
        ("basename_rule", lib.term_stats_basename(effective_name) == f"{effective_name}__term_stats.json"),
        ("document_count_positive", stats["document_count"] > 0 and stats["average_document_length"] > 0),
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
            print("error=bm25 term-stats contract violated")
    print(f"cases={len(cases)} failed={failed} passed={passed}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

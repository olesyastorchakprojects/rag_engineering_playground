#!/usr/bin/env python3
import argparse
import json
import sys
import tempfile
import uuid
from pathlib import Path


THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))
import _hybrid_testlib as lib  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=Path, required=True, dest="script_path")
    parser.add_argument("--chunk-schema", type=Path, required=True, dest="chunk_schema_path")
    parser.add_argument("--config", type=Path, required=True, dest="config_path")
    parser.add_argument("--env-file", type=Path, required=True, dest="env_file_path")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    _ = args.chunk_schema_path

    base_config = lib.load_toml(args.config_path)
    unique_base = f"{base_config['qdrant']['collection']['name']}_bm25_{uuid.uuid4().hex[:10]}"
    mutated = json.loads(json.dumps(base_config))
    mutated["qdrant"]["collection"]["name"] = unique_base
    mutated["sparse"]["strategy"]["kind"] = "bm25_like"
    mutated["sparse"].pop("bag_of_words", None)
    effective_name = lib.derive_effective_collection_name(unique_base, "bm25_like")
    cleanup_error = None
    env = lib.parse_env_file(args.env_file_path)

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        config_path = tmp_dir / "config.toml"
        chunks_path = tmp_dir / "chunks.jsonl"
        vocabulary_path = lib.vocabulary_artifact_path(unique_base)
        term_stats_path = lib.term_stats_artifact_path(effective_name)
        manifest_path = lib.manifest_artifact_path("2026-04-02T00-00-00Z_00000000-0000-0000-0000-000000000000")
        mutated["artifacts"]["manifest_path"] = lib.repo_root_relative_str(manifest_path)
        mutated["sparse"]["bm25_like"] = {
            "document": "bm25_document_weight",
            "query": "bm25_query_weight",
            "k1": 1.2,
            "b": 0.75,
            "idf_smoothing": "default",
        }
        lib.write_text(config_path, lib.dump_toml_document(mutated))
        lib.write_chunks_jsonl(chunks_path, [lib.build_valid_chunk(text="raft leader election"), lib.build_valid_chunk(chunk_index=1, text="leader commit index")])
        first = lib.run_ingest_subprocess(args.script_path, chunks_path, config_path, args.env_file_path)
        first_bytes = term_stats_path.read_bytes() if term_stats_path.exists() else b""
        second = lib.run_ingest_subprocess(args.script_path, chunks_path, config_path, args.env_file_path)
        second_bytes = term_stats_path.read_bytes() if term_stats_path.exists() else b""
        try:
            delete_status, delete_body, _ = lib.delete_collection(env["QDRANT_URL"], effective_name)
            if delete_status < 200 or delete_status >= 300:
                cleanup_error = f"http_status={delete_status} body={delete_body}"
        except Exception as exc:
            cleanup_error = str(exc)
        finally:
            lib.cleanup_artifact_file(term_stats_path)
            lib.cleanup_artifact_file(vocabulary_path)
            lib.cleanup_artifact_file(manifest_path)

    ok = first.returncode == 0 and second.returncode == 0 and first_bytes != b"" and first_bytes == second_bytes and term_stats_path.name == lib.term_stats_basename(effective_name) and cleanup_error is None
    if ok:
        print("OK [bm25_term_stats_roundtrip]")
        print("cases=1 failed=0 passed=1")
        return
    print("FAIL [bm25_term_stats_roundtrip]")
    print("error=bm25 term-stats roundtrip assertions failed")
    print(f"first_stdout={first.stdout.strip()}")
    print(f"second_stdout={second.stdout.strip()}")
    print(f"cleanup_error={cleanup_error}")
    print("cases=1 failed=1 passed=0")
    raise SystemExit(1)


if __name__ == "__main__":
    main()

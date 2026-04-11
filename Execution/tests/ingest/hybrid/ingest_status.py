#!/usr/bin/env python3
import argparse
import json
import sys
import tempfile
import time
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

    config = lib.load_toml(args.config_path)
    env = lib.parse_env_file(args.env_file_path)
    lib.check_qdrant_available(env["QDRANT_URL"])
    lib.check_embedding_available(env["OLLAMA_URL"], config["embedding"]["model"]["name"])

    unique_base = f"{config['qdrant']['collection']['name']}_status_{uuid.uuid4().hex[:10]}"
    effective_name = lib.derive_effective_collection_name(unique_base, config["sparse"]["strategy"]["kind"])
    cleanup_error = None
    update_chunk = lib.build_valid_chunk(chunk_index=0, text="update text")
    skip_log_chunk = lib.build_valid_chunk(chunk_index=1, text="skip log text")
    skip_chunk = lib.build_valid_chunk(chunk_index=2, text="skip text")
    insert_chunk = lib.build_valid_chunk(chunk_index=3, text="insert text")
    update_chunk_second = json.loads(json.dumps(update_chunk))
    update_chunk_second["section_title"] = "Updated Section Title"
    update_chunk_second["section_path"] = ["Introduction", "Updated Section Title"]
    skip_log_chunk_second = json.loads(json.dumps(skip_log_chunk))
    skip_log_chunk_second["content_hash"] = "sha256:skip-log-changed"
    skip_log_chunk_second["text"] = "skip log changed text"

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        config_path = tmp_dir / "config.toml"
        first_chunks = tmp_dir / "first.jsonl"
        second_chunks = tmp_dir / "second.jsonl"
        skipped_log = lib.log_artifact_path(f"{unique_base}_skipped.jsonl")
        failed_log = lib.log_artifact_path(f"{unique_base}_failed.jsonl")
        vocabulary_path = lib.vocabulary_artifact_path(unique_base)
        manifest_path = lib.manifest_artifact_path("2026-04-02T00-00-00Z_00000000-0000-0000-0000-000000000000")
        mutated = json.loads(json.dumps(config))
        mutated["qdrant"]["collection"]["name"] = unique_base
        mutated["artifacts"]["manifest_path"] = lib.repo_root_relative_str(manifest_path)
        mutated["logging"]["failed_chunk_log_path"] = lib.repo_root_relative_str(failed_log)
        mutated["logging"]["skipped_chunk_log_path"] = lib.repo_root_relative_str(skipped_log)
        lib.write_text(config_path, lib.dump_toml_document(mutated))
        lib.write_chunks_jsonl(first_chunks, [update_chunk, skip_log_chunk, skip_chunk])
        lib.write_chunks_jsonl(second_chunks, [update_chunk_second, skip_log_chunk_second, skip_chunk, insert_chunk])

        first = lib.run_ingest_subprocess(args.script_path, first_chunks, config_path, args.env_file_path)
        time.sleep(1.0)
        second = lib.run_ingest_subprocess(args.script_path, second_chunks, config_path, args.env_file_path)
        collection_status, _, collection_json = lib.get_collection(env["QDRANT_URL"], effective_name)
        skipped_entries = lib.read_jsonl_lines(skipped_log)
        try:
            delete_status, delete_body, _ = lib.delete_collection(env["QDRANT_URL"], effective_name)
            if delete_status < 200 or delete_status >= 300:
                cleanup_error = f"http_status={delete_status} body={delete_body}"
        except Exception as exc:
            cleanup_error = str(exc)
        finally:
            lib.cleanup_artifact_file(skipped_log)
            lib.cleanup_artifact_file(failed_log)
            lib.cleanup_artifact_file(vocabulary_path)
            lib.cleanup_artifact_file(manifest_path)

    points_count = lib.extract_hybrid_collection_fields(collection_json)["points_count"]
    second_stdout = second.stdout.strip()
    ok = (
        first.returncode == 0
        and second.returncode == 0
        and collection_status == 200
        and points_count == 4
        and "updated=1" in second_stdout
        and "created=1" in second_stdout
        and "unchanged=1" in second_stdout
        and "skipped=1" in second_stdout
        and "skip_and_log=1" in second_stdout
        and len(skipped_entries) >= 1
        and cleanup_error is None
    )
    if ok:
        print("OK [ingest_status]")
        print("cases=1 failed=0 passed=1")
        return
    print("FAIL [ingest_status]")
    print("error=ingest status assertions failed")
    print(f"first_stdout={first.stdout.strip()}")
    print(f"second_stdout={second.stdout.strip()}")
    print(f"cleanup_error={cleanup_error}")
    print("cases=1 failed=1 passed=0")
    raise SystemExit(1)


if __name__ == "__main__":
    main()

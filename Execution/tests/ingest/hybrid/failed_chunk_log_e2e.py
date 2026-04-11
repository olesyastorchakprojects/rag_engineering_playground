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

    config = lib.load_toml(args.config_path)
    env = lib.parse_env_file(args.env_file_path)
    lib.check_qdrant_available(env["QDRANT_URL"])
    lib.check_embedding_available(env["OLLAMA_URL"], config["embedding"]["model"]["name"])

    unique_base = f"{config['qdrant']['collection']['name']}_failed_{uuid.uuid4().hex[:10]}"
    effective_name = lib.derive_effective_collection_name(unique_base, config["sparse"]["strategy"]["kind"])
    cleanup_error = None
    chunk = lib.build_valid_chunk(text="raft leader election")

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        config_path = tmp_dir / "config.toml"
        chunks_path = tmp_dir / "chunks.jsonl"
        failed_log = lib.log_artifact_path(f"{unique_base}_failed.jsonl")
        skipped_log = lib.log_artifact_path(f"{unique_base}_skipped.jsonl")
        vocabulary_path = lib.vocabulary_artifact_path(unique_base)
        manifest_path = lib.manifest_artifact_path("2026-04-02T00-00-00Z_00000000-0000-0000-0000-000000000000")
        mutated = json.loads(json.dumps(config))
        mutated["qdrant"]["collection"]["name"] = unique_base
        mutated["artifacts"]["manifest_path"] = lib.repo_root_relative_str(manifest_path)
        mutated["logging"]["failed_chunk_log_path"] = lib.repo_root_relative_str(failed_log)
        mutated["logging"]["skipped_chunk_log_path"] = lib.repo_root_relative_str(skipped_log)
        lib.write_text(config_path, lib.dump_toml_document(mutated))
        lib.write_chunks_jsonl(chunks_path, [chunk])

        first = lib.run_ingest_subprocess(args.script_path, chunks_path, config_path, args.env_file_path)
        point_id = lib.compute_point_id(mutated, chunk)
        _, _, point_json = lib.retrieve_points(env["QDRANT_URL"], effective_name, [point_id])
        point = lib.extract_retrieved_point(point_json) or {}
        if isinstance(point.get("payload"), dict):
            bad_payload = dict(point["payload"])
            bad_payload.pop("content_hash", None)
            quoted = effective_name
            lib.send_json_request(
                "PUT",
                env["QDRANT_URL"].rstrip("/") + f"/collections/{quoted}/points/payload",
                {"payload": bad_payload, "points": [point_id]},
            )
        second = lib.run_ingest_subprocess(args.script_path, chunks_path, config_path, args.env_file_path)
        failed_entries = lib.read_jsonl_lines(failed_log)
        try:
            delete_status, delete_body, _ = lib.delete_collection(env["QDRANT_URL"], effective_name)
            if delete_status < 200 or delete_status >= 300:
                cleanup_error = f"http_status={delete_status} body={delete_body}"
        except Exception as exc:
            cleanup_error = str(exc)
        finally:
            lib.cleanup_artifact_file(failed_log)
            lib.cleanup_artifact_file(skipped_log)
            lib.cleanup_artifact_file(vocabulary_path)
            lib.cleanup_artifact_file(manifest_path)

    ok = (
        first.returncode == 0
        and second.returncode == 1
        and "failed=1" in second.stdout
        and len(failed_entries) >= 1
        and cleanup_error is None
    )
    if ok:
        print("OK [failed_chunk_log_e2e]")
        print("cases=1 failed=0 passed=1")
        return
    print("FAIL [failed_chunk_log_e2e]")
    print("error=failed chunk log assertions failed")
    print(f"first_stdout={first.stdout.strip()}")
    print(f"second_stdout={second.stdout.strip()}")
    print(f"cleanup_error={cleanup_error}")
    print("cases=1 failed=1 passed=0")
    raise SystemExit(1)


if __name__ == "__main__":
    main()

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

    unique_base = f"{config['qdrant']['collection']['name']}_meta_{uuid.uuid4().hex[:10]}"
    effective_name = lib.derive_effective_collection_name(unique_base, config["sparse"]["strategy"]["kind"])
    cleanup_error = None

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        config_path = tmp_dir / "config.toml"
        chunks_path = tmp_dir / "chunks.jsonl"
        vocabulary_path = lib.vocabulary_artifact_path(unique_base)
        manifest_path = lib.manifest_artifact_path("2026-04-02T00-00-00Z_00000000-0000-0000-0000-000000000000")
        mutated = json.loads(json.dumps(config))
        mutated["qdrant"]["collection"]["name"] = unique_base
        mutated["artifacts"]["manifest_path"] = lib.repo_root_relative_str(manifest_path)
        lib.write_text(config_path, lib.dump_toml_document(mutated))
        lib.write_chunks_jsonl(chunks_path, [lib.build_valid_chunk()])
        process = lib.run_ingest_subprocess(args.script_path, chunks_path, config_path, args.env_file_path)
        get_status, _, get_json = lib.get_collection(env["QDRANT_URL"], effective_name)
        fields = lib.extract_hybrid_collection_fields(get_json)
        try:
            delete_status, delete_body, _ = lib.delete_collection(env["QDRANT_URL"], effective_name)
            if delete_status < 200 or delete_status >= 300:
                cleanup_error = f"http_status={delete_status} body={delete_body}"
        except Exception as exc:
            cleanup_error = str(exc)
        finally:
            lib.cleanup_artifact_file(vocabulary_path)
            lib.cleanup_artifact_file(manifest_path)

    metadata = fields["metadata"] or {}
    dense_vectors = fields["dense_vectors"] or {}
    sparse_vectors = fields["sparse_vectors"] or {}
    dense_name = mutated["qdrant"]["collection"]["dense_vector_name"]
    sparse_name = mutated["qdrant"]["collection"]["sparse_vector_name"]
    ok = (
        process.returncode == 0
        and get_status == 200
        and isinstance(dense_vectors, dict)
        and dense_name in dense_vectors
        and isinstance(sparse_vectors, dict)
        and sparse_name in sparse_vectors
        and metadata.get("embedding_model_name") == mutated["embedding"]["model"]["name"]
        and metadata.get("sparse_strategy_kind") == mutated["sparse"]["strategy"]["kind"]
        and metadata.get("sparse_strategy_version") == mutated["sparse"]["strategy"]["version"]
        and metadata.get("corpus_version") == mutated["pipeline"]["corpus_version"]
        and isinstance(metadata.get("vocabulary_identity"), dict)
        and cleanup_error is None
    )
    if ok:
        print("OK [qdrant_collection_metadata_roundtrip]")
        print("cases=1 failed=0 passed=1")
        return
    print("FAIL [qdrant_collection_metadata_roundtrip]")
    print(f"error=unexpected metadata roundtrip get_status={get_status}")
    print(f"collection_name={effective_name}")
    print(f"stdout={process.stdout.strip()}")
    print(f"stderr={process.stderr.strip()}")
    print(f"actual_metadata={json.dumps(metadata, ensure_ascii=False)}")
    print(f"actual_dense_vectors={json.dumps(dense_vectors, ensure_ascii=False)}")
    print(f"actual_sparse_vectors={json.dumps(sparse_vectors, ensure_ascii=False)}")
    print(f"cleanup_error={cleanup_error}")
    print("cases=1 failed=1 passed=0")
    raise SystemExit(1)


if __name__ == "__main__":
    main()

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


def run_case(script_path: Path, config_path: Path, env_file_path: Path, case_name: str):
    config = lib.load_toml(config_path)
    env = lib.parse_env_file(env_file_path)
    unique_base = f"{config['qdrant']['collection']['name']}_{case_name}_{uuid.uuid4().hex[:8]}"
    effective_name = lib.derive_effective_collection_name(unique_base, config["sparse"]["strategy"]["kind"])
    mutated = json.loads(json.dumps(config))
    mutated["qdrant"]["collection"]["name"] = unique_base

    metadata = {
        "embedding_model_name": mutated["embedding"]["model"]["name"],
        "sparse_strategy_kind": mutated["sparse"]["strategy"]["kind"],
        "sparse_strategy_version": mutated["sparse"]["strategy"]["version"],
        "corpus_version": mutated["pipeline"]["corpus_version"],
        "vocabulary_identity": lib.build_vocabulary_identity(mutated),
    }
    vectors = {
        mutated["qdrant"]["collection"]["dense_vector_name"]: {
            "size": mutated["embedding"]["model"]["dimension"],
            "distance": mutated["qdrant"]["collection"]["distance"],
        }
    }
    sparse_vectors = {mutated["qdrant"]["collection"]["sparse_vector_name"]: {}}
    expected_error = ""

    if case_name == "collection_sparse_vectors_missing":
        sparse_vectors = None
        expected_error = "sparse_vectors"
    elif case_name == "dense_vector_name_mismatch":
        vectors = {"different_dense": list(vectors.values())[0]}
        expected_error = "dense_vector_name"
    elif case_name == "sparse_vector_name_mismatch":
        sparse_vectors = {"different_sparse": {}}
        expected_error = "sparse_vector_name"
    elif case_name == "embedding_model_name_mismatch":
        metadata["embedding_model_name"] = "different-model"
        expected_error = "embedding_model_name"
    elif case_name == "sparse_strategy_kind_mismatch":
        metadata["sparse_strategy_kind"] = "bm25_like"
        expected_error = "sparse_strategy_kind"
    elif case_name == "vocabulary_identity_mismatch":
        metadata["vocabulary_identity"]["collection_name"] = "different_collection"
        expected_error = "vocabulary_identity"
    else:
        raise RuntimeError(f"unknown case {case_name}")

    create_status, create_body, _ = lib.create_hybrid_collection(
        env["QDRANT_URL"],
        mutated,
        metadata_override=metadata,
        sparse_vectors_override=sparse_vectors,
        vectors_override=vectors,
    )
    if create_status < 200 or create_status >= 300:
        return False, {"error": f"failed to create collection body={create_body}", "case_name": case_name, "collection_name": effective_name, "stdout": "", "stderr": "", "cleanup_error": None}

    cleanup_error = None
    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        config_tmp = tmp_dir / "config.toml"
        chunks_path = tmp_dir / "chunks.jsonl"
        lib.write_text(config_tmp, lib.dump_toml_document(mutated))
        lib.write_chunks_jsonl(chunks_path, [lib.build_valid_chunk()])
        process = lib.run_ingest_subprocess(script_path, chunks_path, config_tmp, env_file_path)
        get_status, _, get_json = lib.get_collection(env["QDRANT_URL"], effective_name)
        fields = lib.extract_hybrid_collection_fields(get_json)
        try:
            delete_status, delete_body, _ = lib.delete_collection(env["QDRANT_URL"], effective_name)
            if delete_status < 200 or delete_status >= 300:
                cleanup_error = f"http_status={delete_status} body={delete_body}"
        except Exception as exc:
            cleanup_error = str(exc)

    combined = "\n".join([process.stdout.strip(), process.stderr.strip()])
    ok = process.returncode == 1 and expected_error in combined and get_status == 200 and fields["points_count"] == 0 and cleanup_error is None
    if ok:
        return True, {}
    return False, {
        "error": "compatibility case failed",
        "case_name": case_name,
        "collection_name": effective_name,
        "stdout": process.stdout.strip(),
        "stderr": process.stderr.strip(),
        "cleanup_error": cleanup_error,
    }


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

    cases = [
        "collection_sparse_vectors_missing",
        "dense_vector_name_mismatch",
        "sparse_vector_name_mismatch",
        "embedding_model_name_mismatch",
        "sparse_strategy_kind_mismatch",
        "vocabulary_identity_mismatch",
    ]
    failed = 0
    passed = 0
    for case_name in cases:
        ok, details = run_case(args.script_path, args.config_path, args.env_file_path, case_name)
        if ok:
            passed += 1
            print(f"OK [{case_name}]")
        else:
            failed += 1
            print(f"FAIL [{case_name}]")
            print(f"error={details['error']}")
            print(f"case_name={details['case_name']}")
            print(f"collection_name={details['collection_name']}")
            print(f"stdout={details['stdout']}")
            print(f"stderr={details['stderr']}")
            print(f"cleanup_error={details['cleanup_error']}")
    print(f"cases={len(cases)} failed={failed} passed={passed}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

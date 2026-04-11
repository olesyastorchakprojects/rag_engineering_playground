#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


def load_toml(path: Path):
    try:
        import tomllib as parser  # type: ignore
    except ModuleNotFoundError:
        import tomli as parser  # type: ignore
    with path.open("rb") as handle:
        return parser.load(handle)


def dump_toml_value(value, indent=""):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        if not value:
            return "[]"
        parts = ["["]
        for item in value:
            parts.append(f"{indent}  {dump_toml_value(item, indent + '  ')},")
        parts.append(f"{indent}]")
        return "\n".join(parts)
    raise TypeError(f"unsupported TOML value type: {type(value).__name__}")


def dump_toml_document(data):
    lines = []

    def emit_table(path_parts, table):
        if path_parts:
            lines.append(f"[{'.'.join(path_parts)}]")
        scalar_items = []
        nested_items = []
        for key, value in table.items():
            if isinstance(value, dict):
                nested_items.append((key, value))
            else:
                scalar_items.append((key, value))
        for key, value in scalar_items:
            lines.append(f"{key} = {dump_toml_value(value)}")
        if scalar_items and nested_items:
            lines.append("")
        for index, (key, value) in enumerate(nested_items):
            emit_table(path_parts + [key], value)
            if index != len(nested_items) - 1:
                lines.append("")

    emit_table([], data)
    return "\n".join(lines) + "\n"


def build_valid_chunk() -> dict:
    return {
        "schema_version": 1,
        "doc_id": "2e9b0ce6-b07e-4b1c-9918-289627c74577",
        "chunk_id": str(uuid.uuid4()),
        "url": "local://Understanding-Distributed-Systems-2nd-Edition.pdf",
        "document_title": "Understanding Distributed Systems (2nd Edition)",
        "section_title": "Introduction",
        "section_path": ["Introduction", "Introduction"],
        "chunk_index": 0,
        "page_start": 19,
        "page_end": 19,
        "tags": ["distributed-systems", "book", "architecture"],
        "content_hash": "sha256:test-content-hash",
        "chunking_version": "v1",
        "chunk_created_at": "2026-02-17T09:00:00Z",
        "text": "Chapter 1 Introduction ...",
    }


def parse_env_file(path: Path):
    parsed = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "" or stripped.startswith("#"):
            continue
        key, value = line.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def make_response(status_code: int, body: bytes):
    body_text = body.decode("utf-8", errors="replace")
    try:
        json_body = json.loads(body_text) if body_text else None
    except json.JSONDecodeError:
        json_body = None
    return status_code, body_text, json_body


def send_json_request(method: str, url: str, payload=None, timeout_sec: int = 30):
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url=url, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            return make_response(response.getcode(), response.read())
    except urllib.error.HTTPError as exc:
        return make_response(exc.code, exc.read())


def check_qdrant_available(base_url: str):
    status_code, _, json_body = send_json_request("GET", base_url.rstrip("/") + "/collections")
    if status_code < 200 or status_code >= 300:
        raise RuntimeError(f"qdrant unavailable http_status={status_code}")
    if not isinstance(json_body, dict):
        raise RuntimeError("qdrant availability response is not JSON object")


def check_embedding_available(base_url: str, model_name: str):
    status_code, body_text, json_body = send_json_request(
        "POST",
        base_url.rstrip("/") + "/api/embed",
        {"model": model_name, "input": ["availability probe"]},
        timeout_sec=60,
    )
    if status_code < 200 or status_code >= 300:
        raise RuntimeError(f"embedding service unavailable http_status={status_code} body={body_text}")
    if not isinstance(json_body, dict) or not isinstance(json_body.get("embeddings"), list):
        raise RuntimeError("embedding service availability response is invalid")


def get_collection(qdrant_url: str, collection_name: str):
    quoted_name = urllib.parse.quote(collection_name, safe="")
    return send_json_request("GET", qdrant_url.rstrip("/") + f"/collections/{quoted_name}")


def delete_collection(qdrant_url: str, collection_name: str):
    quoted_name = urllib.parse.quote(collection_name, safe="")
    return send_json_request("DELETE", qdrant_url.rstrip("/") + f"/collections/{quoted_name}")


def run_case(script_path: Path, chunk_schema_path: Path, config_path: Path, env_file_path: Path):
    _ = chunk_schema_path
    config = load_toml(config_path)
    env = parse_env_file(env_file_path)
    qdrant_url = env["QDRANT_URL"]
    embedding_url = env["OLLAMA_URL"]
    collection_name = f"{config['qdrant']['collection']['name']}_e2e_{uuid.uuid4().hex[:12]}"
    cleanup_error = None

    check_qdrant_available(qdrant_url)
    check_embedding_available(embedding_url, config["embedding"]["model"]["name"])

    status_code, _, _ = get_collection(qdrant_url, collection_name)
    if status_code != 404:
        raise RuntimeError(f"temporary collection already exists collection_name={collection_name} http_status={status_code}")

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        chunks_path = tmp_dir / "chunks.jsonl"
        mutated_config_path = tmp_dir / "config.toml"

        mutated_config = json.loads(json.dumps(config))
        mutated_config["qdrant"]["collection"]["name"] = collection_name
        chunks_path.write_text(json.dumps(build_valid_chunk()) + "\n", encoding="utf-8")
        mutated_config_path.write_text(dump_toml_document(mutated_config), encoding="utf-8")

        process = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--chunks",
                str(chunks_path),
                "--config",
                str(mutated_config_path),
                "--env-file",
                str(env_file_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        status_code, _, json_body = get_collection(qdrant_url, collection_name)
        actual_metadata = None
        actual_vector_size = None
        actual_vector_distance = None
        if isinstance(json_body, dict):
            result = json_body.get("result")
            if isinstance(result, dict):
                config_obj = result.get("config")
                if isinstance(config_obj, dict):
                    metadata = config_obj.get("metadata")
                    if isinstance(metadata, dict):
                        actual_metadata = metadata.get("embedding_model_name")
                    params = config_obj.get("params")
                    if isinstance(params, dict):
                        vectors = params.get("vectors")
                        if isinstance(vectors, dict):
                            actual_vector_size = vectors.get("size")
                            actual_vector_distance = vectors.get("distance")

        try:
            delete_status, delete_body, _ = delete_collection(qdrant_url, collection_name)
            if delete_status < 200 or delete_status >= 300:
                cleanup_error = f"http_status={delete_status} body={delete_body}"
        except Exception as exc:
            cleanup_error = str(exc)

        if process.returncode != 0:
            return (
                False,
                {
                    "error": "ingest subprocess failed",
                    "collection_name": collection_name,
                    "stdout": process.stdout.strip(),
                    "stderr": process.stderr.strip(),
                    "actual_metadata": actual_metadata,
                    "actual_vector_size": actual_vector_size,
                    "actual_vector_distance": actual_vector_distance,
                    "cleanup_error": cleanup_error,
                },
            )

        if status_code != 200:
            return (
                False,
                {
                    "error": f"collection GET failed http_status={status_code}",
                    "collection_name": collection_name,
                    "stdout": process.stdout.strip(),
                    "stderr": process.stderr.strip(),
                    "actual_metadata": actual_metadata,
                    "actual_vector_size": actual_vector_size,
                    "actual_vector_distance": actual_vector_distance,
                    "cleanup_error": cleanup_error,
                },
            )

        expected_metadata = config["embedding"]["model"]["name"]
        expected_vector_size = config["embedding"]["model"]["dimension"]
        expected_vector_distance = config["qdrant"]["collection"]["distance"]

        if actual_metadata != expected_metadata or actual_vector_size != expected_vector_size or actual_vector_distance != expected_vector_distance:
            return (
                False,
                {
                    "error": "collection contract fields do not match config",
                    "collection_name": collection_name,
                    "stdout": process.stdout.strip(),
                    "stderr": process.stderr.strip(),
                    "actual_metadata": actual_metadata,
                    "actual_vector_size": actual_vector_size,
                    "actual_vector_distance": actual_vector_distance,
                    "cleanup_error": cleanup_error,
                },
            )

        if cleanup_error is not None:
            return (
                False,
                {
                    "error": "cleanup failed",
                    "collection_name": collection_name,
                    "stdout": process.stdout.strip(),
                    "stderr": process.stderr.strip(),
                    "actual_metadata": actual_metadata,
                    "actual_vector_size": actual_vector_size,
                    "actual_vector_distance": actual_vector_distance,
                    "cleanup_error": cleanup_error,
                },
            )

        return True, {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=Path, required=True, dest="script_path")
    parser.add_argument("--chunk-schema", type=Path, required=True, dest="chunk_schema_path")
    parser.add_argument("--config", type=Path, required=True, dest="config_path")
    parser.add_argument("--env-file", type=Path, required=True, dest="env_file_path")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    case_name = "collection_metadata_roundtrip"
    try:
        ok, details = run_case(
            args.script_path,
            args.chunk_schema_path,
            args.config_path,
            args.env_file_path,
        )
    except Exception as exc:
        ok = False
        details = {
            "error": str(exc),
            "collection_name": "",
            "stdout": "",
            "stderr": "",
            "actual_metadata": None,
            "actual_vector_size": None,
            "actual_vector_distance": None,
            "cleanup_error": None,
        }

    failed = 0
    passed = 0
    if ok:
        passed = 1
        print(f"OK [{case_name}]")
    else:
        failed = 1
        print(f"FAIL [{case_name}]")
        print(f"error={details['error']}")
        print(f"collection_name={details['collection_name']}")
        print(f"stdout={details['stdout']}")
        print(f"stderr={details['stderr']}")
        print(f"actual_metadata={details['actual_metadata']}")
        print(f"actual_vector_size={details['actual_vector_size']}")
        print(f"actual_vector_distance={details['actual_vector_distance']}")
        print(f"cleanup_error={details['cleanup_error']}")

    print(f"cases=1 failed={failed} passed={passed}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

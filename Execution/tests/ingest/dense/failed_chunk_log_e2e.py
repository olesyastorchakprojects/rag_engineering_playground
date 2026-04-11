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


def send_json_request(method: str, url: str, payload=None, timeout_sec: int = 60):
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


def get_point(qdrant_url: str, collection_name: str, point_id: str):
    quoted_name = urllib.parse.quote(collection_name, safe="")
    quoted_point_id = urllib.parse.quote(point_id, safe="")
    return send_json_request("GET", qdrant_url.rstrip("/") + f"/collections/{quoted_name}/points/{quoted_point_id}")


def update_point_payload(qdrant_url: str, collection_name: str, point_id: str, payload_update: dict):
    quoted_name = urllib.parse.quote(collection_name, safe="")
    return send_json_request(
        "PUT",
        qdrant_url.rstrip("/") + f"/collections/{quoted_name}/points/payload",
        {"payload": payload_update, "points": [point_id]},
    )


def delete_collection(qdrant_url: str, collection_name: str):
    quoted_name = urllib.parse.quote(collection_name, safe="")
    return send_json_request("DELETE", qdrant_url.rstrip("/") + f"/collections/{quoted_name}")


def compute_point_id(config: dict, chunk: dict) -> str:
    namespace_uuid = uuid.UUID(config["qdrant"]["point_id"]["namespace_uuid"])
    return str(uuid.uuid5(namespace_uuid, chunk["chunk_id"]))


def build_chunk() -> dict:
    return {
        "schema_version": 1,
        "doc_id": "2e9b0ce6-b07e-4b1c-9918-289627c74577",
        "chunk_id": str(uuid.uuid4()),
        "url": "local://Understanding-Distributed-Systems-2nd-Edition.pdf",
        "document_title": "Understanding Distributed Systems (2nd Edition)",
        "section_title": "Failed Log Section",
        "section_path": ["Introduction", "Failed Log Section"],
        "chunk_index": 0,
        "page_start": 19,
        "page_end": 19,
        "tags": ["distributed-systems", "book", "architecture"],
        "content_hash": "sha256:failed-log-original",
        "chunking_version": "v1",
        "chunk_created_at": "2026-02-17T09:00:00Z",
        "text": "Failed log text",
    }


def extract_points_count(collection_json_body):
    if not isinstance(collection_json_body, dict):
        return None
    result = collection_json_body.get("result")
    if not isinstance(result, dict):
        return None
    return result.get("points_count")


def extract_point_payload(point_json_body):
    if not isinstance(point_json_body, dict):
        return None, None, None
    status = point_json_body.get("status")
    result = point_json_body.get("result")
    if not isinstance(result, dict):
        return status, result, None
    return status, result.get("id"), result.get("payload")


def read_jsonl_lines(path: Path):
    if not path.exists():
        return []
    lines = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if stripped == "":
            continue
        lines.append(json.loads(stripped))
    return lines


def run_ingest(script_path: Path, chunks_path: Path, config_path: Path, env_file_path: Path):
    return subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--chunks",
            str(chunks_path),
            "--config",
            str(config_path),
            "--env-file",
            str(env_file_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def run_case(script_path: Path, chunk_schema_path: Path, config_path: Path, env_file_path: Path):
    if not chunk_schema_path.exists():
        raise RuntimeError(f"chunk schema file not found path={chunk_schema_path}")
    config = load_toml(config_path)
    env = parse_env_file(env_file_path)
    qdrant_url = env["QDRANT_URL"]
    embedding_url = env["OLLAMA_URL"]
    collection_name = f"{config['qdrant']['collection']['name']}_failed_log_e2e_{uuid.uuid4().hex[:10]}"
    cleanup_error = None
    first_run_stdout = ""
    first_run_stderr = ""
    second_run_stdout = ""
    second_run_stderr = ""
    actual_points_count = None
    actual_failed_log_entries = None

    check_qdrant_available(qdrant_url)
    check_embedding_available(embedding_url, config["embedding"]["model"]["name"])

    pre_status, _, _ = get_collection(qdrant_url, collection_name)
    if pre_status != 404:
        raise RuntimeError(f"temporary collection already exists collection_name={collection_name} http_status={pre_status}")

    chunk = build_chunk()
    point_id = compute_point_id(config, chunk)

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        chunks_path = tmp_dir / "chunks.jsonl"
        mutated_config_path = tmp_dir / "config.toml"
        skipped_log_path = tmp_dir / "skipped.jsonl"
        failed_log_path = tmp_dir / "failed.jsonl"

        mutated_config = json.loads(json.dumps(config))
        mutated_config["qdrant"]["collection"]["name"] = collection_name
        mutated_config["logging"]["failed_chunk_log_path"] = str(failed_log_path)
        mutated_config["logging"]["skipped_chunk_log_path"] = str(skipped_log_path)
        mutated_config_path.write_text(dump_toml_document(mutated_config), encoding="utf-8")
        chunks_path.write_text(json.dumps(chunk) + "\n", encoding="utf-8")

        first_process = run_ingest(script_path, chunks_path, mutated_config_path, env_file_path)
        first_run_stdout = first_process.stdout.strip()
        first_run_stderr = first_process.stderr.strip()
        if first_process.returncode != 0:
            return False, {
                "error": "first ingest subprocess failed",
                "collection_name": collection_name,
                "first_run_stdout": first_run_stdout,
                "first_run_stderr": first_run_stderr,
                "second_run_stdout": second_run_stdout,
                "second_run_stderr": second_run_stderr,
                "actual_points_count": actual_points_count,
                "actual_failed_log_entries": actual_failed_log_entries,
                "cleanup_error": cleanup_error,
            }

        first_failed_entries = read_jsonl_lines(failed_log_path)
        first_skipped_entries = read_jsonl_lines(skipped_log_path)
        if len(first_failed_entries) != 0 or len(first_skipped_entries) != 0:
            return False, {
                "error": "first run produced unexpected log entries",
                "collection_name": collection_name,
                "first_run_stdout": first_run_stdout,
                "first_run_stderr": first_run_stderr,
                "second_run_stdout": second_run_stdout,
                "second_run_stderr": second_run_stderr,
                "actual_points_count": actual_points_count,
                "actual_failed_log_entries": actual_failed_log_entries,
                "cleanup_error": cleanup_error,
            }

        collection_status_code, _, collection_json = get_collection(qdrant_url, collection_name)
        actual_points_count = extract_points_count(collection_json)
        if collection_status_code != 200 or actual_points_count != 1:
            return False, {
                "error": "first run did not create exactly 1 point",
                "collection_name": collection_name,
                "first_run_stdout": first_run_stdout,
                "first_run_stderr": first_run_stderr,
                "second_run_stdout": second_run_stdout,
                "second_run_stderr": second_run_stderr,
                "actual_points_count": actual_points_count,
                "actual_failed_log_entries": actual_failed_log_entries,
                "cleanup_error": cleanup_error,
            }

        point_status_code, _, point_json = get_point(qdrant_url, collection_name, point_id)
        point_status, actual_point_id, payload = extract_point_payload(point_json)
        if point_status_code != 200 or point_status != "ok" or actual_point_id != point_id or not isinstance(payload, dict):
            return False, {
                "error": "failed to read point payload after first run",
                "collection_name": collection_name,
                "first_run_stdout": first_run_stdout,
                "first_run_stderr": first_run_stderr,
                "second_run_stdout": second_run_stdout,
                "second_run_stderr": second_run_stderr,
                "actual_points_count": actual_points_count,
                "actual_failed_log_entries": actual_failed_log_entries,
                "cleanup_error": cleanup_error,
            }

        mutated_payload_snapshot = json.loads(json.dumps(payload))
        mutated_payload_snapshot.pop("content_hash", None)
        mutate_status, mutate_body, _ = update_point_payload(qdrant_url, collection_name, point_id, mutated_payload_snapshot)
        if mutate_status < 200 or mutate_status >= 300:
            return False, {
                "error": f"failed to mutate point payload body={mutate_body}",
                "collection_name": collection_name,
                "first_run_stdout": first_run_stdout,
                "first_run_stderr": first_run_stderr,
                "second_run_stdout": second_run_stdout,
                "second_run_stderr": second_run_stderr,
                "actual_points_count": actual_points_count,
                "actual_failed_log_entries": actual_failed_log_entries,
                "cleanup_error": cleanup_error,
            }

        second_process = run_ingest(script_path, chunks_path, mutated_config_path, env_file_path)
        second_run_stdout = second_process.stdout.strip()
        second_run_stderr = second_process.stderr.strip()

        final_collection_status, _, final_collection_json = get_collection(qdrant_url, collection_name)
        actual_points_count = extract_points_count(final_collection_json)
        final_point_status, _, final_point_json = get_point(qdrant_url, collection_name, point_id)
        final_point_result_status, final_point_id, final_payload = extract_point_payload(final_point_json)

        try:
            delete_status, delete_body, _ = delete_collection(qdrant_url, collection_name)
            if delete_status < 200 or delete_status >= 300:
                cleanup_error = f"http_status={delete_status} body={delete_body}"
        except Exception as exc:
            cleanup_error = str(exc)

        failed_entries = read_jsonl_lines(failed_log_path)
        skipped_entries = read_jsonl_lines(skipped_log_path)
        actual_failed_log_entries = len(failed_entries)

    if second_process.returncode != 1:
        return False, {
            "error": "second ingest subprocess exit code mismatch",
            "collection_name": collection_name,
            "first_run_stdout": first_run_stdout,
            "first_run_stderr": first_run_stderr,
            "second_run_stdout": second_run_stdout,
            "second_run_stderr": second_run_stderr,
            "actual_points_count": actual_points_count,
            "actual_failed_log_entries": actual_failed_log_entries,
            "cleanup_error": cleanup_error,
        }
    for required_substring in ("created=0", "updated=0", "unchanged=0", "skipped=0", "failed=1", "FAIL: dense ingest failed"):
        if required_substring not in second_run_stdout:
            return False, {
                "error": f"second run stdout missing substring {required_substring}",
                "collection_name": collection_name,
                "first_run_stdout": first_run_stdout,
                "first_run_stderr": first_run_stderr,
                "second_run_stdout": second_run_stdout,
                "second_run_stderr": second_run_stderr,
                "actual_points_count": actual_points_count,
                "actual_failed_log_entries": actual_failed_log_entries,
                "cleanup_error": cleanup_error,
            }
    if actual_failed_log_entries != 1:
        return False, {
            "error": "unexpected failed log entry count",
            "collection_name": collection_name,
            "first_run_stdout": first_run_stdout,
            "first_run_stderr": first_run_stderr,
            "second_run_stdout": second_run_stdout,
            "second_run_stderr": second_run_stderr,
            "actual_points_count": actual_points_count,
            "actual_failed_log_entries": actual_failed_log_entries,
            "cleanup_error": cleanup_error,
        }
    failed_entry = failed_entries[0]
    if failed_entry.get("chunk_id") != chunk["chunk_id"]:
        return False, {
            "error": "failed log chunk_id mismatch",
            "collection_name": collection_name,
            "first_run_stdout": first_run_stdout,
            "first_run_stderr": first_run_stderr,
            "second_run_stdout": second_run_stdout,
            "second_run_stderr": second_run_stderr,
            "actual_points_count": actual_points_count,
            "actual_failed_log_entries": actual_failed_log_entries,
            "cleanup_error": cleanup_error,
        }
    if failed_entry.get("stage") != "qdrant":
        return False, {
            "error": "failed log stage mismatch",
            "collection_name": collection_name,
            "first_run_stdout": first_run_stdout,
            "first_run_stderr": first_run_stderr,
            "second_run_stdout": second_run_stdout,
            "second_run_stderr": second_run_stderr,
            "actual_points_count": actual_points_count,
            "actual_failed_log_entries": actual_failed_log_entries,
            "cleanup_error": cleanup_error,
        }
    error_text = failed_entry.get("error")
    if not isinstance(error_text, str) or "missing field path: content_hash" not in error_text:
        return False, {
            "error": "failed log error mismatch",
            "collection_name": collection_name,
            "first_run_stdout": first_run_stdout,
            "first_run_stderr": first_run_stderr,
            "second_run_stdout": second_run_stdout,
            "second_run_stderr": second_run_stderr,
            "actual_points_count": actual_points_count,
            "actual_failed_log_entries": actual_failed_log_entries,
            "cleanup_error": cleanup_error,
        }
    if len(skipped_entries) != 0:
        return False, {
            "error": "skipped log is not empty",
            "collection_name": collection_name,
            "first_run_stdout": first_run_stdout,
            "first_run_stderr": first_run_stderr,
            "second_run_stdout": second_run_stdout,
            "second_run_stderr": second_run_stderr,
            "actual_points_count": actual_points_count,
            "actual_failed_log_entries": actual_failed_log_entries,
            "cleanup_error": cleanup_error,
        }
    if final_collection_status != 200 or actual_points_count != 1:
        return False, {
            "error": "collection points_count mismatch after second run",
            "collection_name": collection_name,
            "first_run_stdout": first_run_stdout,
            "first_run_stderr": first_run_stderr,
            "second_run_stdout": second_run_stdout,
            "second_run_stderr": second_run_stderr,
            "actual_points_count": actual_points_count,
            "actual_failed_log_entries": actual_failed_log_entries,
            "cleanup_error": cleanup_error,
        }
    if final_point_status != 200 or final_point_result_status != "ok" or final_point_id != point_id:
        return False, {
            "error": "failed to read point after second run",
            "collection_name": collection_name,
            "first_run_stdout": first_run_stdout,
            "first_run_stderr": first_run_stderr,
            "second_run_stdout": second_run_stdout,
            "second_run_stderr": second_run_stderr,
            "actual_points_count": actual_points_count,
            "actual_failed_log_entries": actual_failed_log_entries,
            "cleanup_error": cleanup_error,
        }
    if final_payload != mutated_payload_snapshot:
        return False, {
            "error": "point payload changed after second run",
            "collection_name": collection_name,
            "first_run_stdout": first_run_stdout,
            "first_run_stderr": first_run_stderr,
            "second_run_stdout": second_run_stdout,
            "second_run_stderr": second_run_stderr,
            "actual_points_count": actual_points_count,
            "actual_failed_log_entries": actual_failed_log_entries,
            "cleanup_error": cleanup_error,
        }
    if "content_hash" in final_payload:
        return False, {
            "error": "content_hash was unexpectedly restored",
            "collection_name": collection_name,
            "first_run_stdout": first_run_stdout,
            "first_run_stderr": first_run_stderr,
            "second_run_stdout": second_run_stdout,
            "second_run_stderr": second_run_stderr,
            "actual_points_count": actual_points_count,
            "actual_failed_log_entries": actual_failed_log_entries,
            "cleanup_error": cleanup_error,
        }
    if cleanup_error is not None:
        return False, {
            "error": "cleanup failed",
            "collection_name": collection_name,
            "first_run_stdout": first_run_stdout,
            "first_run_stderr": first_run_stderr,
            "second_run_stdout": second_run_stdout,
            "second_run_stderr": second_run_stderr,
            "actual_points_count": actual_points_count,
            "actual_failed_log_entries": actual_failed_log_entries,
            "cleanup_error": cleanup_error,
        }
    return True, {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=Path, required=True, dest="script_path")
    parser.add_argument("--chunk-schema", type=Path, required=True, dest="chunk_schema_path")
    parser.add_argument("--config", type=Path, required=True, dest="config_path")
    parser.add_argument("--env-file", type=Path, required=True, dest="env_file_path")
    parser.add_argument("--verbose", action="store_true", dest="verbose")
    args = parser.parse_args()

    ok, details = run_case(args.script_path, args.chunk_schema_path, args.config_path, args.env_file_path)
    if ok:
        print("OK [failed_chunk_log_on_broken_point]")
        print("cases=1 failed=0 passed=1")
        raise SystemExit(0)

    print("FAIL [failed_chunk_log_on_broken_point]")
    print(f"error={details['error']}")
    print(f"collection_name={details['collection_name']}")
    print(f"first_run_stdout={details['first_run_stdout']}")
    print(f"first_run_stderr={details['first_run_stderr']}")
    print(f"second_run_stdout={details['second_run_stdout']}")
    print(f"second_run_stderr={details['second_run_stderr']}")
    print(f"actual_points_count={details['actual_points_count']}")
    print(f"actual_failed_log_entries={details['actual_failed_log_entries']}")
    if details.get("cleanup_error") is not None:
        print(f"cleanup_error={details['cleanup_error']}")
    print("cases=1 failed=1 passed=0")
    raise SystemExit(1)


if __name__ == "__main__":
    main()

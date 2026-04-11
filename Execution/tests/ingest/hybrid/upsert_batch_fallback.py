#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler
from pathlib import Path


THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))
import _hybrid_testlib as lib  # noqa: E402


class State:
    def __init__(self):
        self.requests = []
        self.lock = threading.Lock()


def make_embedding_handler(dimension: int):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            json_body = json.loads(body.decode("utf-8"))
            items = json_body.get("input", [])
            embeddings = [[0.0] * dimension for _ in items]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"embeddings": embeddings}).encode("utf-8"))

        def log_message(self, format, *args):
            return

    return Handler


def make_qdrant_handler(state: State, collection_name: str):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == f"/collections/{collection_name}":
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"error","error":"collection missing"}')
                return
            self.send_response(500)
            self.end_headers()

        def do_PUT(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            try:
                json_body = json.loads(body.decode("utf-8"))
            except Exception:
                json_body = None
            with state.lock:
                state.requests.append(lib.RecordedRequest("PUT", self.path, body, json_body))
            if self.path == f"/collections/{collection_name}":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok","result":{"status":"acknowledged","operation_id":1}}')
                return
            if self.path == f"/collections/{collection_name}/points":
                points = json_body.get("points", [])
                if len(points) == 2:
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"status":"error","error":"batch upsert failure"}')
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok","result":{"status":"acknowledged","operation_id":1}}')
                return
            self.send_response(500)
            self.end_headers()

        def log_message(self, format, *args):
            return

    return Handler


def has_hybrid_shape(point: dict, dense_name: str, sparse_name: str) -> bool:
    vector = point.get("vector")
    if not isinstance(vector, dict):
        return False
    if dense_name not in vector or sparse_name not in vector:
        return False
    sparse = vector[sparse_name]
    return isinstance(sparse, dict) and isinstance(sparse.get("indices"), list) and isinstance(sparse.get("values"), list)


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
    config["embedding"]["transport"]["max_batch_size"] = 2
    config["qdrant"]["transport"]["upsert_batch_size"] = 2
    effective_name = lib.derive_effective_collection_name(
        config["qdrant"]["collection"]["name"], config["sparse"]["strategy"]["kind"]
    )
    dense_name = config["qdrant"]["collection"]["dense_vector_name"]
    sparse_name = config["qdrant"]["collection"]["sparse_vector_name"]
    dimension = config["embedding"]["model"]["dimension"]
    retry_attempts = config["qdrant"]["retry"]["max_attempts"]
    expected_points_lengths = ([2] * retry_attempts) + [1, 1]
    state = State()
    embedding_server = lib.StubServer(make_embedding_handler(dimension))
    qdrant_server = lib.StubServer(make_qdrant_handler(state, effective_name))

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        chunks_path = tmp_dir / "chunks.jsonl"
        config_path = tmp_dir / "config.toml"
        env_path = tmp_dir / ".env"
        run_id = str(uuid.uuid4())
        started_at = "2026-04-02T00:00:00Z"
        manifest_path = lib.manifest_artifact_path(f"{started_at}_{run_id}")
        temp_config = json.loads(json.dumps(config))
        vocabulary_path = lib.vocabulary_artifact_path(temp_config["qdrant"]["collection"]["name"])
        temp_config["artifacts"]["manifest_path"] = lib.repo_root_relative_str(manifest_path)
        lib.write_chunks_jsonl(chunks_path, [lib.build_valid_chunk(chunk_index=0), lib.build_valid_chunk(chunk_index=1)])
        lib.write_text(config_path, lib.dump_toml_document(temp_config))
        env_text = lib.read_text(args.env_file_path)
        process = None
        try:
            embedding_server.start()
            qdrant_server.start()
            env_text = lib.replace_env_value(env_text, "QDRANT_URL", qdrant_server.base_url)
            env_text = lib.replace_env_value(env_text, "OLLAMA_URL", embedding_server.base_url)
            lib.write_text(env_path, env_text)
            process = subprocess.Popen(
                [sys.executable, str(args.script_path), "--chunks", str(chunks_path), "--config", str(config_path), "--env-file", str(env_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=lib.REPO_ROOT,
            )
            deadline = time.time() + lib.TIMEOUT_SEC
            observed_points_lengths = []
            while time.time() < deadline:
                with state.lock:
                    observed_points_lengths = [
                        len(req.json_body.get("points", []))
                        for req in state.requests
                        if req.path == f"/collections/{effective_name}/points" and isinstance(req.json_body, dict)
                    ]
                if observed_points_lengths[: len(expected_points_lengths)] == expected_points_lengths:
                    if len(observed_points_lengths) >= len(expected_points_lengths):
                        break
                if process.poll() is not None:
                    break
                time.sleep(0.05)
            lib.terminate_process(process)
            with state.lock:
                point_requests = [
                    req.json_body
                    for req in state.requests
                    if req.path == f"/collections/{effective_name}/points" and isinstance(req.json_body, dict)
                ]
            shape_ok = all(
                has_hybrid_shape(point, dense_name, sparse_name)
                for req in point_requests
                for point in req.get("points", [])
            )
            ok = observed_points_lengths[: len(expected_points_lengths)] == expected_points_lengths and shape_ok
            if ok:
                print("OK [upsert_batch_fallback]")
                print("cases=1 failed=0 passed=1")
                return
            stdout, stderr = process.communicate()
            print("FAIL [upsert_batch_fallback]")
            print(f"error=unexpected upsert fallback request sequence {observed_points_lengths}")
            print(f"stdout={stdout.strip()}")
            print(f"stderr={stderr.strip()}")
            if args.verbose:
                print(f"expected_points_lengths={expected_points_lengths}")
            print("cases=1 failed=1 passed=0")
            raise SystemExit(1)
        finally:
            if process is not None:
                lib.terminate_process(process)
            lib.cleanup_artifact_file(vocabulary_path)
            lib.cleanup_artifact_file(manifest_path)
            embedding_server.stop()
            qdrant_server.stop()


if __name__ == "__main__":
    main()

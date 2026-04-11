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
            embeddings = [[0.0] * dimension for _ in json_body.get("input", [])]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"embeddings": embeddings}).encode("utf-8"))

        def log_message(self, format, *args):
            return

    return Handler


def make_qdrant_handler(state: State, effective_name: str):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == f"/collections/{effective_name}":
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
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok","result":{"status":"acknowledged","operation_id":1}}')

        def log_message(self, format, *args):
            return

    return Handler


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
    effective_name = lib.derive_effective_collection_name(config["qdrant"]["collection"]["name"], config["sparse"]["strategy"]["kind"])
    dense_name = config["qdrant"]["collection"]["dense_vector_name"]
    sparse_name = config["qdrant"]["collection"]["sparse_vector_name"]
    state = State()
    embedding_server = lib.StubServer(make_embedding_handler(config["embedding"]["model"]["dimension"]))
    qdrant_server = lib.StubServer(make_qdrant_handler(state, effective_name))

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        chunks_path = tmp_dir / "chunks.jsonl"
        config_path = tmp_dir / "config.toml"
        env_path = tmp_dir / ".env"
        run_id = str(uuid.uuid4())
        started_at = "2026-04-02T00:00:00Z"
        temp_config = json.loads(json.dumps(config))
        vocabulary_path = lib.vocabulary_artifact_path(temp_config["qdrant"]["collection"]["name"])
        manifest_path = lib.manifest_artifact_path(f"{started_at}_{run_id}")
        temp_config["artifacts"]["manifest_path"] = lib.repo_root_relative_str(manifest_path)
        lib.write_text(config_path, lib.dump_toml_document(temp_config))
        chunks_path.write_text(json.dumps(lib.build_valid_chunk()) + "\n", encoding="utf-8")
        process = None
        try:
            embedding_server.start()
            qdrant_server.start()
            env_text = lib.read_text(args.env_file_path)
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
            create_request = None
            while time.time() < deadline:
                with state.lock:
                    for request in state.requests:
                        if request.path == f"/collections/{effective_name}":
                            create_request = request
                            break
                if create_request is not None or process.poll() is not None:
                    break
                time.sleep(0.05)
            lib.terminate_process(process)
            body = create_request.json_body if create_request is not None else None
            metadata = body.get("metadata") if isinstance(body, dict) else None
            vectors = body.get("vectors") if isinstance(body, dict) else None
            sparse_vectors = body.get("sparse_vectors") if isinstance(body, dict) else None
            ok = (
                create_request is not None
                and create_request.path == f"/collections/{effective_name}"
                and isinstance(vectors, dict)
                and dense_name in vectors
                and isinstance(sparse_vectors, dict)
                and sparse_name in sparse_vectors
                and isinstance(metadata, dict)
                and metadata.get("embedding_model_name") == config["embedding"]["model"]["name"]
                and metadata.get("sparse_strategy_kind") == config["sparse"]["strategy"]["kind"]
            )
            if ok:
                print("OK [hybrid_collection_create_shape]")
                print("cases=1 failed=0 passed=1")
                return
            stdout, stderr = process.communicate()
            print("FAIL [hybrid_collection_create_shape]")
            print(f"error=unexpected create body {body}")
            print(f"stdout={stdout.strip()}")
            print(f"stderr={stderr.strip()}")
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

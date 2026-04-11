#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path


THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))
import _hybrid_testlib as lib  # noqa: E402


class EmbeddingState:
    def __init__(self):
        self.requests = []
        self.lock = threading.Lock()


def make_embedding_handler(state: EmbeddingState):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            try:
                json_body = json.loads(body.decode("utf-8"))
            except Exception:
                json_body = None
            with state.lock:
                state.requests.append(lib.RecordedRequest("POST", self.path, body, json_body))
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"stub embedding failure"}')

        def log_message(self, format, *args):
            return

    return Handler


def make_qdrant_handler(collection_name: str, config: dict):
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
            if self.path == f"/collections/{collection_name}":
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=Path, required=True, dest="script_path")
    parser.add_argument("--chunk-schema", type=Path, required=True, dest="chunk_schema_path")
    parser.add_argument("--config", type=Path, required=True, dest="config_path")
    parser.add_argument("--env-file", type=Path, required=True, dest="env_file_path")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    _ = args.chunk_schema_path

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        config = json.loads(json.dumps(lib.load_toml(args.config_path)))
        tokenizer_path = tmp_dir / "local_tokenizer.json"
        lib.write_local_tokenizer(tokenizer_path)
        config["sparse"]["tokenizer"]["source"] = str(tokenizer_path)
        config["sparse"]["tokenizer"].pop("revision", None)
        config_path = tmp_dir / "config.toml"
        lib.write_text(config_path, lib.dump_toml_document(config))

        effective_name = lib.derive_effective_collection_name(
            config["qdrant"]["collection"]["name"],
            config["sparse"]["strategy"]["kind"],
        )
        expected_request_count = 1 + config["embedding"]["retry"]["max_attempts"]
        embedding_state = EmbeddingState()
        embedding_server = lib.StubServer(make_embedding_handler(embedding_state))
        qdrant_server = lib.StubServer(make_qdrant_handler(effective_name, config))
        case_name = "embedding_retry_limit"

        chunks_path = tmp_dir / "chunks.jsonl"
        env_path = tmp_dir / ".env"
        chunks_path.write_text(json.dumps(lib.build_valid_chunk()) + "\n", encoding="utf-8")
        process = None
        try:
            qdrant_server.start()
            embedding_server.start()
            env_text = lib.read_text(args.env_file_path)
            env_text = lib.replace_env_value(env_text, "QDRANT_URL", qdrant_server.base_url)
            env_text = lib.replace_env_value(env_text, "OLLAMA_URL", embedding_server.base_url)
            lib.write_text(env_path, env_text)
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(args.script_path),
                    "--chunks",
                    str(chunks_path),
                    "--config",
                    str(config_path),
                    "--env-file",
                    str(env_path),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            deadline = time.time() + lib.TIMEOUT_SEC
            observed = 0
            while time.time() < deadline:
                with embedding_state.lock:
                    observed = len(embedding_state.requests)
                if observed >= expected_request_count:
                    break
                if process.poll() is not None:
                    break
                time.sleep(0.05)
            lib.terminate_process(process)
            with embedding_state.lock:
                observed = len(embedding_state.requests)
            ok = observed == expected_request_count
            if ok:
                print(f"OK [{case_name}]")
                print("cases=1 failed=0 passed=1")
                return
            stdout, stderr = process.communicate()
            print(f"FAIL [{case_name}]")
            print(f"error=expected {expected_request_count} embedding requests got {observed}")
            print(f"stdout={stdout.strip()}")
            print(f"stderr={stderr.strip()}")
            print("cases=1 failed=1 passed=0")
            raise SystemExit(1)
        finally:
            if process is not None:
                lib.terminate_process(process)
            embedding_server.stop()
            qdrant_server.stop()


if __name__ == "__main__":
    main()

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


class QdrantState:
    def __init__(self):
        self.requests = []
        self.lock = threading.Lock()


def make_qdrant_handler(state: QdrantState, collection_name: str):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            with state.lock:
                state.requests.append(lib.RecordedRequest("GET", self.path, b"", None))
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"error","error":"stub qdrant failure"}')

        def do_PUT(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            try:
                json_body = json.loads(body.decode("utf-8"))
            except Exception:
                json_body = None
            with state.lock:
                state.requests.append(lib.RecordedRequest("PUT", self.path, body, json_body))
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"error","error":"stub qdrant failure"}')

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
    effective_name = lib.derive_effective_collection_name(
        config["qdrant"]["collection"]["name"],
        config["sparse"]["strategy"]["kind"],
    )
    expected_request_count = config["qdrant"]["retry"]["max_attempts"]
    qdrant_state = QdrantState()
    qdrant_server = lib.StubServer(make_qdrant_handler(qdrant_state, effective_name))
    case_name = "qdrant_retry_limit"

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        chunks_path = tmp_dir / "chunks.jsonl"
        env_path = tmp_dir / ".env"
        chunks_path.write_text(json.dumps(lib.build_valid_chunk()) + "\n", encoding="utf-8")
        process = None
        try:
            qdrant_server.start()
            env_text = lib.read_text(args.env_file_path)
            env_text = lib.replace_env_value(env_text, "QDRANT_URL", qdrant_server.base_url)
            lib.write_text(env_path, env_text)
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(args.script_path),
                    "--chunks",
                    str(chunks_path),
                    "--config",
                    str(args.config_path),
                    "--env-file",
                    str(env_path),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            deadline = time.time() + lib.TIMEOUT_SEC
            observed = 0
            expected_path = f"/collections/{effective_name}"
            while time.time() < deadline:
                with qdrant_state.lock:
                    observed = sum(1 for request in qdrant_state.requests if request.method == "GET" and request.path == expected_path)
                if observed >= expected_request_count or process.poll() is not None:
                    break
                time.sleep(0.05)
            lib.terminate_process(process)
            ok = observed == expected_request_count
            if ok:
                print(f"OK [{case_name}]")
                print("cases=1 failed=0 passed=1")
                return
            stdout, stderr = process.communicate()
            print(f"FAIL [{case_name}]")
            print(f"error=expected {expected_request_count} qdrant requests got {observed}")
            print(f"stdout={stdout.strip()}")
            print(f"stderr={stderr.strip()}")
            print("cases=1 failed=1 passed=0")
            raise SystemExit(1)
        finally:
            if process is not None:
                lib.terminate_process(process)
            qdrant_server.stop()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import argparse
import json
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


TIMEOUT_SEC = 10.0


def load_toml(path: Path):
    try:
        import tomllib as parser  # type: ignore
    except ModuleNotFoundError:
        import tomli as parser  # type: ignore
    with path.open("rb") as handle:
        return parser.load(handle)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def replace_env_value(env_text: str, key: str, value: str) -> str:
    lines = env_text.splitlines()
    replaced = False
    new_lines = []
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}")
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        new_lines.append(f"{key}={value}")
    return "\n".join(new_lines) + "\n"


def build_valid_chunk() -> dict:
    return {
        "schema_version": 1,
        "doc_id": "2e9b0ce6-b07e-4b1c-9918-289627c74577",
        "chunk_id": "b48b106e-58ab-4e14-a0ae-c46b607e9e24",
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


class RecordedRequest:
    def __init__(self, method: str, path: str, body: bytes, json_body):
        self.method = method
        self.path = path
        self.body = body
        self.json_body = json_body


class StubServer:
    def __init__(self, handler_factory):
        self.handler_factory = handler_factory
        self.server = None
        self.thread = None

    def start(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.handler_factory)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.wait_ready()

    def wait_ready(self):
        deadline = time.time() + TIMEOUT_SEC
        while time.time() < deadline:
            try:
                with socket.create_connection(self.server.server_address, timeout=0.2):
                    return
            except OSError:
                time.sleep(0.05)
        raise RuntimeError("stub service did not become ready")

    @property
    def base_url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def stop(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        if self.thread is not None:
            self.thread.join(timeout=1.0)


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
                state.requests.append(RecordedRequest("POST", self.path, body, json_body))
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"stub embedding failure"}')

        def log_message(self, format, *args):
            return

    return Handler


def make_qdrant_handler(collection_name: str):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == f"/collections/{collection_name}":
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"error","error":"collection missing"}')
                return
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"error","error":"unexpected GET"}')

        def do_PUT(self):
            if self.path == f"/collections/{collection_name}":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok","result":{"status":"acknowledged","operation_id":1}}')
                return
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"error","error":"unexpected PUT"}')

        def log_message(self, format, *args):
            return

    return Handler


def terminate_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2.0)


def run_case(script_path: Path, chunk_schema_path: Path, config_path: Path, env_file_path: Path):
    _ = chunk_schema_path
    config = load_toml(config_path)
    expected_request_count = 1 + config["embedding"]["retry"]["max_attempts"]
    collection_name = config["qdrant"]["collection"]["name"]

    case_name = "embedding_retry_limit"
    embedding_state = EmbeddingState()
    embedding_server = StubServer(make_embedding_handler(embedding_state))
    qdrant_server = StubServer(make_qdrant_handler(collection_name))

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        chunks_path = tmp_dir / "chunks.jsonl"
        mutated_env_path = tmp_dir / ".env"

        chunks_path.write_text(json.dumps(build_valid_chunk()) + "\n", encoding="utf-8")

        process = None
        try:
            qdrant_server.start()
            embedding_server.start()

            env_text = read_text(env_file_path)
            env_text = replace_env_value(env_text, "QDRANT_URL", qdrant_server.base_url)
            env_text = replace_env_value(env_text, "OLLAMA_URL", embedding_server.base_url)
            write_text(mutated_env_path, env_text)

            process = subprocess.Popen(
                [
                    sys.executable,
                    str(script_path),
                    "--chunks",
                    str(chunks_path),
                    "--config",
                    str(config_path),
                    "--env-file",
                    str(mutated_env_path),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            deadline = time.time() + TIMEOUT_SEC
            while time.time() < deadline:
                with embedding_state.lock:
                    observed_request_count = len(embedding_state.requests)
                if observed_request_count >= expected_request_count:
                    break
                if process.poll() is not None:
                    stdout, stderr = process.communicate()
                    return (
                        False,
                        case_name,
                        {
                            "error": "subprocess exited before reaching expected request count",
                            "observed_request_count": observed_request_count,
                            "expected_request_count": expected_request_count,
                            "stdout": stdout.strip(),
                            "stderr": stderr.strip(),
                        },
                    )
                time.sleep(0.05)
            else:
                return (
                    False,
                    case_name,
                    {
                        "error": "expected request count was not reached before timeout",
                        "observed_request_count": len(embedding_state.requests),
                        "expected_request_count": expected_request_count,
                    },
                )

            terminate_process(process)
            with embedding_state.lock:
                observed_request_count = len(embedding_state.requests)

            if observed_request_count != expected_request_count:
                return (
                    False,
                    case_name,
                    {
                        "error": "observed request count does not match expected request count",
                        "observed_request_count": observed_request_count,
                        "expected_request_count": expected_request_count,
                    },
                )
            return True, case_name, {}
        finally:
            if process is not None:
                terminate_process(process)
            embedding_server.stop()
            qdrant_server.stop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=Path, required=True, dest="script_path")
    parser.add_argument("--chunk-schema", type=Path, required=True, dest="chunk_schema_path")
    parser.add_argument("--config", type=Path, required=True, dest="config_path")
    parser.add_argument("--env-file", type=Path, required=True, dest="env_file_path")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    passed, case_name, details = run_case(
        script_path=args.script_path,
        chunk_schema_path=args.chunk_schema_path,
        config_path=args.config_path,
        env_file_path=args.env_file_path,
    )

    failed = 0
    passed_count = 0
    if passed:
        passed_count = 1
        print(f"OK [{case_name}]")
    else:
        failed = 1
        print(f"FAIL [{case_name}]")
        print(f"error={details['error']}")
        print(f"observed_request_count={details['observed_request_count']}")
        print(f"expected_request_count={details['expected_request_count']}")
        if args.verbose:
            if details.get("stdout"):
                print(f"stdout={details['stdout']}")
            if details.get("stderr"):
                print(f"stderr={details['stderr']}")

    print(f"cases=1 failed={failed} passed={passed_count}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

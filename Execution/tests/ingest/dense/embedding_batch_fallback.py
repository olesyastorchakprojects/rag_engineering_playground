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
    raise TypeError(f"unsupported TOML value: {type(value).__name__}")


def dump_toml_document(data):
    lines = []

    def emit_table(path_parts, table):
        if path_parts:
            lines.append(f"[{'.'.join(path_parts)}]")
        scalar_keys = []
        nested_keys = []
        for key, value in table.items():
            if isinstance(value, dict):
                nested_keys.append((key, value))
            else:
                scalar_keys.append((key, value))
        for key, value in scalar_keys:
            lines.append(f"{key} = {dump_toml_value(value)}")
        if scalar_keys and nested_keys:
            lines.append("")
        for index, (key, value) in enumerate(nested_keys):
            emit_table(path_parts + [key], value)
            if index != len(nested_keys) - 1:
                lines.append("")

    emit_table([], data)
    return "\n".join(lines) + "\n"


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


def build_valid_chunk(chunk_index: int, chunk_id: str) -> dict:
    return {
        "schema_version": 1,
        "doc_id": "2e9b0ce6-b07e-4b1c-9918-289627c74577",
        "chunk_id": chunk_id,
        "url": "local://Understanding-Distributed-Systems-2nd-Edition.pdf",
        "document_title": "Understanding Distributed Systems (2nd Edition)",
        "section_title": "Introduction",
        "section_path": ["Introduction", "Introduction"],
        "chunk_index": chunk_index,
        "page_start": 19,
        "page_end": 19,
        "tags": ["distributed-systems", "book", "architecture"],
        "content_hash": f"sha256:test-content-hash-{chunk_index}",
        "chunking_version": "v1",
        "chunk_created_at": "2026-02-17T09:00:00Z",
        "text": f"Chunk text {chunk_index}",
    }


class RecordedRequest:
    def __init__(self, method: str, path: str, json_body):
        self.method = method
        self.path = path
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


class QdrantState:
    def __init__(self):
        self.requests = []
        self.lock = threading.Lock()


def make_embedding_handler(state: EmbeddingState, dimension: int):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            try:
                json_body = json.loads(body.decode("utf-8"))
            except Exception:
                json_body = None
            with state.lock:
                state.requests.append(RecordedRequest("POST", self.path, json_body))

            input_items = []
            if isinstance(json_body, dict) and isinstance(json_body.get("input"), list):
                input_items = json_body["input"]

            if len(input_items) == 2:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error":"stub embedding batch failure"}')
                return

            embeddings = [[0.0] * dimension for _ in input_items]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"embeddings": embeddings}).encode("utf-8"))

        def log_message(self, format, *args):
            return

    return Handler


def make_qdrant_handler(state: QdrantState, collection_name: str):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            with state.lock:
                state.requests.append(RecordedRequest("GET", self.path, None))
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
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            try:
                json_body = json.loads(body.decode("utf-8"))
            except Exception:
                json_body = None
            with state.lock:
                state.requests.append(RecordedRequest("PUT", self.path, json_body))
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
    config["embedding"]["transport"]["max_batch_size"] = 2
    collection_name = config["qdrant"]["collection"]["name"]
    dimension = config["embedding"]["model"]["dimension"]

    initial_batch_item_count = 2
    retry_attempts = config["embedding"]["retry"]["max_attempts"]
    expected_input_lengths = ([initial_batch_item_count] * retry_attempts) + [1, 1]
    case_name = "embedding_batch_fallback"

    embedding_state = EmbeddingState()
    qdrant_state = QdrantState()
    embedding_server = StubServer(make_embedding_handler(embedding_state, dimension))
    qdrant_server = StubServer(make_qdrant_handler(qdrant_state, collection_name))

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        chunks_path = tmp_dir / "chunks.jsonl"
        mutated_config_path = tmp_dir / "config.toml"
        mutated_env_path = tmp_dir / ".env"
        process = None
        try:
            chunks = [
                build_valid_chunk(0, "b48b106e-58ab-4e14-a0ae-c46b607e9e24"),
                build_valid_chunk(1, "62bc1c1f-6e1b-4f4b-8d74-4dd7b886e88d"),
            ]
            chunks_path.write_text(
                "".join(json.dumps(chunk) + "\n" for chunk in chunks),
                encoding="utf-8",
            )
            write_text(mutated_config_path, dump_toml_document(config))

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
                    str(mutated_config_path),
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
                    observed_lengths = [
                        len(request.json_body.get("input", []))
                        for request in embedding_state.requests
                        if request.method == "POST" and request.path == "/api/embed" and isinstance(request.json_body, dict)
                    ]
                if observed_lengths[: len(expected_input_lengths)] == expected_input_lengths:
                    if len(observed_lengths) >= len(expected_input_lengths):
                        break
                if process.poll() is not None:
                    stdout, stderr = process.communicate()
                    return (
                        False,
                        case_name,
                        {
                            "error": "subprocess exited before reaching expected input lengths sequence",
                            "observed_request_count": len(observed_lengths),
                            "observed_input_lengths": observed_lengths,
                            "expected_input_lengths": expected_input_lengths,
                            "stdout": stdout.strip(),
                            "stderr": stderr.strip(),
                        },
                    )
                time.sleep(0.05)
            else:
                with embedding_state.lock:
                    observed_lengths = [
                        len(request.json_body.get("input", []))
                        for request in embedding_state.requests
                        if request.method == "POST" and request.path == "/api/embed" and isinstance(request.json_body, dict)
                    ]
                return (
                    False,
                    case_name,
                    {
                        "error": "expected input lengths sequence was not reached before timeout",
                        "observed_request_count": len(observed_lengths),
                        "observed_input_lengths": observed_lengths,
                        "expected_input_lengths": expected_input_lengths,
                    },
                )

            terminate_process(process)
            with embedding_state.lock:
                observed_lengths = [
                    len(request.json_body.get("input", []))
                    for request in embedding_state.requests
                    if request.method == "POST" and request.path == "/api/embed" and isinstance(request.json_body, dict)
                ]
            if observed_lengths[: len(expected_input_lengths)] != expected_input_lengths:
                return (
                    False,
                    case_name,
                    {
                        "error": "observed input lengths sequence does not match expected sequence",
                        "observed_request_count": len(observed_lengths),
                        "observed_input_lengths": observed_lengths,
                        "expected_input_lengths": expected_input_lengths,
                    },
                )
            if len(observed_lengths) != len(expected_input_lengths):
                return (
                    False,
                    case_name,
                    {
                        "error": "observed request count does not match expected sequence length",
                        "observed_request_count": len(observed_lengths),
                        "observed_input_lengths": observed_lengths,
                        "expected_input_lengths": expected_input_lengths,
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
        args.script_path,
        args.chunk_schema_path,
        args.config_path,
        args.env_file_path,
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
        print(f"observed_input_lengths={details['observed_input_lengths']}")
        if args.verbose:
            print(f"expected_input_lengths={details['expected_input_lengths']}")
            if details.get("stdout"):
                print(f"stdout={details['stdout']}")
            if details.get("stderr"):
                print(f"stderr={details['stderr']}")

    print(f"cases=1 failed={failed} passed={passed_count}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

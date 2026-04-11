#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler
from pathlib import Path


THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))
import _hybrid_testlib as lib  # noqa: E402


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
            self.end_headers()

        def do_PUT(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok","result":{"status":"acknowledged","operation_id":1}}')

        def log_message(self, format, *args):
            return

    return Handler


def run_ingest(script_path: Path, chunks_path: Path, config_path: Path, env_path: Path):
    return subprocess.run(
        [sys.executable, str(script_path), "--chunks", str(chunks_path), "--config", str(config_path), "--env-file", str(env_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=lib.REPO_ROOT,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=Path, required=True, dest="script_path")
    parser.add_argument("--chunk-schema", type=Path, required=True, dest="chunk_schema_path")
    parser.add_argument("--config", type=Path, required=True, dest="config_path")
    parser.add_argument("--env-file", type=Path, required=True, dest="env_file_path")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    _ = args.chunk_schema_path

    base_config = lib.load_toml(args.config_path)
    effective_name = lib.derive_effective_collection_name(base_config["qdrant"]["collection"]["name"], base_config["sparse"]["strategy"]["kind"])
    embedding_server = lib.StubServer(make_embedding_handler(base_config["embedding"]["model"]["dimension"]))
    qdrant_server = lib.StubServer(make_qdrant_handler(effective_name))

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        chunks_path = tmp_dir / "chunks.jsonl"
        config_path = tmp_dir / "config.toml"
        env_path = tmp_dir / ".env"
        vocabulary_path = lib.vocabulary_artifact_path(base_config["qdrant"]["collection"]["name"])
        manifest_path = lib.manifest_artifact_path("2026-04-02T00-00-00Z_00000000-0000-0000-0000-000000000000")
        chunks = [lib.build_valid_chunk(text="raft leader election"), lib.build_valid_chunk(chunk_index=1, text="leader commit index")]
        lib.write_chunks_jsonl(chunks_path, chunks)
        config = json.loads(json.dumps(base_config))
        config["artifacts"]["manifest_path"] = lib.repo_root_relative_str(manifest_path)
        lib.write_text(config_path, lib.dump_toml_document(config))
        env_text = lib.read_text(args.env_file_path)
        try:
            embedding_server.start()
            qdrant_server.start()
            env_text = lib.replace_env_value(env_text, "QDRANT_URL", qdrant_server.base_url)
            env_text = lib.replace_env_value(env_text, "OLLAMA_URL", embedding_server.base_url)
            lib.write_text(env_path, env_text)

            first = run_ingest(args.script_path, chunks_path, config_path, env_path)
            first_exists = vocabulary_path.exists()
            first_bytes = vocabulary_path.read_bytes() if first_exists else b""

            second = run_ingest(args.script_path, chunks_path, config_path, env_path)
            second_bytes = vocabulary_path.read_bytes() if vocabulary_path.exists() else b""

            incompatible = lib.build_vocabulary_artifact(config, [lib.build_valid_chunk(text="different tokens")])
            incompatible["collection_name"] = "different_base_name"
            vocabulary_path.write_text(json.dumps(incompatible, indent=2), encoding="utf-8")
            third = run_ingest(args.script_path, chunks_path, config_path, env_path)

            ok = (
                first.returncode == 0
                and second.returncode == 0
                and first_exists
                and first_bytes == second_bytes
                and third.returncode == 1
            )
            if ok:
                print("OK [vocabulary_bootstrap_and_reuse]")
                print("cases=1 failed=0 passed=1")
                return
            print("FAIL [vocabulary_bootstrap_and_reuse]")
            print(f"error=unexpected lifecycle rc=({first.returncode},{second.returncode},{third.returncode}) exists={first_exists} byte_stable={first_bytes == second_bytes}")
            print(f"first_stdout={first.stdout.strip()}")
            print(f"second_stdout={second.stdout.strip()}")
            print(f"third_stdout={third.stdout.strip()}")
            print("cases=1 failed=1 passed=0")
            raise SystemExit(1)
        finally:
            lib.cleanup_artifact_file(vocabulary_path)
            lib.cleanup_artifact_file(manifest_path)
            embedding_server.stop()
            qdrant_server.stop()


if __name__ == "__main__":
    main()

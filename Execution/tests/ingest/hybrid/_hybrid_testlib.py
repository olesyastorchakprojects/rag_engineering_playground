#!/usr/bin/env python3
import json
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


TIMEOUT_SEC = 10.0
REPO_ROOT = Path(__file__).resolve().parents[4]
HYBRID_ARTIFACTS_ROOT = REPO_ROOT / "Execution" / "ingest" / "hybrid" / "artifacts"


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


def parse_env_file(path: Path):
    parsed = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "" or stripped.startswith("#"):
            continue
        key, value = line.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


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


def dump_toml_value(value, indent=""):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value == int(value):
            return f"{value:.1f}"
        return repr(value)
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


def build_valid_chunk(chunk_index: int = 0, chunk_id: str | None = None, text: str = "Hybrid ingest test chunk."):
    if chunk_id is None:
        chunk_id = str(uuid.uuid4())
    return {
        "schema_version": 1,
        "doc_id": "2e9b0ce6-b07e-4b1c-9918-289627c74577",
        "chunk_id": chunk_id,
        "url": "local://Understanding-Distributed-Systems-2nd-Edition.pdf",
        "document_title": "Understanding Distributed Systems (2nd Edition)",
        "section_title": f"Section {chunk_index}",
        "section_path": ["Introduction", f"Section {chunk_index}"],
        "chunk_index": chunk_index,
        "page_start": 19 + chunk_index,
        "page_end": 19 + chunk_index,
        "tags": ["distributed-systems", "book", "architecture"],
        "content_hash": f"sha256:hybrid-test-{chunk_index}",
        "chunking_version": "v1",
        "chunk_created_at": "2026-02-17T09:00:00Z",
        "text": text,
    }


def write_local_tokenizer(path: Path) -> Path:
    try:
        from tokenizers import Tokenizer
        from tokenizers.models import WordLevel
        from tokenizers.pre_tokenizers import Whitespace
    except ModuleNotFoundError as exc:
        raise RuntimeError("tokenizers package is required for hybrid test tokenizer fixtures") from exc

    tokenizer = Tokenizer(WordLevel({"unk": 0}, unk_token="unk"))
    tokenizer.pre_tokenizer = Whitespace()
    tokenizer.save(str(path))
    return path


def validate_chunk_contract(chunk: dict):
    required = [
        "schema_version",
        "doc_id",
        "chunk_id",
        "url",
        "document_title",
        "section_title",
        "section_path",
        "chunk_index",
        "page_start",
        "page_end",
        "tags",
        "content_hash",
        "chunking_version",
        "chunk_created_at",
        "text",
    ]
    for key in required:
        if key not in chunk:
            raise ValueError(f"missing chunk field {key}")
    if chunk["page_end"] < chunk["page_start"]:
        raise ValueError("chunk.page_end < chunk.page_start")
    if not isinstance(chunk["section_path"], list):
        raise ValueError("chunk.section_path must be list")
    if not isinstance(chunk["tags"], list):
        raise ValueError("chunk.tags must be list")


def derive_strategy_suffix(kind: str) -> str:
    mapping = {
        "bag_of_words": "bow",
        "bm25_like": "bm25",
    }
    if kind not in mapping:
        raise ValueError(f"unsupported sparse strategy kind {kind}")
    return mapping[kind]


def validate_base_collection_name(name: str) -> None:
    if not isinstance(name, str) or name.strip() == "":
        raise ValueError("qdrant.collection.name must be non-empty")
    if name.endswith("_bow"):
        raise ValueError("qdrant.collection.name must not end with _bow")
    if name.endswith("_bm25"):
        raise ValueError("qdrant.collection.name must not end with _bm25")
    if name.endswith("_"):
        raise ValueError("qdrant.collection.name must not end with _")


def derive_effective_collection_name(base_name: str, strategy_kind: str) -> str:
    validate_base_collection_name(base_name)
    return f"{base_name}_{derive_strategy_suffix(strategy_kind)}"


def vocabulary_name(base_collection_name: str) -> str:
    return f"{base_collection_name}__sparse_vocabulary"


def vocabulary_basename(base_collection_name: str) -> str:
    return f"{vocabulary_name(base_collection_name)}.json"


def term_stats_basename(effective_collection_name: str) -> str:
    return f"{effective_collection_name}__term_stats.json"


def manifest_basename() -> str:
    return "run_manifest.json"


def repo_root_relative_str(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def vocabulary_artifact_path(base_collection_name: str) -> Path:
    return HYBRID_ARTIFACTS_ROOT / "vocabularies" / vocabulary_basename(base_collection_name)


def term_stats_artifact_path(effective_collection_name: str) -> Path:
    return HYBRID_ARTIFACTS_ROOT / "term_stats" / term_stats_basename(effective_collection_name)


def manifest_artifact_path(run_dir_name: str) -> Path:
    return HYBRID_ARTIFACTS_ROOT / "manifests" / run_dir_name / manifest_basename()


def log_artifact_path(name: str) -> Path:
    return HYBRID_ARTIFACTS_ROOT / "logs" / name


def remove_file_if_exists(path: Path) -> None:
    if path.exists():
        path.unlink()


def remove_empty_parents(path: Path, stop_at: Path) -> None:
    current = path.parent
    while current != stop_at and current.is_dir():
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def cleanup_artifact_file(path: Path) -> None:
    remove_file_if_exists(path)
    remove_empty_parents(path, HYBRID_ARTIFACTS_ROOT)


def normalize_tokens(text: str, lowercase: bool, min_token_length: int):
    tokens = re.findall(r"[A-Za-z0-9]+", text)
    normalized = []
    for token in tokens:
        candidate = token.lower() if lowercase else token
        if len(candidate) < min_token_length:
            continue
        normalized.append(candidate)
    return normalized


def build_vocabulary_artifact(config: dict, chunks):
    seen = {}
    tokens = []
    for chunk in chunks:
        normalized = normalize_tokens(
            chunk["text"],
            config["sparse"]["preprocessing"]["lowercase"],
            config["sparse"]["preprocessing"]["min_token_length"],
        )
        for token in normalized:
            if token not in seen:
                token_id = len(tokens)
                seen[token] = token_id
                tokens.append({"token": token, "token_id": token_id})
    tokenizer = {
        "library": config["sparse"]["tokenizer"]["library"],
        "source": config["sparse"]["tokenizer"]["source"],
    }
    revision = config["sparse"]["tokenizer"].get("revision")
    if revision is not None:
        tokenizer["revision"] = revision
    base_name = config["qdrant"]["collection"]["name"]
    return {
        "vocabulary_name": vocabulary_name(base_name),
        "collection_name": base_name,
        "text_processing": {
            "lowercase": config["sparse"]["preprocessing"]["lowercase"],
            "min_token_length": config["sparse"]["preprocessing"]["min_token_length"],
        },
        "tokenizer": tokenizer,
        "created_at": "2026-04-02T00:00:00Z",
        "tokens": tokens,
    }


def vocabulary_token_map(vocabulary_artifact: dict):
    mapping = {}
    for entry in vocabulary_artifact["tokens"]:
        mapping[entry["token"]] = entry["token_id"]
    return mapping


def build_bow_sparse_vector(config: dict, text: str, vocabulary_artifact: dict, mode: str = "document"):
    token_map = vocabulary_token_map(vocabulary_artifact)
    counts = {}
    oov_count = 0
    for token in normalize_tokens(
        text,
        config["sparse"]["preprocessing"]["lowercase"],
        config["sparse"]["preprocessing"]["min_token_length"],
    ):
        if token not in token_map:
            oov_count += 1
            continue
        token_id = token_map[token]
        if mode == "query":
            counts[token_id] = 1.0
        else:
            counts[token_id] = counts.get(token_id, 0.0) + 1.0
    indices = sorted(counts.keys())
    values = [counts[token_id] for token_id in indices]
    return {"indices": indices, "values": values, "oov_count": oov_count}


def build_term_stats_artifact(config: dict, vocabulary_artifact: dict, chunks):
    token_map = vocabulary_token_map(vocabulary_artifact)
    effective_name = derive_effective_collection_name(
        config["qdrant"]["collection"]["name"],
        config["sparse"]["strategy"]["kind"],
    )
    doc_freq = {}
    retained_lengths = []
    for chunk in chunks:
        retained_ids = []
        for token in normalize_tokens(
            chunk["text"],
            config["sparse"]["preprocessing"]["lowercase"],
            config["sparse"]["preprocessing"]["min_token_length"],
        ):
            token_id = token_map.get(token)
            if token_id is not None:
                retained_ids.append(token_id)
        retained_lengths.append(len(retained_ids))
        for token_id in sorted(set(retained_ids)):
            key = str(token_id)
            doc_freq[key] = doc_freq.get(key, 0) + 1
    average_document_length = sum(retained_lengths) / max(len(retained_lengths), 1)
    return {
        "collection_name": effective_name,
        "sparse_strategy": {
            "kind": config["sparse"]["strategy"]["kind"],
            "version": config["sparse"]["strategy"]["version"],
        },
        "vocabulary_name": vocabulary_artifact["vocabulary_name"],
        "document_count": len(chunks),
        "average_document_length": average_document_length,
        "document_frequency_by_token_id": doc_freq,
        "created_at": "2026-04-02T00:00:00Z",
    }


def compute_point_id(config: dict, chunk: dict) -> str:
    namespace_uuid = uuid.UUID(config["qdrant"]["point_id"]["namespace_uuid"])
    return str(uuid.uuid5(namespace_uuid, chunk["chunk_id"]))


def is_valid_iso_utc_timestamp(value) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        return True
    except ValueError:
        return False


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
    if status_code < 200 or status_code >= 300 or not isinstance(json_body, dict):
        raise RuntimeError("qdrant unavailable")


def check_embedding_available(base_url: str, model_name: str):
    status_code, _, json_body = send_json_request(
        "POST",
        base_url.rstrip("/") + "/api/embed",
        {"model": model_name, "input": ["availability probe"]},
        timeout_sec=60,
    )
    if status_code < 200 or status_code >= 300 or not isinstance(json_body, dict):
        raise RuntimeError("embedding service unavailable")


def get_collection(qdrant_url: str, collection_name: str):
    quoted_name = urllib.parse.quote(collection_name, safe="")
    return send_json_request("GET", qdrant_url.rstrip("/") + f"/collections/{quoted_name}")


def delete_collection(qdrant_url: str, collection_name: str):
    quoted_name = urllib.parse.quote(collection_name, safe="")
    return send_json_request("DELETE", qdrant_url.rstrip("/") + f"/collections/{quoted_name}")


def retrieve_points(qdrant_url: str, collection_name: str, point_ids, with_payload: bool = True, with_vector: bool = True):
    quoted_name = urllib.parse.quote(collection_name, safe="")
    payload = {
        "ids": list(point_ids),
        "with_payload": with_payload,
        "with_vector": with_vector,
    }
    return send_json_request("POST", qdrant_url.rstrip("/") + f"/collections/{quoted_name}/points", payload)


def create_hybrid_collection(qdrant_url: str, config: dict, metadata_override=None, sparse_vectors_override=Ellipsis, vectors_override=None):
    effective_name = derive_effective_collection_name(
        config["qdrant"]["collection"]["name"],
        config["sparse"]["strategy"]["kind"],
    )
    quoted_name = urllib.parse.quote(effective_name, safe="")
    dense_name = config["qdrant"]["collection"]["dense_vector_name"]
    sparse_name = config["qdrant"]["collection"]["sparse_vector_name"]
    vectors = vectors_override
    if vectors is None:
        vectors = {
            dense_name: {
                "size": config["embedding"]["model"]["dimension"],
                "distance": config["qdrant"]["collection"]["distance"],
            }
        }
    sparse_vectors = sparse_vectors_override
    if sparse_vectors is Ellipsis:
        sparse_vectors = {
            sparse_name: {}
        }
    metadata = metadata_override
    if metadata is None:
        vocabulary_identity = build_vocabulary_identity(config)
        metadata = {
            "embedding_model_name": config["embedding"]["model"]["name"],
            "sparse_strategy_kind": config["sparse"]["strategy"]["kind"],
            "sparse_strategy_version": config["sparse"]["strategy"]["version"],
            "corpus_version": config["pipeline"]["corpus_version"],
            "vocabulary_identity": vocabulary_identity,
        }
    body = {
        "vectors": vectors,
        "sparse_vectors": sparse_vectors,
        "metadata": metadata,
    }
    return send_json_request("PUT", qdrant_url.rstrip("/") + f"/collections/{quoted_name}", body)


def build_vocabulary_identity(config: dict):
    identity = {
        "collection_name": config["qdrant"]["collection"]["name"],
        "tokenizer_library": config["sparse"]["tokenizer"]["library"],
        "tokenizer_source": config["sparse"]["tokenizer"]["source"],
        "preprocessing_kind": config["sparse"]["preprocessing"]["kind"],
        "lowercase": config["sparse"]["preprocessing"]["lowercase"],
        "min_token_length": config["sparse"]["preprocessing"]["min_token_length"],
    }
    revision = config["sparse"]["tokenizer"].get("revision")
    if revision is not None:
        identity["tokenizer_revision"] = revision
    return identity


def extract_hybrid_collection_fields(collection_json_body):
    fields = {
        "status": None,
        "points_count": None,
        "dense_vectors": None,
        "sparse_vectors": None,
        "metadata": None,
    }
    if not isinstance(collection_json_body, dict):
        return fields
    fields["status"] = collection_json_body.get("status")
    result = collection_json_body.get("result")
    if not isinstance(result, dict):
        return fields
    fields["points_count"] = result.get("points_count")
    config_obj = result.get("config")
    if not isinstance(config_obj, dict):
        return fields
    params = config_obj.get("params")
    if isinstance(params, dict):
        fields["dense_vectors"] = params.get("vectors")
        fields["sparse_vectors"] = params.get("sparse_vectors")
    metadata = config_obj.get("metadata")
    if isinstance(metadata, dict):
        fields["metadata"] = metadata
    return fields


def extract_retrieved_point(point_json_body):
    if not isinstance(point_json_body, dict):
        return None
    result = point_json_body.get("result")
    if isinstance(result, list):
        if len(result) == 0:
            return None
        return result[0]
    return result


def run_ingest_subprocess(script_path: Path, chunks_path: Path, config_path: Path, env_file_path: Path):
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
        cwd=REPO_ROOT,
    )


def terminate_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2.0)


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


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_jsonl_lines(path: Path):
    if not path.exists():
        return []
    lines = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if stripped:
            lines.append(json.loads(stripped))
    return lines


def write_chunks_jsonl(path: Path, chunks):
    path.write_text("".join(json.dumps(chunk) + "\n" for chunk in chunks), encoding="utf-8")

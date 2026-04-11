#!/usr/bin/env python3
import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_SCHEMA_PATH = REPO_ROOT / "Execution" / "ingest" / "schemas" / "dense_ingest_config.schema.json"
ENV_SCHEMA_PATH = REPO_ROOT / "Execution" / "ingest" / "schemas" / "dense_ingest_env.schema.json"
CHUNK_SCHEMA_PATH = REPO_ROOT / "Execution" / "schemas" / "chunk.schema.json"


class IngestError(Exception):
    pass


class ConfigError(IngestError):
    pass


class EnvError(IngestError):
    pass


class ChunkValidationError(IngestError):
    pass


class ExternalServiceError(IngestError):
    pass


class InvalidResponseError(ExternalServiceError):
    pass


@dataclass
class RetryPolicy:
    max_attempts: int
    backoff: str


@dataclass
class AppConfig:
    pipeline_name: str
    chunk_schema_version: int
    ingest_config_version: str
    chunking_strategy: str
    embedding_model_name: str
    embedding_model_dimension: int
    embedding_text_source: str
    embedding_timeout_sec: int
    embedding_max_batch_size: int
    embedding_retry: RetryPolicy
    qdrant_collection_name: str
    qdrant_collection_distance: str
    qdrant_vector_name: str
    qdrant_create_if_missing: bool
    qdrant_point_id_strategy: str
    qdrant_point_id_namespace_uuid: str
    qdrant_point_id_format: str
    qdrant_timeout_sec: int
    qdrant_upsert_batch_size: int
    qdrant_retry: RetryPolicy
    idempotency_strategy: str
    fingerprint_fields: List[str]
    on_fingerprint_change: str
    on_metadata_change: str
    failed_chunk_log_path: str
    skipped_chunk_log_path: str


@dataclass
class EnvConfig:
    qdrant_url: str
    ollama_url: str


@dataclass
class ChunkContext:
    chunk: Dict[str, Any]
    chunk_index: int
    point_id: str
    ingest_status: Optional[str] = None


@dataclass
class ChunkWithEmbedding:
    chunk_context: ChunkContext
    embedding: List[float]


@dataclass
class Summary:
    total: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    failed: int = 0


@dataclass
class HttpResponse:
    status_code: int
    body_bytes: bytes
    body_text: str
    json_body: Optional[Any]


def log_runtime(message: str) -> None:
    print(f"[dense_ingest] {message}", file=sys.stderr, flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", required=True, dest="chunks_path")
    parser.add_argument("--config", required=True, dest="config_path")
    parser.add_argument("--env-file", required=True, dest="env_file_path")
    parser.add_argument("--report-only", action="store_true", dest="report_only")
    return parser.parse_args()


def load_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise IngestError(f"required file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise IngestError(f"invalid JSON file {path}: {exc}") from exc


def load_toml_module() -> Any:
    try:
        import tomllib as parser  # type: ignore
    except ModuleNotFoundError:
        try:
            import tomli as parser  # type: ignore
        except ModuleNotFoundError as exc:
            raise ConfigError("no TOML parser available") from exc
    return parser


def load_toml(path: Path) -> Dict[str, Any]:
    parser = load_toml_module()
    try:
        with path.open("rb") as handle:
            data = parser.load(handle)
    except FileNotFoundError as exc:
        raise ConfigError(f"config file not found: {path}") from exc
    except Exception as exc:
        raise ConfigError(f"config TOML parse error: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("config root must be an object")
    return data


def require_exact_keys(obj: Dict[str, Any], required: Iterable[str], optional: Iterable[str], path: str) -> None:
    required_set = set(required)
    optional_set = set(optional)
    actual_keys = set(obj.keys())
    missing = sorted(required_set - actual_keys)
    extra = sorted(actual_keys - required_set - optional_set)
    if missing:
        raise IngestError(f"{path} missing required keys: {', '.join(missing)}")
    if extra:
        raise IngestError(f"{path} has unexpected keys: {', '.join(extra)}")


def require_dict(value: Any, path: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise IngestError(f"{path} must be an object")
    return value


def require_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or value == "":
        raise IngestError(f"{path} must be a non-empty string")
    return value


def require_int(value: Any, path: str, minimum: Optional[int] = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise IngestError(f"{path} must be an integer")
    if minimum is not None and value < minimum:
        raise IngestError(f"{path} must be >= {minimum}")
    return value


def require_bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise IngestError(f"{path} must be a boolean")
    return value


def require_string_list(value: Any, path: str, min_items: int = 0) -> List[str]:
    if not isinstance(value, list):
        raise IngestError(f"{path} must be an array")
    items: List[str] = []
    for index, item in enumerate(value):
        items.append(require_string(item, f"{path}[{index}]"))
    if len(items) < min_items:
        raise IngestError(f"{path} must contain at least {min_items} item(s)")
    return items


def validate_uuid_string(value: str, path: str) -> None:
    try:
        uuid.UUID(value)
    except ValueError as exc:
        raise IngestError(f"{path} must be a canonical UUID") from exc


def validate_iso_datetime(value: str, path: str) -> None:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise IngestError(f"{path} must be an ISO 8601 datetime") from exc


def validate_config(config_data: Dict[str, Any]) -> AppConfig:
    schema = require_dict(load_json_file(CONFIG_SCHEMA_PATH), str(CONFIG_SCHEMA_PATH))
    if schema.get("type") != "object":
        raise ConfigError("config schema root must be object")

    try:
        require_exact_keys(config_data, schema["required"], (), "CONFIG_PATH")

        pipeline = require_dict(config_data["pipeline"], "CONFIG_PATH.pipeline")
        require_exact_keys(pipeline, ("name", "chunk_schema_version", "ingest_config_version", "corpus_version", "chunking_strategy"), (), "CONFIG_PATH.pipeline")

        embedding = require_dict(config_data["embedding"], "CONFIG_PATH.embedding")
        require_exact_keys(embedding, ("model", "input", "transport", "retry"), (), "CONFIG_PATH.embedding")
        embedding_model = require_dict(embedding["model"], "CONFIG_PATH.embedding.model")
        require_exact_keys(embedding_model, ("name", "dimension"), (), "CONFIG_PATH.embedding.model")
        embedding_input = require_dict(embedding["input"], "CONFIG_PATH.embedding.input")
        require_exact_keys(embedding_input, ("text_source",), (), "CONFIG_PATH.embedding.input")
        embedding_transport = require_dict(embedding["transport"], "CONFIG_PATH.embedding.transport")
        require_exact_keys(embedding_transport, ("timeout_sec", "max_batch_size"), (), "CONFIG_PATH.embedding.transport")
        embedding_retry = require_dict(embedding["retry"], "CONFIG_PATH.embedding.retry")
        require_exact_keys(embedding_retry, ("max_attempts", "backoff"), (), "CONFIG_PATH.embedding.retry")

        qdrant = require_dict(config_data["qdrant"], "CONFIG_PATH.qdrant")
        require_exact_keys(qdrant, ("collection", "point_id", "transport", "retry"), (), "CONFIG_PATH.qdrant")
        qdrant_collection = require_dict(qdrant["collection"], "CONFIG_PATH.qdrant.collection")
        require_exact_keys(
            qdrant_collection,
            ("name", "distance", "vector_name", "create_if_missing"),
            (),
            "CONFIG_PATH.qdrant.collection",
        )
        qdrant_point_id = require_dict(qdrant["point_id"], "CONFIG_PATH.qdrant.point_id")
        require_exact_keys(
            qdrant_point_id,
            ("strategy", "namespace_uuid", "format"),
            (),
            "CONFIG_PATH.qdrant.point_id",
        )
        qdrant_transport = require_dict(qdrant["transport"], "CONFIG_PATH.qdrant.transport")
        require_exact_keys(qdrant_transport, ("timeout_sec", "upsert_batch_size"), (), "CONFIG_PATH.qdrant.transport")
        qdrant_retry = require_dict(qdrant["retry"], "CONFIG_PATH.qdrant.retry")
        require_exact_keys(qdrant_retry, ("max_attempts", "backoff"), (), "CONFIG_PATH.qdrant.retry")

        idempotency = require_dict(config_data["idempotency"], "CONFIG_PATH.idempotency")
        require_exact_keys(
            idempotency,
            ("strategy", "fingerprint_fields", "on_fingerprint_change", "on_metadata_change"),
            (),
            "CONFIG_PATH.idempotency",
        )

        logging_cfg = require_dict(config_data["logging"], "CONFIG_PATH.logging")
        require_exact_keys(logging_cfg, ("failed_chunk_log_path", "skipped_chunk_log_path"), (), "CONFIG_PATH.logging")
    except IngestError as exc:
        raise ConfigError(str(exc)) from exc

    pipeline_name = require_string(pipeline["name"], "CONFIG_PATH.pipeline.name")
    chunk_schema_version = require_int(pipeline["chunk_schema_version"], "CONFIG_PATH.pipeline.chunk_schema_version", 1)
    ingest_config_version = require_string(pipeline["ingest_config_version"], "CONFIG_PATH.pipeline.ingest_config_version")
    chunking_strategy = require_string(pipeline["chunking_strategy"], "CONFIG_PATH.pipeline.chunking_strategy")
    if chunking_strategy not in ("structural", "fixed"):
        raise ConfigError("CONFIG_PATH.pipeline.chunking_strategy must be structural or fixed")

    embedding_model_name = require_string(embedding_model["name"], "CONFIG_PATH.embedding.model.name")
    embedding_model_dimension = require_int(embedding_model["dimension"], "CONFIG_PATH.embedding.model.dimension", 1)
    embedding_text_source = require_string(embedding_input["text_source"], "CONFIG_PATH.embedding.input.text_source")
    embedding_timeout_sec = require_int(embedding_transport["timeout_sec"], "CONFIG_PATH.embedding.transport.timeout_sec", 1)
    embedding_max_batch_size = require_int(
        embedding_transport["max_batch_size"], "CONFIG_PATH.embedding.transport.max_batch_size", 1
    )
    embedding_retry_max_attempts = require_int(
        embedding_retry["max_attempts"], "CONFIG_PATH.embedding.retry.max_attempts", 1
    )
    embedding_retry_backoff = require_string(embedding_retry["backoff"], "CONFIG_PATH.embedding.retry.backoff")
    if embedding_retry_backoff != "exponential":
        raise ConfigError("CONFIG_PATH.embedding.retry.backoff must be exponential")

    qdrant_collection_name = require_string(qdrant_collection["name"], "CONFIG_PATH.qdrant.collection.name")
    qdrant_collection_distance = require_string(
        qdrant_collection["distance"], "CONFIG_PATH.qdrant.collection.distance"
    )
    if qdrant_collection_distance not in ("Cosine", "Dot", "Euclid", "Manhattan"):
        raise ConfigError("CONFIG_PATH.qdrant.collection.distance has unsupported value")
    qdrant_vector_name = require_string(qdrant_collection["vector_name"], "CONFIG_PATH.qdrant.collection.vector_name")
    if qdrant_vector_name != "default":
        raise ConfigError("CONFIG_PATH.qdrant.collection.vector_name must be default")
    qdrant_create_if_missing = require_bool(
        qdrant_collection["create_if_missing"], "CONFIG_PATH.qdrant.collection.create_if_missing"
    )

    qdrant_point_id_strategy = require_string(qdrant_point_id["strategy"], "CONFIG_PATH.qdrant.point_id.strategy")
    if qdrant_point_id_strategy != "uuid5(chunk.chunk_id)":
        raise ConfigError("CONFIG_PATH.qdrant.point_id.strategy must be uuid5(chunk.chunk_id)")
    qdrant_point_id_namespace_uuid = require_string(
        qdrant_point_id["namespace_uuid"], "CONFIG_PATH.qdrant.point_id.namespace_uuid"
    )
    validate_uuid_string(qdrant_point_id_namespace_uuid, "CONFIG_PATH.qdrant.point_id.namespace_uuid")
    qdrant_point_id_format = require_string(qdrant_point_id["format"], "CONFIG_PATH.qdrant.point_id.format")
    if qdrant_point_id_format != "canonical_uuid":
        raise ConfigError("CONFIG_PATH.qdrant.point_id.format must be canonical_uuid")

    qdrant_timeout_sec = require_int(qdrant_transport["timeout_sec"], "CONFIG_PATH.qdrant.transport.timeout_sec", 1)
    qdrant_upsert_batch_size = require_int(
        qdrant_transport["upsert_batch_size"], "CONFIG_PATH.qdrant.transport.upsert_batch_size", 1
    )
    qdrant_retry_max_attempts = require_int(qdrant_retry["max_attempts"], "CONFIG_PATH.qdrant.retry.max_attempts", 1)
    qdrant_retry_backoff = require_string(qdrant_retry["backoff"], "CONFIG_PATH.qdrant.retry.backoff")
    if qdrant_retry_backoff != "exponential":
        raise ConfigError("CONFIG_PATH.qdrant.retry.backoff must be exponential")

    idempotency_strategy = require_string(idempotency["strategy"], "CONFIG_PATH.idempotency.strategy")
    if idempotency_strategy != "field_tuple_hash":
        raise ConfigError("CONFIG_PATH.idempotency.strategy must be field_tuple_hash")
    fingerprint_fields = require_string_list(
        idempotency["fingerprint_fields"], "CONFIG_PATH.idempotency.fingerprint_fields", min_items=1
    )
    on_fingerprint_change = require_string(
        idempotency["on_fingerprint_change"], "CONFIG_PATH.idempotency.on_fingerprint_change"
    )
    if on_fingerprint_change != "log_and_skip":
        raise ConfigError("CONFIG_PATH.idempotency.on_fingerprint_change must be log_and_skip")
    on_metadata_change = require_string(idempotency["on_metadata_change"], "CONFIG_PATH.idempotency.on_metadata_change")
    if on_metadata_change != "update_changed_fields":
        raise ConfigError("CONFIG_PATH.idempotency.on_metadata_change must be update_changed_fields")

    failed_chunk_log_path = require_string(logging_cfg["failed_chunk_log_path"], "CONFIG_PATH.logging.failed_chunk_log_path")
    skipped_chunk_log_path = require_string(
        logging_cfg["skipped_chunk_log_path"], "CONFIG_PATH.logging.skipped_chunk_log_path"
    )

    return AppConfig(
        pipeline_name=pipeline_name,
        chunk_schema_version=chunk_schema_version,
        ingest_config_version=ingest_config_version,
        chunking_strategy=chunking_strategy,
        embedding_model_name=embedding_model_name,
        embedding_model_dimension=embedding_model_dimension,
        embedding_text_source=embedding_text_source,
        embedding_timeout_sec=embedding_timeout_sec,
        embedding_max_batch_size=embedding_max_batch_size,
        embedding_retry=RetryPolicy(embedding_retry_max_attempts, embedding_retry_backoff),
        qdrant_collection_name=qdrant_collection_name,
        qdrant_collection_distance=qdrant_collection_distance,
        qdrant_vector_name=qdrant_vector_name,
        qdrant_create_if_missing=qdrant_create_if_missing,
        qdrant_point_id_strategy=qdrant_point_id_strategy,
        qdrant_point_id_namespace_uuid=qdrant_point_id_namespace_uuid,
        qdrant_point_id_format=qdrant_point_id_format,
        qdrant_timeout_sec=qdrant_timeout_sec,
        qdrant_upsert_batch_size=qdrant_upsert_batch_size,
        qdrant_retry=RetryPolicy(qdrant_retry_max_attempts, qdrant_retry_backoff),
        idempotency_strategy=idempotency_strategy,
        fingerprint_fields=fingerprint_fields,
        on_fingerprint_change=on_fingerprint_change,
        on_metadata_change=on_metadata_change,
        failed_chunk_log_path=failed_chunk_log_path,
        skipped_chunk_log_path=skipped_chunk_log_path,
    )


def validate_env(env_data: Dict[str, Any]) -> EnvConfig:
    schema = require_dict(load_json_file(ENV_SCHEMA_PATH), str(ENV_SCHEMA_PATH))
    required = schema.get("required", [])
    try:
        require_exact_keys(env_data, required, tuple(k for k in env_data.keys() if k not in required), "ENV_FILE_PATH")
    except IngestError as exc:
        raise EnvError(str(exc)) from exc

    qdrant_url = require_string(env_data.get("QDRANT_URL"), "ENV_FILE_PATH.QDRANT_URL")
    ollama_url = require_string(env_data.get("OLLAMA_URL"), "ENV_FILE_PATH.OLLAMA_URL")
    validate_base_url(qdrant_url, "ENV_FILE_PATH.QDRANT_URL")
    validate_base_url(ollama_url, "ENV_FILE_PATH.OLLAMA_URL")
    return EnvConfig(qdrant_url=qdrant_url.rstrip("/"), ollama_url=ollama_url.rstrip("/"))


def parse_env_file(path: Path) -> Dict[str, Any]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise EnvError(f"env file not found: {path}") from exc
    except OSError as exc:
        raise EnvError(f"env file read error: {exc}") from exc

    parsed: Dict[str, Any] = {}
    for line_number, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        if stripped == "" or stripped.startswith("#"):
            continue
        if "=" not in raw_line:
            raise EnvError(f"env file format error at line {line_number}")
        key, value = raw_line.split("=", 1)
        key = key.strip()
        if key == "":
            raise EnvError(f"env file format error at line {line_number}")
        parsed[key] = value.strip()
    return parsed


def validate_base_url(value: str, path: str) -> None:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in ("http", "https") or parsed.netloc == "":
        raise EnvError(f"{path} must be an absolute http(s) URL")


def read_chunks(path: Path) -> List[Tuple[int, Dict[str, Any]]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise IngestError(f"chunks file not found: {path}") from exc
    except OSError as exc:
        raise IngestError(f"chunks file read error: {exc}") from exc

    chunks: List[Tuple[int, Dict[str, Any]]] = []
    for line in lines:
        if line.strip() == "":
            continue
        chunk_index = len(chunks)
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ChunkValidationError(f"chunk_index={chunk_index} JSON parse error: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ChunkValidationError(f"chunk_index={chunk_index} chunk must be a JSON object")
        chunks.append((chunk_index, parsed))
    return chunks


def validate_chunk(chunk: Dict[str, Any], chunk_index: int, config: AppConfig) -> None:
    schema = require_dict(load_json_file(CHUNK_SCHEMA_PATH), str(CHUNK_SCHEMA_PATH))
    require_exact_keys(
        chunk,
        schema["required"],
        ("section_title", "section_path", "tags", "ingest"),
        f"chunk[{chunk_index}]",
    )

    require_int(chunk.get("schema_version"), f"chunk[{chunk_index}].schema_version", 1)
    if chunk["schema_version"] != config.chunk_schema_version:
        raise ChunkValidationError(
            f"chunk schema_version mismatch: expected {config.chunk_schema_version} actual {chunk['schema_version']}"
        )
    require_string(chunk.get("doc_id"), f"chunk[{chunk_index}].doc_id")
    require_string(chunk.get("chunk_id"), f"chunk[{chunk_index}].chunk_id")
    require_string(chunk.get("url"), f"chunk[{chunk_index}].url")
    require_string(chunk.get("document_title"), f"chunk[{chunk_index}].document_title")
    require_int(chunk.get("chunk_index"), f"chunk[{chunk_index}].chunk_index", 0)
    page_start = require_int(chunk.get("page_start"), f"chunk[{chunk_index}].page_start", 1)
    page_end = require_int(chunk.get("page_end"), f"chunk[{chunk_index}].page_end", 1)
    if page_end < page_start:
        raise ChunkValidationError(f"chunk[{chunk_index}] page_end must be >= page_start")
    require_string(chunk.get("content_hash"), f"chunk[{chunk_index}].content_hash")
    require_string(chunk.get("chunking_version"), f"chunk[{chunk_index}].chunking_version")
    validate_iso_datetime(require_string(chunk.get("chunk_created_at"), f"chunk[{chunk_index}].chunk_created_at"), f"chunk[{chunk_index}].chunk_created_at")
    require_string(chunk.get("text"), f"chunk[{chunk_index}].text")

    if "section_title" in chunk and chunk["section_title"] is not None:
        require_string(chunk["section_title"], f"chunk[{chunk_index}].section_title")
    if "section_path" in chunk:
        require_string_list(chunk["section_path"], f"chunk[{chunk_index}].section_path")
    if "tags" in chunk:
        require_string_list(chunk["tags"], f"chunk[{chunk_index}].tags")
    if "ingest" in chunk:
        ingest = require_dict(chunk["ingest"], f"chunk[{chunk_index}].ingest")
        require_exact_keys(
            ingest,
            (),
            ("embedding_model", "embedding_model_dimension", "ingest_config_version", "ingested_at"),
            f"chunk[{chunk_index}].ingest",
        )
        if "embedding_model" in ingest:
            require_string(ingest["embedding_model"], f"chunk[{chunk_index}].ingest.embedding_model")
        if "embedding_model_dimension" in ingest:
            require_int(ingest["embedding_model_dimension"], f"chunk[{chunk_index}].ingest.embedding_model_dimension")
        if "ingest_config_version" in ingest:
            require_string(ingest["ingest_config_version"], f"chunk[{chunk_index}].ingest.ingest_config_version")
        if "ingested_at" in ingest:
            validate_iso_datetime(
                require_string(ingest["ingested_at"], f"chunk[{chunk_index}].ingest.ingested_at"),
                f"chunk[{chunk_index}].ingest.ingested_at",
            )


def ensure_parent_dir(path_str: str) -> None:
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)


def append_jsonl(path_str: str, record: Dict[str, Any]) -> None:
    ensure_parent_dir(path_str)
    with Path(path_str).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")


def log_failed_chunk(config: AppConfig, chunk: Dict[str, Any], chunk_index: int, stage: str, error: str) -> None:
    append_jsonl(
        config.failed_chunk_log_path,
        {
            "chunk_id": chunk.get("chunk_id", ""),
            "chunk_index": chunk_index,
            "stage": stage,
            "error": error,
        },
    )


def log_skipped_chunk(config: AppConfig, chunk: Dict[str, Any], chunk_index: int) -> None:
    append_jsonl(
        config.skipped_chunk_log_path,
        {
            "chunk_id": chunk.get("chunk_id", ""),
            "chunk_index": chunk_index,
            "reason": "fingerprint_changed",
        },
    )


def now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_ingest_metadata(config: AppConfig, ingested_at: str) -> Dict[str, Any]:
    return {
        "embedding_model": config.embedding_model_name,
        "embedding_model_dimension": config.embedding_model_dimension,
        "ingest_config_version": config.ingest_config_version,
        "ingested_at": ingested_at,
    }


def inject_ingest_metadata(chunk: Dict[str, Any], ingest_metadata: Dict[str, Any]) -> Dict[str, Any]:
    updated = json.loads(json.dumps(chunk))
    updated["ingest"] = dict(ingest_metadata)
    return updated


def chunked(values: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def backoff_sleep(policy: RetryPolicy, attempt_index: int) -> None:
    if attempt_index >= policy.max_attempts - 1:
        return
    if policy.backoff != "exponential":
        return
    time.sleep(0.1 * (2 ** attempt_index))


def make_http_response(status_code: int, body_bytes: bytes) -> HttpResponse:
    try:
        body_text = body_bytes.decode("utf-8")
    except UnicodeDecodeError:
        body_text = body_bytes.decode("utf-8", errors="replace")
    json_body: Optional[Any] = None
    if body_text != "":
        try:
            json_body = json.loads(body_text)
        except json.JSONDecodeError:
            json_body = None
    return HttpResponse(status_code=status_code, body_bytes=body_bytes, body_text=body_text, json_body=json_body)


def format_service_error(response: Optional[HttpResponse], default_message: str) -> str:
    if response is None:
        return f"{default_message}; detailed error body unavailable"
    details: List[str] = [f"{default_message}; http_status={response.status_code}"]
    if isinstance(response.json_body, dict):
        found = False
        for key in ("error", "message", "status", "details"):
            if key in response.json_body:
                details.append(f"{key}={response.json_body[key]}")
                found = True
        if not found:
            details.append("detailed error body unavailable")
    elif response.body_text != "":
        details.append(f"body={response.body_text}")
    else:
        details.append("detailed error body unavailable")
    return " ".join(str(part) for part in details)


def send_json_request(method: str, url: str, payload: Optional[Dict[str, Any]], timeout_sec: int) -> HttpResponse:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url=url, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            return make_http_response(response.getcode(), response.read())
    except urllib.error.HTTPError as exc:
        return make_http_response(exc.code, exc.read())
    except urllib.error.URLError as exc:
        raise ExternalServiceError(f"transport error: {exc}") from exc


def request_with_retry(
    service_name: str,
    method: str,
    url: str,
    payload: Optional[Dict[str, Any]],
    timeout_sec: int,
    retry_policy: RetryPolicy,
    validate_success: Any,
) -> Any:
    last_error: Optional[Exception] = None
    for attempt_index in range(retry_policy.max_attempts):
        try:
            response = send_json_request(method, url, payload, timeout_sec)
            return validate_success(response)
        except (ExternalServiceError, InvalidResponseError) as exc:
            last_error = exc
            if attempt_index + 1 < retry_policy.max_attempts:
                log_runtime(
                    f"{service_name} retry attempt={attempt_index + 1}/{retry_policy.max_attempts} error={exc}"
                )
                backoff_sleep(retry_policy, attempt_index)
    assert last_error is not None
    raise last_error


def validate_embedding_response(response: HttpResponse, expected_count: int, expected_dimension: int) -> List[List[float]]:
    if not (200 <= response.status_code < 300):
        raise ExternalServiceError(format_service_error(response, "embedding request failed"))
    if not isinstance(response.json_body, dict):
        raise InvalidResponseError("embedding response body must be a JSON object")
    embeddings = response.json_body.get("embeddings")
    if not isinstance(embeddings, list):
        raise InvalidResponseError("embedding response.embeddings must be an array")
    if len(embeddings) != expected_count:
        raise InvalidResponseError("embedding response.embeddings length mismatch")

    validated: List[List[float]] = []
    for embedding_index, embedding in enumerate(embeddings):
        if not isinstance(embedding, list):
            raise InvalidResponseError(f"embedding[{embedding_index}] must be an array")
        if len(embedding) != expected_dimension:
            raise InvalidResponseError(f"embedding[{embedding_index}] dimension mismatch")
        vector: List[float] = []
        for value_index, value in enumerate(embedding):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise InvalidResponseError(f"embedding[{embedding_index}][{value_index}] must be JSON-number")
            vector.append(float(value))
        validated.append(vector)
    return validated


def validate_qdrant_ack_response(response: HttpResponse, operation_name: str) -> Dict[str, Any]:
    if not (200 <= response.status_code < 300):
        raise ExternalServiceError(format_service_error(response, f"{operation_name} failed"))
    if not isinstance(response.json_body, dict):
        raise InvalidResponseError(f"{operation_name} response must be JSON object")
    return response.json_body


def build_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + path


def qdrant_get_collection(config: AppConfig, env: EnvConfig) -> Tuple[str, Optional[Dict[str, Any]]]:
    url = build_url(env.qdrant_url, f"/collections/{urllib.parse.quote(config.qdrant_collection_name, safe='')}")

    def validate(response: HttpResponse) -> Tuple[str, Optional[Dict[str, Any]]]:
        if response.status_code == 404:
            return ("missing", None)
        if not (200 <= response.status_code < 300):
            raise ExternalServiceError(format_service_error(response, "qdrant collection lookup failed"))
        if not isinstance(response.json_body, dict):
            raise InvalidResponseError("qdrant collection lookup response must be JSON object")
        return ("exists", response.json_body)

    return request_with_retry(
        "qdrant_get_collection",
        "GET",
        url,
        None,
        config.qdrant_timeout_sec,
        config.qdrant_retry,
        validate,
    )


def qdrant_create_collection(config: AppConfig, env: EnvConfig) -> None:
    url = build_url(env.qdrant_url, f"/collections/{urllib.parse.quote(config.qdrant_collection_name, safe='')}")
    body = {
        "vectors": {
            "size": config.embedding_model_dimension,
            "distance": config.qdrant_collection_distance,
        },
        "metadata": {
            "embedding_model_name": config.embedding_model_name,
            "chunking_strategy": config.chunking_strategy,
        },
    }
    request_with_retry(
        "qdrant_create_collection",
        "PUT",
        url,
        body,
        config.qdrant_timeout_sec,
        config.qdrant_retry,
        lambda response: validate_qdrant_ack_response(response, "qdrant create collection"),
    )


def extract_collection_compatibility_errors(config: AppConfig, collection_body: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    result = collection_body.get("result")
    if not isinstance(result, dict):
        errors.append("collection result missing")
        log_runtime("collection compatibility check=result_object actual=missing")
        return errors

    config_obj = result.get("config")
    if not isinstance(config_obj, dict):
        errors.append("collection config missing")
        log_runtime("collection compatibility check=config_object actual=missing")
        return errors

    metadata = config_obj.get("metadata")
    if not isinstance(metadata, dict):
        errors.append("collection metadata missing")
        log_runtime("collection compatibility check=embedding_model_name_presence collection metadata missing")
    else:
        has_embedding_model_name = "embedding_model_name" in metadata
        log_runtime(f"collection compatibility check=embedding_model_name_presence actual={has_embedding_model_name}")
        if not has_embedding_model_name:
            errors.append("collection metadata missing embedding_model_name")
        else:
            actual_model_name = metadata.get("embedding_model_name")
            log_runtime(
                "collection compatibility check=embedding_model_name_compare "
                f"expected={config.embedding_model_name} actual={actual_model_name}"
            )
            if actual_model_name != config.embedding_model_name:
                errors.append("collection embedding_model_name mismatch")

        actual_chunking_strategy = metadata.get("chunking_strategy")
        log_runtime(
            "collection compatibility check=chunking_strategy_compare "
            f"expected={config.chunking_strategy} actual={actual_chunking_strategy}"
        )
        if actual_chunking_strategy != config.chunking_strategy:
            errors.append("collection chunking_strategy mismatch")

    params = config_obj.get("params", {}) if isinstance(config_obj.get("params"), dict) else {}
    vector_config = params.get("vectors", {}) if isinstance(params.get("vectors"), dict) else {}
    actual_size = vector_config.get("size")
    actual_distance = vector_config.get("distance")
    log_runtime(
        f"collection compatibility check=vector_dimension expected={config.embedding_model_dimension} actual={actual_size}"
    )
    log_runtime(
        f"collection compatibility check=vector_distance expected={config.qdrant_collection_distance} actual={actual_distance}"
    )
    if actual_size != config.embedding_model_dimension:
        errors.append("collection vector dimension mismatch")
    if actual_distance != config.qdrant_collection_distance:
        errors.append("collection vector distance mismatch")
    return errors


def compute_point_id(config: AppConfig, chunk: Dict[str, Any]) -> str:
    namespace_uuid = uuid.UUID(config.qdrant_point_id_namespace_uuid)
    return str(uuid.uuid5(namespace_uuid, require_string(chunk.get("chunk_id"), "chunk.chunk_id")))


def split_chunk_field_reference(field_path: str) -> List[str]:
    parts = field_path.split(".")
    if len(parts) >= 2 and parts[0] == "chunk":
        return parts[1:]
    return parts


def resolve_field_path(payload: Dict[str, Any], field_path: str) -> Any:
    current: Any = payload
    for part in split_chunk_field_reference(field_path):
        if not isinstance(current, dict) or part not in current:
            raise IngestError(f"missing field path: {field_path}")
        current = current[part]
    return current


def canonicalize_fingerprint_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def compute_fingerprint(config: AppConfig, payload: Dict[str, Any]) -> str:
    values = [canonicalize_fingerprint_value(resolve_field_path(payload, path)) for path in config.fingerprint_fields]
    serialized = json.dumps(values, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def qdrant_get_point(config: AppConfig, env: EnvConfig, point_id: str) -> Optional[Dict[str, Any]]:
    collection_name = urllib.parse.quote(config.qdrant_collection_name, safe="")
    point_id_path = urllib.parse.quote(point_id, safe="")
    url = build_url(env.qdrant_url, f"/collections/{collection_name}/points/{point_id_path}")

    def validate(response: HttpResponse) -> Optional[Dict[str, Any]]:
        if response.status_code == 404:
            return None
        if not (200 <= response.status_code < 300):
            raise ExternalServiceError(format_service_error(response, "qdrant point lookup failed"))
        if not isinstance(response.json_body, dict):
            raise InvalidResponseError("qdrant point lookup response must be JSON object")
        result = response.json_body.get("result")
        if not isinstance(result, dict):
            raise InvalidResponseError("qdrant point lookup result must be object")
        payload = result.get("payload")
        if not isinstance(payload, dict):
            raise InvalidResponseError("qdrant point lookup payload must be object")
        return result

    return request_with_retry(
        "qdrant_get_point",
        "GET",
        url,
        None,
        config.qdrant_timeout_sec,
        config.qdrant_retry,
        validate,
    )


def delete_field_path(payload: Dict[str, Any], field_path: str) -> None:
    parts = split_chunk_field_reference(field_path)
    current: Any = payload
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            return
        current = current[part]
    if isinstance(current, dict):
        current.pop(parts[-1], None)


def build_metadata_view(payload: Dict[str, Any], fingerprint_fields: Sequence[str]) -> Dict[str, Any]:
    copied = json.loads(json.dumps(payload))
    for field_path in fingerprint_fields:
        delete_field_path(copied, field_path)
    return copied


def build_metadata_comparison_view(payload: Dict[str, Any], fingerprint_fields: Sequence[str]) -> Dict[str, Any]:
    copied = build_metadata_view(payload, fingerprint_fields)
    # `ingest.ingested_at` changes on every run and must not force `update`.
    delete_field_path(copied, "ingest.ingested_at")
    return copied


def build_update_payload(config: AppConfig, chunk_payload: Dict[str, Any], point_payload: Dict[str, Any]) -> Dict[str, Any]:
    desired_metadata = build_metadata_view(chunk_payload, config.fingerprint_fields)
    current_metadata = build_metadata_view(point_payload, config.fingerprint_fields)
    desired_comparison = build_metadata_comparison_view(chunk_payload, config.fingerprint_fields)
    current_comparison = build_metadata_comparison_view(point_payload, config.fingerprint_fields)
    if desired_comparison == current_comparison:
        return {}

    payload_update: Dict[str, Any] = json.loads(json.dumps(point_payload))
    for key, value in desired_metadata.items():
        if key == "text":
            continue
        if current_metadata.get(key) != value:
            payload_update[key] = value
    return payload_update


def call_embedding_service(config: AppConfig, env: EnvConfig, texts: List[str]) -> List[List[float]]:
    if len(texts) == 0:
        raise InvalidResponseError("embedding input must not be empty")
    url = build_url(env.ollama_url, "/api/embed")
    body = {
        "model": config.embedding_model_name,
        "input": texts,
    }
    return request_with_retry(
        "embedding_request",
        "POST",
        url,
        body,
        config.embedding_timeout_sec,
        config.embedding_retry,
        lambda response: validate_embedding_response(response, len(texts), config.embedding_model_dimension),
    )


def qdrant_upsert_points(config: AppConfig, env: EnvConfig, points: List[Dict[str, Any]]) -> None:
    url = build_url(
        env.qdrant_url,
        f"/collections/{urllib.parse.quote(config.qdrant_collection_name, safe='')}/points",
    )
    body = {"points": points}
    request_with_retry(
        "qdrant_upsert_points",
        "PUT",
        url,
        body,
        config.qdrant_timeout_sec,
        config.qdrant_retry,
        lambda response: validate_qdrant_ack_response(response, "qdrant upsert"),
    )


def qdrant_update_payload(config: AppConfig, env: EnvConfig, point_id: str, payload: Dict[str, Any]) -> None:
    url = build_url(
        env.qdrant_url,
        f"/collections/{urllib.parse.quote(config.qdrant_collection_name, safe='')}/points/payload",
    )
    body = {
        "payload": payload,
        "points": [point_id],
    }
    request_with_retry(
        "qdrant_update_payload",
        "PUT",
        url,
        body,
        config.qdrant_timeout_sec,
        config.qdrant_retry,
        lambda response: validate_qdrant_ack_response(response, "qdrant payload update"),
    )


def assign_ingest_statuses(
    config: AppConfig,
    env: EnvConfig,
    chunk_contexts: List[ChunkContext],
    collection_created_in_run: bool,
    summary: Summary,
) -> Tuple[List[ChunkContext], List[ChunkContext]]:
    inserts: List[ChunkContext] = []
    updates: List[ChunkContext] = []

    for chunk_context in chunk_contexts:
        chunk_index = chunk_context.chunk_index
        try:
            if collection_created_in_run:
                chunk_context.ingest_status = "insert"
                log_runtime(f"status assignment chunk_index={chunk_index} ingest_status=insert reason=collection_created")
                inserts.append(chunk_context)
                continue

            point = qdrant_get_point(config, env, chunk_context.point_id)
            if point is None:
                chunk_context.ingest_status = "insert"
                log_runtime(f"status assignment chunk_index={chunk_index} ingest_status=insert reason=point_missing")
                inserts.append(chunk_context)
                continue

            point_payload = point["payload"]
            chunk_fingerprint = compute_fingerprint(config, chunk_context.chunk)
            point_fingerprint = compute_fingerprint(config, point_payload)
            if chunk_fingerprint != point_fingerprint:
                chunk_context.ingest_status = "skip_and_log"
                summary.skipped += 1
                log_skipped_chunk(config, chunk_context.chunk, chunk_context.chunk_index)
                log_runtime(f"status assignment chunk_index={chunk_index} ingest_status=skip_and_log reason=fingerprint_changed")
                continue

            chunk_metadata = build_metadata_comparison_view(chunk_context.chunk, config.fingerprint_fields)
            point_metadata = build_metadata_comparison_view(point_payload, config.fingerprint_fields)
            if chunk_metadata != point_metadata:
                chunk_context.ingest_status = "update"
                updates.append(chunk_context)
                log_runtime(f"status assignment chunk_index={chunk_index} ingest_status=update reason=metadata_changed")
            else:
                chunk_context.ingest_status = "skip"
                summary.unchanged += 1
                log_runtime(f"status assignment chunk_index={chunk_index} ingest_status=skip reason=metadata_unchanged")
        except Exception as exc:
            summary.failed += 1
            log_failed_chunk(config, chunk_context.chunk, chunk_index, "qdrant", str(exc))
            log_runtime(f"status assignment chunk_index={chunk_index} ingest_status=failed error={exc}")
    return inserts, updates


def process_embedding_batches(
    config: AppConfig,
    env: EnvConfig,
    insert_chunks: List[ChunkContext],
    summary: Summary,
) -> List[ChunkWithEmbedding]:
    results: List[ChunkWithEmbedding] = []
    for batch_index, batch in enumerate(chunked(insert_chunks, config.embedding_max_batch_size)):
        batch_list = list(batch)
        log_runtime(f"embedding batch start batch_index={batch_index} batch_size={len(batch_list)}")
        try:
            texts = [require_string(resolve_field_path(item.chunk, config.embedding_text_source), f"text_source chunk_index={item.chunk_index}") for item in batch_list]
            embeddings = call_embedding_service(config, env, texts)
            for item, embedding in zip(batch_list, embeddings):
                results.append(ChunkWithEmbedding(item, embedding))
            log_runtime(f"embedding batch result batch_index={batch_index} batch_size={len(batch_list)} status=success")
        except Exception as batch_exc:
            log_runtime(
                f"embedding batch result batch_index={batch_index} batch_size={len(batch_list)} status=failed error={batch_exc}"
            )
            log_runtime(
                f"embedding fallback start batch_index={batch_index} batch_size={len(batch_list)} mode=per_chunk"
            )
            for item in batch_list:
                try:
                    text = require_string(
                        resolve_field_path(item.chunk, config.embedding_text_source),
                        f"text_source chunk_index={item.chunk_index}",
                    )
                    embedding = call_embedding_service(config, env, [text])[0]
                    results.append(ChunkWithEmbedding(item, embedding))
                    log_runtime(f"embedding fallback chunk_index={item.chunk_index} status=success")
                except Exception as item_exc:
                    summary.failed += 1
                    log_failed_chunk(config, item.chunk, item.chunk_index, "embed", str(item_exc))
                    log_runtime(f"embedding fallback chunk_index={item.chunk_index} status=failed error={item_exc}")
    return results


def point_from_embedding(chunk_with_embedding: ChunkWithEmbedding) -> Dict[str, Any]:
    return {
        "id": chunk_with_embedding.chunk_context.point_id,
        "vector": chunk_with_embedding.embedding,
        "payload": chunk_with_embedding.chunk_context.chunk,
    }


def process_upsert_batches(
    config: AppConfig,
    env: EnvConfig,
    chunk_embeddings: List[ChunkWithEmbedding],
    summary: Summary,
) -> None:
    for batch_index, batch in enumerate(chunked(chunk_embeddings, config.qdrant_upsert_batch_size)):
        batch_list = list(batch)
        log_runtime(f"qdrant upsert batch start batch_index={batch_index} batch_size={len(batch_list)}")
        try:
            points = [point_from_embedding(item) for item in batch_list]
            qdrant_upsert_points(config, env, points)
            summary.created += len(batch_list)
            log_runtime(f"qdrant upsert batch result batch_index={batch_index} batch_size={len(batch_list)} status=success")
        except Exception as batch_exc:
            log_runtime(
                f"qdrant upsert batch result batch_index={batch_index} batch_size={len(batch_list)} status=failed error={batch_exc}"
            )
            log_runtime(
                f"qdrant upsert fallback start batch_index={batch_index} batch_size={len(batch_list)} mode=per_point"
            )
            for item in batch_list:
                try:
                    qdrant_upsert_points(config, env, [point_from_embedding(item)])
                    summary.created += 1
                    log_runtime(f"qdrant upsert fallback chunk_index={item.chunk_context.chunk_index} status=success")
                except Exception as item_exc:
                    summary.failed += 1
                    log_failed_chunk(config, item.chunk_context.chunk, item.chunk_context.chunk_index, "qdrant", str(item_exc))
                    log_runtime(
                        f"qdrant upsert fallback chunk_index={item.chunk_context.chunk_index} status=failed error={item_exc}"
                    )


def process_updates(config: AppConfig, env: EnvConfig, updates: List[ChunkContext], summary: Summary) -> None:
    for chunk_context in updates:
        chunk_index = chunk_context.chunk_index
        log_runtime(f"update path start chunk_index={chunk_index}")
        try:
            point = qdrant_get_point(config, env, chunk_context.point_id)
            if point is None:
                raise ExternalServiceError("point missing during update path")
            payload = build_update_payload(config, chunk_context.chunk, point["payload"])
            if payload == {}:
                summary.unchanged += 1
                log_runtime(f"update path result chunk_index={chunk_index} status=noop")
                continue
            qdrant_update_payload(config, env, chunk_context.point_id, payload)
            summary.updated += 1
            log_runtime(f"update path result chunk_index={chunk_index} status=success")
        except Exception as exc:
            summary.failed += 1
            log_failed_chunk(config, chunk_context.chunk, chunk_index, "qdrant", str(exc))
            log_runtime(f"update path result chunk_index={chunk_index} status=failed error={exc}")


def validate_runtime_settings(config: AppConfig, env: EnvConfig) -> None:
    validate_base_url(env.qdrant_url, "ENV_FILE_PATH.QDRANT_URL")
    validate_base_url(env.ollama_url, "ENV_FILE_PATH.OLLAMA_URL")
    if config.embedding_max_batch_size < 1:
        raise ConfigError("CONFIG_PATH.embedding.transport.max_batch_size must be >= 1")
    if config.qdrant_upsert_batch_size < 1:
        raise ConfigError("CONFIG_PATH.qdrant.transport.upsert_batch_size must be >= 1")
    if config.embedding_timeout_sec < 1:
        raise ConfigError("CONFIG_PATH.embedding.transport.timeout_sec must be >= 1")
    if config.qdrant_timeout_sec < 1:
        raise ConfigError("CONFIG_PATH.qdrant.transport.timeout_sec must be >= 1")


def load_runtime_config(config_path: Path, env_path: Path) -> Tuple[AppConfig, EnvConfig]:
    log_runtime("loading config")
    config = validate_config(load_toml(config_path))
    log_runtime("loading env")
    env = validate_env(parse_env_file(env_path))
    log_runtime("runtime settings validation start")
    validate_runtime_settings(config, env)
    log_runtime("runtime settings validation result=success")
    return config, env


def load_and_validate_chunks(path: Path, config: AppConfig, summary: Summary) -> List[ChunkContext]:
    log_runtime(f"loading chunks path={path}")
    chunks = read_chunks(path)
    if len(chunks) == 0:
        log_runtime(f"fail-fast reason=no_chunks path={path}")
        print(f"FAIL: no chunks in {path}")
        raise SystemExit(1)

    valid_chunks: List[ChunkContext] = []
    for chunk_index, chunk in chunks:
        summary.total += 1
        try:
            validate_chunk(chunk, chunk_index, config)
            point_id = compute_point_id(config, chunk)
            valid_chunks.append(ChunkContext(chunk=chunk, chunk_index=chunk_index, point_id=point_id))
            log_runtime(f"chunk validation chunk_index={chunk_index} result=success")
        except Exception as exc:
            summary.failed += 1
            chunk_id = chunk.get("chunk_id", "")
            append_jsonl(
                config.failed_chunk_log_path,
                {
                    "chunk_id": chunk_id,
                    "chunk_index": chunk_index,
                    "stage": "validate",
                    "error": str(exc),
                },
            )
            log_runtime(f"chunk validation chunk_index={chunk_index} result=failed error={exc}")
    return valid_chunks


def print_normal_summary(summary: Summary, report_only: bool) -> int:
    print(
        f"chunks={summary.total} created={summary.created} updated={summary.updated} "
        f"unchanged={summary.unchanged} skipped={summary.skipped} failed={summary.failed}"
    )
    if summary.failed > 0:
        if report_only:
            print("WARN: dense ingest completed with failures")
            return 0
        print("FAIL: dense ingest failed")
        return 1
    print("OK: dense ingest completed")
    return 0


def run_ingest(chunks_path: Path, config: AppConfig, env: EnvConfig, report_only: bool) -> int:
    summary = Summary()
    valid_chunks = load_and_validate_chunks(chunks_path, config, summary)

    log_runtime("collection existence check start")
    collection_status, collection_body = qdrant_get_collection(config, env)
    log_runtime(f"collection existence check result={collection_status}")

    collection_created_in_run = False
    if collection_status == "missing":
        if not config.qdrant_create_if_missing:
            log_runtime("fail-fast reason=collection_missing create_if_missing=false")
            print("SKIP: collection does not exist and create_if_missing=false")
            return 0
        log_runtime("collection creation start")
        qdrant_create_collection(config, env)
        log_runtime("collection creation result=success")
        collection_created_in_run = True
    else:
        compatibility_errors = extract_collection_compatibility_errors(config, require_dict(collection_body, "collection_body"))
        if compatibility_errors:
            raise IngestError("; ".join(compatibility_errors))

    ingest_metadata = build_ingest_metadata(config, now_iso_utc())
    enriched_chunks = [
        ChunkContext(
            chunk=inject_ingest_metadata(chunk_context.chunk, ingest_metadata),
            chunk_index=chunk_context.chunk_index,
            point_id=chunk_context.point_id,
        )
        for chunk_context in valid_chunks
    ]

    inserts, updates = assign_ingest_statuses(config, env, enriched_chunks, collection_created_in_run, summary)
    chunk_embeddings = process_embedding_batches(config, env, inserts, summary)
    process_upsert_batches(config, env, chunk_embeddings, summary)
    process_updates(config, env, updates, summary)

    return print_normal_summary(summary, report_only)


def main() -> None:
    args = parse_args()
    exit_code = 1
    log_runtime("run start")
    try:
        config, env = load_runtime_config(Path(args.config_path), Path(args.env_file_path))
        exit_code = run_ingest(Path(args.chunks_path), config, env, bool(args.report_only))
    except SystemExit as exc:
        exit_code = int(exc.code)
        raise
    except IngestError as exc:
        print(f"FAIL: {exc}")
        exit_code = 1
    finally:
        log_runtime(f"exit code={exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

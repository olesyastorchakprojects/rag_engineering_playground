#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_SCHEMA_PATH = REPO_ROOT / "Execution" / "ingest" / "schemas" / "hybrid_ingest_config.schema.json"
ENV_SCHEMA_PATH = REPO_ROOT / "Execution" / "ingest" / "schemas" / "dense_ingest_env.schema.json"
CHUNK_SCHEMA_PATH = REPO_ROOT / "Execution" / "schemas" / "chunk.schema.json"
VOCAB_SCHEMA_PATH = REPO_ROOT / "Execution" / "ingest" / "schemas" / "common" / "sparse_vocabulary.schema.json"
TERM_STATS_SCHEMA_PATH = REPO_ROOT / "Execution" / "ingest" / "schemas" / "common" / "bm25_term_stats.schema.json"
MANIFEST_SCHEMA_PATH = REPO_ROOT / "Execution" / "ingest" / "schemas" / "hybrid_ingest_manifest.schema.json"


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
    corpus_version: str
    chunking_strategy: str
    embedding_model_name: str
    embedding_model_dimension: int
    embedding_text_source: str
    embedding_timeout_sec: int
    embedding_max_batch_size: int
    embedding_retry: RetryPolicy
    sparse_strategy_kind: str
    sparse_strategy_version: str
    sparse_text_source: str
    sparse_tokenizer_library: str
    sparse_tokenizer_source: str
    sparse_tokenizer_revision: Optional[str]
    sparse_preprocessing_kind: str
    sparse_lowercase: bool
    sparse_min_token_length: int
    sparse_bow_document: Optional[str]
    sparse_bow_query: Optional[str]
    sparse_bm25_document: Optional[str]
    sparse_bm25_query: Optional[str]
    sparse_bm25_k1: Optional[float]
    sparse_bm25_b: Optional[float]
    sparse_bm25_idf_smoothing: Optional[str]
    sparse_bm25_term_stats_path: Optional[str]
    artifacts_vocabulary_path: str
    artifacts_manifest_path: str
    qdrant_base_collection_name: str
    qdrant_effective_collection_name: str
    qdrant_collection_distance: str
    qdrant_dense_vector_name: str
    qdrant_sparse_vector_name: str
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
class VocabularyState:
    artifact: Dict[str, Any]
    token_to_id: Dict[str, int]
    id_to_token: Dict[int, str]
    created_in_this_run: bool


@dataclass
class Bm25StatsState:
    artifact: Dict[str, Any]
    created_in_this_run: bool
    document_count: int
    average_document_length: float
    document_frequency_by_token_id: Dict[int, int]


@dataclass
class ManifestRuntime:
    run_id: str
    started_at: str


@dataclass
class ChunkContext:
    chunk: Dict[str, Any]
    chunk_index: int
    point_id: str
    sparse_vector: Optional[Dict[str, Any]] = None
    oov_token_count: int = 0
    ingest_status: Optional[str] = None


@dataclass
class ChunkWithRepresentations:
    chunk_context: ChunkContext
    embedding: List[float]


@dataclass
class Summary:
    total: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    skip_and_log: int = 0
    failed: int = 0


@dataclass
class HttpResponse:
    status_code: int
    body_bytes: bytes
    body_text: str
    json_body: Optional[Any]


def log_runtime(message: str) -> None:
    print(f"[hybrid_ingest] {message}", file=sys.stderr, flush=True)


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


def require_number(value: Any, path: str, minimum: Optional[float] = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise IngestError(f"{path} must be a number")
    number = float(value)
    if minimum is not None and number < minimum:
        raise IngestError(f"{path} must be >= {minimum}")
    return number


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


def validate_base_url(value: str, path: str) -> None:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in ("http", "https") or parsed.netloc == "":
        raise EnvError(f"{path} must be an absolute http(s) URL")


def derive_strategy_suffix(strategy_kind: str) -> str:
    mapping = {
        "bag_of_words": "bow",
        "bm25_like": "bm25",
    }
    suffix = mapping.get(strategy_kind)
    if suffix is None:
        raise ConfigError("CONFIG_PATH.sparse.strategy.kind has unsupported value")
    return suffix


def validate_base_collection_name(base_name: str) -> None:
    if base_name.endswith("_bow"):
        raise ConfigError("CONFIG_PATH.qdrant.collection.name must not end with _bow")
    if base_name.endswith("_bm25"):
        raise ConfigError("CONFIG_PATH.qdrant.collection.name must not end with _bm25")
    if base_name.endswith("_"):
        raise ConfigError("CONFIG_PATH.qdrant.collection.name must not end with _")


def derive_effective_collection_name(base_name: str, strategy_kind: str) -> str:
    validate_base_collection_name(base_name)
    return f"{base_name}_{derive_strategy_suffix(strategy_kind)}"


def expected_vocabulary_name(base_collection_name: str) -> str:
    return f"{base_collection_name}__sparse_vocabulary"


def expected_vocabulary_basename(base_collection_name: str) -> str:
    return f"{expected_vocabulary_name(base_collection_name)}.json"


def expected_term_stats_basename(effective_collection_name: str) -> str:
    return f"{effective_collection_name}__term_stats.json"


def derive_vocabulary_artifact_path(base_collection_name: str) -> str:
    return str(
        REPO_ROOT
        / "Execution"
        / "ingest"
        / "hybrid"
        / "artifacts"
        / "vocabularies"
        / expected_vocabulary_basename(base_collection_name)
    )


def derive_term_stats_artifact_path(effective_collection_name: str) -> str:
    return str(
        REPO_ROOT
        / "Execution"
        / "ingest"
        / "hybrid"
        / "artifacts"
        / "term_stats"
        / expected_term_stats_basename(effective_collection_name)
    )


def resolve_repo_root_relative_path(path_str: str) -> str:
    path = Path(path_str)
    if path.is_absolute():
        return str(path)
    return str(REPO_ROOT / path)


def parse_manifest_parent_name(path_str: str) -> Tuple[str, str]:
    parent_name = Path(path_str).parent.name
    if parent_name == "":
        raise ConfigError("CONFIG_PATH.artifacts.manifest_path parent directory must be present")
    if "_" not in parent_name:
        raise ConfigError(
            "CONFIG_PATH.artifacts.manifest_path parent directory must be '<started_at>_<run_id>'"
        )
    started_at_part, run_id_part = parent_name.rsplit("_", 1)
    if started_at_part == "":
        raise ConfigError(
            "CONFIG_PATH.artifacts.manifest_path parent directory must contain started_at prefix"
        )
    try:
        uuid.UUID(run_id_part)
    except ValueError as exc:
        raise ConfigError(
            "CONFIG_PATH.artifacts.manifest_path parent directory run_id must be UUID"
        ) from exc
    return started_at_part, run_id_part


def normalize_filesystem_timestamp(value: str) -> str:
    if "T" in value and value.endswith("Z"):
        left, right = value.split("T", 1)
        core = right[:-1]
        if ":" not in core and core.count("-") >= 2:
            hh, mm, ss = core.split("-", 2)
            candidate = f"{left}T{hh}:{mm}:{ss}Z"
            try:
                validate_iso_datetime(candidate, "manifest.started_at")
                return candidate
            except IngestError:
                pass
    validate_iso_datetime(value, "manifest.started_at")
    return value


def parse_manifest_runtime(path_str: str) -> ManifestRuntime:
    started_at_part, run_id = parse_manifest_parent_name(path_str)
    started_at = normalize_filesystem_timestamp(started_at_part)
    return ManifestRuntime(run_id=str(uuid.UUID(run_id)), started_at=started_at)


def validate_config(config_data: Dict[str, Any]) -> AppConfig:
    schema = require_dict(load_json_file(CONFIG_SCHEMA_PATH), str(CONFIG_SCHEMA_PATH))
    if schema.get("type") != "object":
        raise ConfigError("config schema root must be object")

    try:
        require_exact_keys(config_data, schema["required"], (), "CONFIG_PATH")

        pipeline = require_dict(config_data["pipeline"], "CONFIG_PATH.pipeline")
        require_exact_keys(
            pipeline,
            ("name", "chunk_schema_version", "ingest_config_version", "corpus_version", "chunking_strategy"),
            (),
            "CONFIG_PATH.pipeline",
        )

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

        sparse = require_dict(config_data["sparse"], "CONFIG_PATH.sparse")
        require_exact_keys(
            sparse,
            ("strategy", "input", "tokenizer", "preprocessing"),
            ("bag_of_words", "bm25_like"),
            "CONFIG_PATH.sparse",
        )
        sparse_strategy = require_dict(sparse["strategy"], "CONFIG_PATH.sparse.strategy")
        require_exact_keys(sparse_strategy, ("kind", "version"), (), "CONFIG_PATH.sparse.strategy")
        sparse_input = require_dict(sparse["input"], "CONFIG_PATH.sparse.input")
        require_exact_keys(sparse_input, ("text_source",), (), "CONFIG_PATH.sparse.input")
        sparse_tokenizer = require_dict(sparse["tokenizer"], "CONFIG_PATH.sparse.tokenizer")
        require_exact_keys(sparse_tokenizer, ("library", "source"), ("revision",), "CONFIG_PATH.sparse.tokenizer")
        sparse_preprocessing = require_dict(sparse["preprocessing"], "CONFIG_PATH.sparse.preprocessing")
        require_exact_keys(
            sparse_preprocessing,
            ("kind", "lowercase", "min_token_length"),
            (),
            "CONFIG_PATH.sparse.preprocessing",
        )

        artifacts = require_dict(config_data["artifacts"], "CONFIG_PATH.artifacts")
        require_exact_keys(artifacts, ("manifest_path",), (), "CONFIG_PATH.artifacts")

        qdrant = require_dict(config_data["qdrant"], "CONFIG_PATH.qdrant")
        require_exact_keys(qdrant, ("collection", "point_id", "transport", "retry"), (), "CONFIG_PATH.qdrant")
        qdrant_collection = require_dict(qdrant["collection"], "CONFIG_PATH.qdrant.collection")
        require_exact_keys(
            qdrant_collection,
            ("name", "distance", "dense_vector_name", "sparse_vector_name", "create_if_missing"),
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
    corpus_version = require_string(pipeline["corpus_version"], "CONFIG_PATH.pipeline.corpus_version")
    if re.fullmatch(r"v[1-9][0-9]*", corpus_version) is None:
        raise ConfigError("CONFIG_PATH.pipeline.corpus_version must match ^v[1-9][0-9]*$")
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

    sparse_strategy_kind = require_string(sparse_strategy["kind"], "CONFIG_PATH.sparse.strategy.kind")
    if sparse_strategy_kind not in ("bag_of_words", "bm25_like"):
        raise ConfigError("CONFIG_PATH.sparse.strategy.kind has unsupported value")
    sparse_strategy_version = require_string(sparse_strategy["version"], "CONFIG_PATH.sparse.strategy.version")
    if sparse_strategy_version != "v1":
        raise ConfigError("CONFIG_PATH.sparse.strategy.version must be v1")

    sparse_text_source = require_string(sparse_input["text_source"], "CONFIG_PATH.sparse.input.text_source")
    sparse_tokenizer_library = require_string(sparse_tokenizer["library"], "CONFIG_PATH.sparse.tokenizer.library")
    if sparse_tokenizer_library != "tokenizers":
        raise ConfigError("CONFIG_PATH.sparse.tokenizer.library must be tokenizers")
    sparse_tokenizer_source = require_string(sparse_tokenizer["source"], "CONFIG_PATH.sparse.tokenizer.source")
    sparse_tokenizer_revision: Optional[str] = None
    if "revision" in sparse_tokenizer:
        sparse_tokenizer_revision = require_string(sparse_tokenizer["revision"], "CONFIG_PATH.sparse.tokenizer.revision")

    sparse_preprocessing_kind = require_string(sparse_preprocessing["kind"], "CONFIG_PATH.sparse.preprocessing.kind")
    if sparse_preprocessing_kind != "basic_word_v1":
        raise ConfigError("CONFIG_PATH.sparse.preprocessing.kind must be basic_word_v1")
    sparse_lowercase = require_bool(sparse_preprocessing["lowercase"], "CONFIG_PATH.sparse.preprocessing.lowercase")
    sparse_min_token_length = require_int(
        sparse_preprocessing["min_token_length"], "CONFIG_PATH.sparse.preprocessing.min_token_length", 1
    )

    sparse_bow_document: Optional[str] = None
    sparse_bow_query: Optional[str] = None
    sparse_bm25_document: Optional[str] = None
    sparse_bm25_query: Optional[str] = None
    sparse_bm25_k1: Optional[float] = None
    sparse_bm25_b: Optional[float] = None
    sparse_bm25_idf_smoothing: Optional[str] = None
    sparse_bm25_term_stats_path: Optional[str] = None
    has_bow = "bag_of_words" in sparse
    has_bm25 = "bm25_like" in sparse
    if sparse_strategy_kind == "bag_of_words":
        if not has_bow or has_bm25:
            raise ConfigError("CONFIG_PATH.sparse must contain only [bag_of_words] for bag_of_words strategy")
        sparse_bow = require_dict(sparse["bag_of_words"], "CONFIG_PATH.sparse.bag_of_words")
        require_exact_keys(sparse_bow, ("document", "query"), (), "CONFIG_PATH.sparse.bag_of_words")
        sparse_bow_document = require_string(sparse_bow["document"], "CONFIG_PATH.sparse.bag_of_words.document")
        sparse_bow_query = require_string(sparse_bow["query"], "CONFIG_PATH.sparse.bag_of_words.query")
        if sparse_bow_document != "term_frequency":
            raise ConfigError("CONFIG_PATH.sparse.bag_of_words.document must be term_frequency")
        if sparse_bow_query != "binary_presence":
            raise ConfigError("CONFIG_PATH.sparse.bag_of_words.query must be binary_presence")
    else:
        if not has_bm25 or has_bow:
            raise ConfigError("CONFIG_PATH.sparse must contain only [bm25_like] for bm25_like strategy")
        sparse_bm25 = require_dict(sparse["bm25_like"], "CONFIG_PATH.sparse.bm25_like")
        require_exact_keys(
            sparse_bm25,
            ("document", "query", "k1", "b", "idf_smoothing"),
            (),
            "CONFIG_PATH.sparse.bm25_like",
        )
        sparse_bm25_document = require_string(sparse_bm25["document"], "CONFIG_PATH.sparse.bm25_like.document")
        sparse_bm25_query = require_string(sparse_bm25["query"], "CONFIG_PATH.sparse.bm25_like.query")
        sparse_bm25_k1 = require_number(sparse_bm25["k1"], "CONFIG_PATH.sparse.bm25_like.k1", 0.0)
        if sparse_bm25_k1 <= 0.0:
            raise ConfigError("CONFIG_PATH.sparse.bm25_like.k1 must be > 0")
        sparse_bm25_b = require_number(sparse_bm25["b"], "CONFIG_PATH.sparse.bm25_like.b")
        if not (0.0 <= sparse_bm25_b <= 1.0):
            raise ConfigError("CONFIG_PATH.sparse.bm25_like.b must be in [0.0, 1.0]")
        sparse_bm25_idf_smoothing = require_string(
            sparse_bm25["idf_smoothing"], "CONFIG_PATH.sparse.bm25_like.idf_smoothing"
        )
        if sparse_bm25_document != "bm25_document_weight":
            raise ConfigError("CONFIG_PATH.sparse.bm25_like.document must be bm25_document_weight")
        if sparse_bm25_query != "bm25_query_weight":
            raise ConfigError("CONFIG_PATH.sparse.bm25_like.query must be bm25_query_weight")

    qdrant_base_collection_name = require_string(qdrant_collection["name"], "CONFIG_PATH.qdrant.collection.name")
    validate_base_collection_name(qdrant_base_collection_name)
    qdrant_effective_collection_name = derive_effective_collection_name(
        qdrant_base_collection_name, sparse_strategy_kind
    )
    qdrant_collection_distance = require_string(qdrant_collection["distance"], "CONFIG_PATH.qdrant.collection.distance")
    if qdrant_collection_distance not in ("Cosine", "Dot", "Euclid", "Manhattan"):
        raise ConfigError("CONFIG_PATH.qdrant.collection.distance has unsupported value")
    qdrant_dense_vector_name = require_string(
        qdrant_collection["dense_vector_name"], "CONFIG_PATH.qdrant.collection.dense_vector_name"
    )
    qdrant_sparse_vector_name = require_string(
        qdrant_collection["sparse_vector_name"], "CONFIG_PATH.qdrant.collection.sparse_vector_name"
    )
    if qdrant_dense_vector_name == qdrant_sparse_vector_name:
        raise ConfigError(
            "CONFIG_PATH.qdrant.collection.dense_vector_name must differ from sparse_vector_name"
        )
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

    failed_chunk_log_path = resolve_repo_root_relative_path(
        require_string(logging_cfg["failed_chunk_log_path"], "CONFIG_PATH.logging.failed_chunk_log_path")
    )
    skipped_chunk_log_path = resolve_repo_root_relative_path(
        require_string(logging_cfg["skipped_chunk_log_path"], "CONFIG_PATH.logging.skipped_chunk_log_path")
    )
    artifacts_vocabulary_path = derive_vocabulary_artifact_path(qdrant_base_collection_name)
    artifacts_manifest_path = resolve_repo_root_relative_path(
        require_string(artifacts["manifest_path"], "CONFIG_PATH.artifacts.manifest_path")
    )
    if Path(artifacts_manifest_path).name != "run_manifest.json":
        raise ConfigError("CONFIG_PATH.artifacts.manifest_path basename must be run_manifest.json")
    parse_manifest_parent_name(artifacts_manifest_path)

    if sparse_strategy_kind == "bm25_like":
        sparse_bm25_term_stats_path = derive_term_stats_artifact_path(qdrant_effective_collection_name)

    return AppConfig(
        pipeline_name=pipeline_name,
        chunk_schema_version=chunk_schema_version,
        ingest_config_version=ingest_config_version,
        corpus_version=corpus_version,
        chunking_strategy=chunking_strategy,
        embedding_model_name=embedding_model_name,
        embedding_model_dimension=embedding_model_dimension,
        embedding_text_source=embedding_text_source,
        embedding_timeout_sec=embedding_timeout_sec,
        embedding_max_batch_size=embedding_max_batch_size,
        embedding_retry=RetryPolicy(embedding_retry_max_attempts, embedding_retry_backoff),
        sparse_strategy_kind=sparse_strategy_kind,
        sparse_strategy_version=sparse_strategy_version,
        sparse_text_source=sparse_text_source,
        sparse_tokenizer_library=sparse_tokenizer_library,
        sparse_tokenizer_source=sparse_tokenizer_source,
        sparse_tokenizer_revision=sparse_tokenizer_revision,
        sparse_preprocessing_kind=sparse_preprocessing_kind,
        sparse_lowercase=sparse_lowercase,
        sparse_min_token_length=sparse_min_token_length,
        sparse_bow_document=sparse_bow_document,
        sparse_bow_query=sparse_bow_query,
        sparse_bm25_document=sparse_bm25_document,
        sparse_bm25_query=sparse_bm25_query,
        sparse_bm25_k1=sparse_bm25_k1,
        sparse_bm25_b=sparse_bm25_b,
        sparse_bm25_idf_smoothing=sparse_bm25_idf_smoothing,
        sparse_bm25_term_stats_path=sparse_bm25_term_stats_path,
        artifacts_vocabulary_path=artifacts_vocabulary_path,
        artifacts_manifest_path=artifacts_manifest_path,
        qdrant_base_collection_name=qdrant_base_collection_name,
        qdrant_effective_collection_name=qdrant_effective_collection_name,
        qdrant_collection_distance=qdrant_collection_distance,
        qdrant_dense_vector_name=qdrant_dense_vector_name,
        qdrant_sparse_vector_name=qdrant_sparse_vector_name,
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
    validate_iso_datetime(
        require_string(chunk.get("chunk_created_at"), f"chunk[{chunk_index}].chunk_created_at"),
        f"chunk[{chunk_index}].chunk_created_at",
    )
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
    Path(path_str).parent.mkdir(parents=True, exist_ok=True)


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


def build_vocabulary_identity(config: AppConfig) -> Dict[str, Any]:
    identity: Dict[str, Any] = {
        "collection_name": config.qdrant_base_collection_name,
        "tokenizer_library": config.sparse_tokenizer_library,
        "tokenizer_source": config.sparse_tokenizer_source,
        "preprocessing_kind": config.sparse_preprocessing_kind,
        "lowercase": config.sparse_lowercase,
        "min_token_length": config.sparse_min_token_length,
    }
    if config.sparse_tokenizer_revision is not None:
        identity["tokenizer_revision"] = config.sparse_tokenizer_revision
    return identity


def qdrant_get_collection(config: AppConfig, env: EnvConfig) -> Tuple[str, Optional[Dict[str, Any]]]:
    url = build_url(
        env.qdrant_url,
        f"/collections/{urllib.parse.quote(config.qdrant_effective_collection_name, safe='')}",
    )

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


def qdrant_create_collection(config: AppConfig, env: EnvConfig, vocabulary_identity: Dict[str, Any]) -> None:
    url = build_url(
        env.qdrant_url,
        f"/collections/{urllib.parse.quote(config.qdrant_effective_collection_name, safe='')}",
    )
    body = {
        "vectors": {
            config.qdrant_dense_vector_name: {
                "size": config.embedding_model_dimension,
                "distance": config.qdrant_collection_distance,
            }
        },
        "sparse_vectors": {
            config.qdrant_sparse_vector_name: {}
        },
        "metadata": {
            "embedding_model_name": config.embedding_model_name,
            "chunking_strategy": config.chunking_strategy,
            "sparse_strategy_kind": config.sparse_strategy_kind,
            "sparse_strategy_version": config.sparse_strategy_version,
            "corpus_version": config.corpus_version,
            "vocabulary_identity": vocabulary_identity,
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


def extract_collection_compatibility_errors(
    config: AppConfig,
    collection_body: Dict[str, Any],
    expected_vocabulary_identity: Dict[str, Any],
) -> List[str]:
    errors: List[str] = []
    result = collection_body.get("result")
    if not isinstance(result, dict):
        return ["collection result missing"]
    config_obj = result.get("config")
    if not isinstance(config_obj, dict):
        return ["collection config missing"]
    params = config_obj.get("params")
    if not isinstance(params, dict):
        return ["collection params missing"]

    vectors = params.get("vectors")
    if not isinstance(vectors, dict):
        errors.append("collection vectors missing")
    else:
        dense_vector = vectors.get(config.qdrant_dense_vector_name)
        if not isinstance(dense_vector, dict):
            errors.append("collection dense_vector_name mismatch")
        else:
            if dense_vector.get("size") != config.embedding_model_dimension:
                errors.append("collection dense_vector_dimension mismatch")
            if dense_vector.get("distance") != config.qdrant_collection_distance:
                errors.append("collection dense_vector_distance mismatch")

    sparse_vectors = params.get("sparse_vectors")
    if not isinstance(sparse_vectors, dict):
        errors.append("collection sparse_vectors missing")
    elif config.qdrant_sparse_vector_name not in sparse_vectors:
        errors.append("collection sparse_vector_name mismatch")

    metadata = config_obj.get("metadata")
    if not isinstance(metadata, dict):
        errors.append("collection metadata missing")
        return errors
    if metadata.get("embedding_model_name") != config.embedding_model_name:
        errors.append("collection embedding_model_name mismatch")
    actual_chunking_strategy = metadata.get("chunking_strategy")
    log_runtime(
        "collection compatibility check=chunking_strategy_compare "
        f"expected={config.chunking_strategy} actual={actual_chunking_strategy}"
    )
    if actual_chunking_strategy != config.chunking_strategy:
        errors.append("collection chunking_strategy mismatch")
    if metadata.get("sparse_strategy_kind") != config.sparse_strategy_kind:
        errors.append("collection sparse_strategy_kind mismatch")
    if metadata.get("sparse_strategy_version") != config.sparse_strategy_version:
        errors.append("collection sparse_strategy_version mismatch")
    if metadata.get("corpus_version") != config.corpus_version:
        errors.append("collection corpus_version mismatch")
    if metadata.get("vocabulary_identity") != expected_vocabulary_identity:
        errors.append("collection vocabulary_identity mismatch")
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
    collection_name = urllib.parse.quote(config.qdrant_effective_collection_name, safe="")
    url = build_url(env.qdrant_url, f"/collections/{collection_name}/points")
    body = {
        "ids": [point_id],
        "with_payload": True,
        "with_vector": True,
    }

    def validate(response: HttpResponse) -> Optional[Dict[str, Any]]:
        if response.status_code == 404:
            return None
        if not (200 <= response.status_code < 300):
            raise ExternalServiceError(format_service_error(response, "qdrant point lookup failed"))
        if not isinstance(response.json_body, dict):
            raise InvalidResponseError("qdrant point lookup response must be JSON object")
        result = response.json_body.get("result")
        if isinstance(result, list):
            if len(result) == 0:
                return None
            point = result[0]
        elif isinstance(result, dict):
            point = result
        else:
            raise InvalidResponseError("qdrant point lookup result must be object or array")
        if not isinstance(point, dict):
            raise InvalidResponseError("qdrant point lookup result item must be object")
        payload = point.get("payload")
        if not isinstance(payload, dict):
            raise InvalidResponseError("qdrant point lookup payload must be object")
        return point

    return request_with_retry(
        "qdrant_get_point",
        "POST",
        url,
        body,
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
        f"/collections/{urllib.parse.quote(config.qdrant_effective_collection_name, safe='')}/points",
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
        f"/collections/{urllib.parse.quote(config.qdrant_effective_collection_name, safe='')}/points/payload",
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


def init_sparse_tokenizer(config: AppConfig) -> Any:
    try:
        from tokenizers import Tokenizer
    except ModuleNotFoundError as exc:
        raise ConfigError(f"Missing required dependency 'tokenizers': {exc}") from exc

    source_path = Path(config.sparse_tokenizer_source)
    if source_path.exists():
        return Tokenizer.from_file(str(source_path))

    if config.sparse_tokenizer_revision:
        try:
            return Tokenizer.from_pretrained(config.sparse_tokenizer_source, revision=config.sparse_tokenizer_revision)
        except TypeError:
            return Tokenizer.from_pretrained(config.sparse_tokenizer_source)
    return Tokenizer.from_pretrained(config.sparse_tokenizer_source)


def normalize_sparse_token(token: str, lowercase: bool, min_token_length: int) -> Optional[str]:
    candidate = token
    if lowercase:
        candidate = candidate.lower()
    if candidate.startswith("##"):
        candidate = candidate[2:]
    candidate = candidate.strip()
    while candidate and not candidate[0].isalnum():
        candidate = candidate[1:]
    while candidate and not candidate[-1].isalnum():
        candidate = candidate[:-1]
    if len(candidate) < min_token_length:
        return None
    if not any(ch.isalnum() for ch in candidate):
        return None
    return candidate


def tokenize_canonical(config: AppConfig, tokenizer: Any, text: str) -> List[str]:
    encoding = tokenizer.encode(text)
    raw_tokens = getattr(encoding, "tokens", None)
    if not isinstance(raw_tokens, list):
        raise IngestError("tokenizer.encode(text).tokens must be a list")
    normalized: List[str] = []
    for token in raw_tokens:
        if not isinstance(token, str):
            continue
        canonical = normalize_sparse_token(token, config.sparse_lowercase, config.sparse_min_token_length)
        if canonical is None:
            continue
        normalized.append(canonical)
    return normalized


def validate_vocabulary_artifact(config: AppConfig, artifact: Dict[str, Any]) -> VocabularyState:
    schema = require_dict(load_json_file(VOCAB_SCHEMA_PATH), str(VOCAB_SCHEMA_PATH))
    try:
        require_exact_keys(artifact, schema["required"], (), "SPARSE_VOCABULARY")
        vocabulary_name = require_string(artifact["vocabulary_name"], "SPARSE_VOCABULARY.vocabulary_name")
        expected_name = expected_vocabulary_name(config.qdrant_base_collection_name)
        if vocabulary_name != expected_name:
            raise IngestError("SPARSE_VOCABULARY.vocabulary_name mismatch")
        collection_name = require_string(artifact["collection_name"], "SPARSE_VOCABULARY.collection_name")
        if collection_name != config.qdrant_base_collection_name:
            raise IngestError("SPARSE_VOCABULARY.collection_name mismatch")

        text_processing = require_dict(artifact["text_processing"], "SPARSE_VOCABULARY.text_processing")
        require_exact_keys(
            text_processing,
            ("lowercase", "min_token_length", "preprocessing_kind"),
            (),
            "SPARSE_VOCABULARY.text_processing",
        )
        if (
            require_string(
                text_processing["preprocessing_kind"],
                "SPARSE_VOCABULARY.text_processing.preprocessing_kind",
            )
            != config.sparse_preprocessing_kind
        ):
            raise IngestError("SPARSE_VOCABULARY.text_processing.preprocessing_kind mismatch")
        if require_bool(text_processing["lowercase"], "SPARSE_VOCABULARY.text_processing.lowercase") != config.sparse_lowercase:
            raise IngestError("SPARSE_VOCABULARY.text_processing.lowercase mismatch")
        if (
            require_int(text_processing["min_token_length"], "SPARSE_VOCABULARY.text_processing.min_token_length", 1)
            != config.sparse_min_token_length
        ):
            raise IngestError("SPARSE_VOCABULARY.text_processing.min_token_length mismatch")

        tokenizer_obj = require_dict(artifact["tokenizer"], "SPARSE_VOCABULARY.tokenizer")
        require_exact_keys(tokenizer_obj, ("library", "source"), ("revision",), "SPARSE_VOCABULARY.tokenizer")
        if require_string(tokenizer_obj["library"], "SPARSE_VOCABULARY.tokenizer.library") != config.sparse_tokenizer_library:
            raise IngestError("SPARSE_VOCABULARY.tokenizer.library mismatch")
        if require_string(tokenizer_obj["source"], "SPARSE_VOCABULARY.tokenizer.source") != config.sparse_tokenizer_source:
            raise IngestError("SPARSE_VOCABULARY.tokenizer.source mismatch")
        artifact_revision = tokenizer_obj.get("revision")
        if config.sparse_tokenizer_revision is None and artifact_revision is not None:
            raise IngestError("SPARSE_VOCABULARY.tokenizer.revision mismatch")
        if config.sparse_tokenizer_revision is not None:
            if require_string(artifact_revision, "SPARSE_VOCABULARY.tokenizer.revision") != config.sparse_tokenizer_revision:
                raise IngestError("SPARSE_VOCABULARY.tokenizer.revision mismatch")

        validate_iso_datetime(require_string(artifact["created_at"], "SPARSE_VOCABULARY.created_at"), "SPARSE_VOCABULARY.created_at")

        tokens = artifact["tokens"]
        if not isinstance(tokens, list):
            raise IngestError("SPARSE_VOCABULARY.tokens must be an array")
        token_to_id: Dict[str, int] = {}
        id_to_token: Dict[int, str] = {}
        for index, entry in enumerate(tokens):
            entry_obj = require_dict(entry, f"SPARSE_VOCABULARY.tokens[{index}]")
            require_exact_keys(entry_obj, ("token", "token_id"), (), f"SPARSE_VOCABULARY.tokens[{index}]")
            token = require_string(entry_obj["token"], f"SPARSE_VOCABULARY.tokens[{index}].token")
            token_id = require_int(entry_obj["token_id"], f"SPARSE_VOCABULARY.tokens[{index}].token_id", 0)
            if token_id != index:
                raise IngestError("SPARSE_VOCABULARY token_id must equal zero-based array position")
            if token in token_to_id:
                raise IngestError("SPARSE_VOCABULARY token must be unique")
            token_to_id[token] = token_id
            id_to_token[token_id] = token
    except IngestError as exc:
        raise IngestError(str(exc)) from exc

    return VocabularyState(
        artifact=artifact,
        token_to_id=token_to_id,
        id_to_token=id_to_token,
        created_in_this_run=False,
    )


def build_vocabulary_artifact(config: AppConfig, tokenizer: Any, chunk_contexts: List[ChunkContext]) -> Dict[str, Any]:
    seen: Dict[str, int] = {}
    tokens: List[Dict[str, Any]] = []
    for chunk_context in chunk_contexts:
        text = require_string(
            resolve_field_path(chunk_context.chunk, config.sparse_text_source),
            f"sparse_text_source chunk_index={chunk_context.chunk_index}",
        )
        for token in tokenize_canonical(config, tokenizer, text):
            if token in seen:
                continue
            token_id = len(tokens)
            seen[token] = token_id
            tokens.append({"token": token, "token_id": token_id})

    tokenizer_object: Dict[str, Any] = {
        "library": config.sparse_tokenizer_library,
        "source": config.sparse_tokenizer_source,
    }
    if config.sparse_tokenizer_revision is not None:
        tokenizer_object["revision"] = config.sparse_tokenizer_revision

    return {
        "vocabulary_name": expected_vocabulary_name(config.qdrant_base_collection_name),
        "collection_name": config.qdrant_base_collection_name,
        "text_processing": {
            "preprocessing_kind": config.sparse_preprocessing_kind,
            "lowercase": config.sparse_lowercase,
            "min_token_length": config.sparse_min_token_length,
        },
        "tokenizer": tokenizer_object,
        "created_at": now_iso_utc(),
        "tokens": tokens,
    }


def load_or_create_vocabulary(config: AppConfig, tokenizer: Any, chunk_contexts: List[ChunkContext]) -> VocabularyState:
    path = Path(config.artifacts_vocabulary_path)
    if path.exists():
        loaded = require_dict(load_json_file(path), str(path))
        state = validate_vocabulary_artifact(config, loaded)
        state.created_in_this_run = False
        return state

    artifact = build_vocabulary_artifact(config, tokenizer, chunk_contexts)
    state = validate_vocabulary_artifact(config, artifact)
    ensure_parent_dir(config.artifacts_vocabulary_path)
    path.write_text(json.dumps(artifact, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    state.created_in_this_run = True
    return state


def parse_bm25_epsilon(idf_smoothing: str) -> float:
    if idf_smoothing.startswith("epsilon:"):
        value = idf_smoothing.split(":", 1)[1]
        try:
            epsilon = float(value)
        except ValueError as exc:
            raise ConfigError("CONFIG_PATH.sparse.bm25_like.idf_smoothing has invalid epsilon value") from exc
        if epsilon < 0.0:
            raise ConfigError("CONFIG_PATH.sparse.bm25_like.idf_smoothing epsilon must be >= 0")
        return epsilon
    return 0.25


def build_corpus_tokens(
    config: AppConfig,
    tokenizer: Any,
    chunk_contexts: List[ChunkContext],
    vocabulary: VocabularyState,
) -> List[List[str]]:
    corpus: List[List[str]] = []
    for chunk_context in chunk_contexts:
        text = require_string(
            resolve_field_path(chunk_context.chunk, config.sparse_text_source),
            f"sparse_text_source chunk_index={chunk_context.chunk_index}",
        )
        canonical = tokenize_canonical(config, tokenizer, text)
        retained = [token for token in canonical if token in vocabulary.token_to_id]
        corpus.append(retained)
    return corpus


def build_term_stats_artifact(
    config: AppConfig,
    vocabulary: VocabularyState,
    corpus_tokens: List[List[str]],
) -> Dict[str, Any]:
    document_count = len(corpus_tokens)
    if document_count < 1:
        raise IngestError("BM25 term stats requires at least one document")
    doc_lengths = [len(doc) for doc in corpus_tokens]
    average_document_length = float(sum(doc_lengths)) / float(document_count)
    if average_document_length <= 0.0:
        raise IngestError("BM25 term stats average_document_length must be > 0")
    df_by_token_id: Dict[str, int] = {}
    for document in corpus_tokens:
        for token in set(document):
            token_id = vocabulary.token_to_id.get(token)
            if token_id is None:
                continue
            key = str(token_id)
            df_by_token_id[key] = df_by_token_id.get(key, 0) + 1
    if len(df_by_token_id) == 0:
        raise IngestError("BM25 term stats document_frequency_by_token_id must not be empty")
    return {
        "collection_name": config.qdrant_effective_collection_name,
        "sparse_strategy": {
            "kind": config.sparse_strategy_kind,
            "version": config.sparse_strategy_version,
        },
        "vocabulary_name": require_string(vocabulary.artifact["vocabulary_name"], "SPARSE_VOCABULARY.vocabulary_name"),
        "vocabulary_identity": build_vocabulary_identity(config),
        "document_count": document_count,
        "average_document_length": average_document_length,
        "document_frequency_by_token_id": df_by_token_id,
        "created_at": now_iso_utc(),
    }


def validate_term_stats_artifact(
    config: AppConfig,
    artifact: Dict[str, Any],
    vocabulary_name: str,
    vocabulary_identity: Dict[str, Any],
) -> Bm25StatsState:
    schema = require_dict(load_json_file(TERM_STATS_SCHEMA_PATH), str(TERM_STATS_SCHEMA_PATH))
    try:
        require_exact_keys(artifact, schema["required"], ("vocabulary_identity",), "BM25_TERM_STATS")
        collection_name = require_string(artifact["collection_name"], "BM25_TERM_STATS.collection_name")
        if collection_name != config.qdrant_effective_collection_name:
            raise IngestError("BM25_TERM_STATS.collection_name mismatch")
        sparse_strategy = require_dict(artifact["sparse_strategy"], "BM25_TERM_STATS.sparse_strategy")
        require_exact_keys(sparse_strategy, ("kind", "version"), (), "BM25_TERM_STATS.sparse_strategy")
        if require_string(sparse_strategy["kind"], "BM25_TERM_STATS.sparse_strategy.kind") != config.sparse_strategy_kind:
            raise IngestError("BM25_TERM_STATS.sparse_strategy.kind mismatch")
        if require_string(sparse_strategy["version"], "BM25_TERM_STATS.sparse_strategy.version") != config.sparse_strategy_version:
            raise IngestError("BM25_TERM_STATS.sparse_strategy.version mismatch")
        if require_string(artifact["vocabulary_name"], "BM25_TERM_STATS.vocabulary_name") != vocabulary_name:
            raise IngestError("BM25_TERM_STATS.vocabulary_name mismatch")
        persisted_vocabulary_identity = require_dict(
            artifact.get("vocabulary_identity"),
            "BM25_TERM_STATS.vocabulary_identity",
        )
        if persisted_vocabulary_identity != vocabulary_identity:
            raise IngestError("BM25_TERM_STATS.vocabulary_identity mismatch")
        document_count = require_int(artifact["document_count"], "BM25_TERM_STATS.document_count", 1)
        average_document_length = require_number(
            artifact["average_document_length"], "BM25_TERM_STATS.average_document_length"
        )
        if average_document_length <= 0.0:
            raise IngestError("BM25_TERM_STATS.average_document_length must be > 0")
        df_obj = require_dict(artifact["document_frequency_by_token_id"], "BM25_TERM_STATS.document_frequency_by_token_id")
        if len(df_obj) == 0:
            raise IngestError("BM25_TERM_STATS.document_frequency_by_token_id must not be empty")
        document_frequency_by_token_id: Dict[int, int] = {}
        for key, value in df_obj.items():
            if re.fullmatch(r"(0|[1-9][0-9]*)", key) is None:
                raise IngestError("BM25_TERM_STATS.document_frequency_by_token_id key must be non-negative integer string")
            freq = require_int(value, f"BM25_TERM_STATS.document_frequency_by_token_id.{key}", 1)
            if freq > document_count:
                raise IngestError("BM25_TERM_STATS.document_frequency_by_token_id value must be <= document_count")
            document_frequency_by_token_id[int(key)] = freq
        validate_iso_datetime(
            require_string(artifact["created_at"], "BM25_TERM_STATS.created_at"),
            "BM25_TERM_STATS.created_at",
        )
    except IngestError as exc:
        raise IngestError(str(exc)) from exc

    return Bm25StatsState(
        artifact=artifact,
        created_in_this_run=False,
        document_count=document_count,
        average_document_length=average_document_length,
        document_frequency_by_token_id=document_frequency_by_token_id,
    )


def load_or_create_bm25_stats(
    config: AppConfig,
    vocabulary: VocabularyState,
    corpus_tokens: List[List[str]],
) -> Bm25StatsState:
    if config.sparse_bm25_term_stats_path is None:
        raise ConfigError("CONFIG_PATH.sparse.bm25_like.term_stats_path must be set for bm25_like")
    path = Path(config.sparse_bm25_term_stats_path)
    vocabulary_name = require_string(vocabulary.artifact["vocabulary_name"], "SPARSE_VOCABULARY.vocabulary_name")
    vocabulary_identity = build_vocabulary_identity(config)
    if path.exists():
        loaded = require_dict(load_json_file(path), str(path))
        state = validate_term_stats_artifact(config, loaded, vocabulary_name, vocabulary_identity)
        state.created_in_this_run = False
        return state

    artifact = build_term_stats_artifact(config, vocabulary, corpus_tokens)
    if artifact.get("vocabulary_name") != vocabulary_name:
        raise IngestError("BM25 term stats artifact vocabulary_name mismatch")
    state = validate_term_stats_artifact(config, artifact, vocabulary_name, vocabulary_identity)
    ensure_parent_dir(config.sparse_bm25_term_stats_path)
    path.write_text(json.dumps(artifact, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    state.created_in_this_run = True
    return state


def build_bm25_model(config: AppConfig, corpus_tokens: List[List[str]]) -> Any:
    try:
        from rank_bm25 import BM25Okapi  # type: ignore
    except ModuleNotFoundError as exc:
        raise ConfigError(f"Missing required dependency 'rank_bm25': {exc}") from exc
    if config.sparse_bm25_k1 is None or config.sparse_bm25_b is None or config.sparse_bm25_idf_smoothing is None:
        raise ConfigError("bm25_like strategy config is incomplete")
    epsilon = parse_bm25_epsilon(config.sparse_bm25_idf_smoothing)
    return BM25Okapi(corpus_tokens, k1=config.sparse_bm25_k1, b=config.sparse_bm25_b, epsilon=epsilon)


def build_sparse_vector_bag_of_words(token_ids: List[int]) -> Dict[str, Any]:
    counts = Counter(token_ids)
    indices = sorted(counts.keys())
    values = [float(counts[token_id]) for token_id in indices]
    return {"indices": indices, "values": values}


def build_sparse_vector_bm25_like(
    config: AppConfig,
    token_ids: List[int],
    vocabulary: VocabularyState,
    bm25_model: Any,
    bm25_stats: Bm25StatsState,
) -> Dict[str, Any]:
    if config.sparse_bm25_k1 is None or config.sparse_bm25_b is None:
        raise ConfigError("bm25_like parameters missing")
    token_counts = Counter(token_ids)
    indices = sorted(token_counts.keys())
    values: List[float] = []
    document_length = float(len(token_ids))
    average_document_length = bm25_stats.average_document_length
    if average_document_length <= 0.0:
        raise IngestError("bm25 term stats average_document_length must be > 0")
    for token_id in indices:
        token = vocabulary.id_to_token.get(token_id)
        if token is None:
            values.append(0.0)
            continue
        idf = float(bm25_model.idf.get(token, 0.0))
        tf = float(token_counts[token_id])
        denominator = tf + config.sparse_bm25_k1 * (
            1.0 - config.sparse_bm25_b + config.sparse_bm25_b * (document_length / average_document_length)
        )
        weight = 0.0 if denominator == 0 else idf * ((tf * (config.sparse_bm25_k1 + 1.0)) / denominator)
        values.append(float(weight))
    return {"indices": indices, "values": values}


def build_chunk_sparse_vector(
    config: AppConfig,
    tokenizer: Any,
    vocabulary: VocabularyState,
    chunk_context: ChunkContext,
    bm25_model: Optional[Any],
    bm25_stats: Optional[Bm25StatsState],
) -> Tuple[Dict[str, Any], int]:
    text = require_string(
        resolve_field_path(chunk_context.chunk, config.sparse_text_source),
        f"sparse_text_source chunk_index={chunk_context.chunk_index}",
    )
    canonical_tokens = tokenize_canonical(config, tokenizer, text)
    retained_ids: List[int] = []
    oov_count = 0
    for token in canonical_tokens:
        token_id = vocabulary.token_to_id.get(token)
        if token_id is None:
            oov_count += 1
            continue
        retained_ids.append(token_id)
    if text.strip() != "" and len(retained_ids) == 0:
        raise IngestError("empty sparse vector after normalization and vocabulary lookup")

    if config.sparse_strategy_kind == "bag_of_words":
        vector = build_sparse_vector_bag_of_words(retained_ids)
    elif config.sparse_strategy_kind == "bm25_like":
        if bm25_model is None or bm25_stats is None:
            raise IngestError("bm25_like strategy requires BM25 runtime state")
        vector = build_sparse_vector_bm25_like(config, retained_ids, vocabulary, bm25_model, bm25_stats)
    else:
        raise ConfigError("unsupported sparse strategy")

    indices = vector.get("indices")
    values = vector.get("values")
    if not isinstance(indices, list) or not isinstance(values, list) or len(indices) != len(values):
        raise IngestError("sparse vector must contain aligned indices/values arrays")
    if text.strip() != "" and len(indices) == 0:
        raise IngestError("empty sparse vector for non-empty text")
    return vector, oov_count


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
                inserts.append(chunk_context)
                continue

            point = qdrant_get_point(config, env, chunk_context.point_id)
            if point is None:
                chunk_context.ingest_status = "insert"
                inserts.append(chunk_context)
                continue

            point_payload = require_dict(point.get("payload"), "qdrant_point.payload")
            chunk_fingerprint = compute_fingerprint(config, chunk_context.chunk)
            point_fingerprint = compute_fingerprint(config, point_payload)
            if chunk_fingerprint != point_fingerprint:
                chunk_context.ingest_status = "skip_and_log"
                summary.skipped += 1
                summary.skip_and_log += 1
                log_skipped_chunk(config, chunk_context.chunk, chunk_context.chunk_index)
                continue

            chunk_metadata = build_metadata_comparison_view(chunk_context.chunk, config.fingerprint_fields)
            point_metadata = build_metadata_comparison_view(point_payload, config.fingerprint_fields)
            if chunk_metadata != point_metadata:
                chunk_context.ingest_status = "update"
                updates.append(chunk_context)
            else:
                chunk_context.ingest_status = "skip"
                summary.unchanged += 1
        except Exception as exc:
            summary.failed += 1
            log_failed_chunk(config, chunk_context.chunk, chunk_index, "qdrant", str(exc))
    return inserts, updates


def prepare_sparse_vectors_for_inserts(
    config: AppConfig,
    tokenizer: Any,
    vocabulary: VocabularyState,
    insert_chunks: List[ChunkContext],
    summary: Summary,
    bm25_model: Optional[Any],
    bm25_stats: Optional[Bm25StatsState],
) -> Tuple[List[ChunkContext], int]:
    prepared: List[ChunkContext] = []
    oov_total = 0
    for chunk_context in insert_chunks:
        try:
            sparse_vector, oov_count = build_chunk_sparse_vector(
                config=config,
                tokenizer=tokenizer,
                vocabulary=vocabulary,
                chunk_context=chunk_context,
                bm25_model=bm25_model,
                bm25_stats=bm25_stats,
            )
            chunk_context.sparse_vector = sparse_vector
            chunk_context.oov_token_count = oov_count
            oov_total += oov_count
            prepared.append(chunk_context)
        except Exception as exc:
            summary.failed += 1
            log_failed_chunk(config, chunk_context.chunk, chunk_context.chunk_index, "sparse", str(exc))
    return prepared, oov_total


def process_embedding_batches(
    config: AppConfig,
    env: EnvConfig,
    insert_chunks: List[ChunkContext],
    summary: Summary,
) -> List[ChunkWithRepresentations]:
    results: List[ChunkWithRepresentations] = []
    for batch_index, batch in enumerate(chunked(insert_chunks, config.embedding_max_batch_size)):
        batch_list = list(batch)
        log_runtime(f"embedding batch start batch_index={batch_index} batch_size={len(batch_list)}")
        try:
            texts = [
                require_string(
                    resolve_field_path(item.chunk, config.embedding_text_source),
                    f"text_source chunk_index={item.chunk_index}",
                )
                for item in batch_list
            ]
            embeddings = call_embedding_service(config, env, texts)
            for item, embedding in zip(batch_list, embeddings):
                results.append(ChunkWithRepresentations(item, embedding))
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
                    results.append(ChunkWithRepresentations(item, embedding))
                    log_runtime(f"embedding fallback chunk_index={item.chunk_index} status=success")
                except Exception as item_exc:
                    summary.failed += 1
                    log_failed_chunk(config, item.chunk, item.chunk_index, "embed", str(item_exc))
                    log_runtime(f"embedding fallback chunk_index={item.chunk_index} status=failed error={item_exc}")
    return results


def point_from_representation(config: AppConfig, item: ChunkWithRepresentations) -> Dict[str, Any]:
    sparse_vector = item.chunk_context.sparse_vector
    if not isinstance(sparse_vector, dict):
        raise IngestError("sparse vector missing on prepared insert chunk")
    return {
        "id": item.chunk_context.point_id,
        "vector": {
            config.qdrant_dense_vector_name: item.embedding,
            config.qdrant_sparse_vector_name: sparse_vector,
        },
        "payload": item.chunk_context.chunk,
    }


def process_upsert_batches(
    config: AppConfig,
    env: EnvConfig,
    prepared_chunks: List[ChunkWithRepresentations],
    summary: Summary,
) -> None:
    for batch_index, batch in enumerate(chunked(prepared_chunks, config.qdrant_upsert_batch_size)):
        batch_list = list(batch)
        log_runtime(f"qdrant upsert batch start batch_index={batch_index} batch_size={len(batch_list)}")
        try:
            points = [point_from_representation(config, item) for item in batch_list]
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
                    qdrant_upsert_points(config, env, [point_from_representation(config, item)])
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
        try:
            point = qdrant_get_point(config, env, chunk_context.point_id)
            if point is None:
                raise ExternalServiceError("point missing during update path")
            payload = build_update_payload(config, chunk_context.chunk, require_dict(point["payload"], "point.payload"))
            if payload == {}:
                summary.unchanged += 1
                continue
            qdrant_update_payload(config, env, chunk_context.point_id, payload)
            summary.updated += 1
        except Exception as exc:
            summary.failed += 1
            log_failed_chunk(config, chunk_context.chunk, chunk_index, "qdrant", str(exc))


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
        except Exception as exc:
            summary.failed += 1
            append_jsonl(
                config.failed_chunk_log_path,
                {
                    "chunk_id": chunk.get("chunk_id", ""),
                    "chunk_index": chunk_index,
                    "stage": "validate",
                    "error": str(exc),
                },
            )
    if len(valid_chunks) == 0:
        log_runtime(f"fail-fast reason=no_valid_chunks path={path}")
        raise IngestError(f"no valid chunks after validation in {path}")
    return valid_chunks


def build_manifest(
    config: AppConfig,
    runtime: ManifestRuntime,
    summary: Summary,
    vocabulary_state: Optional[VocabularyState],
    oov_token_count: int,
    status: str,
    completed_at: Optional[str] = None,
    last_error: Optional[str] = None,
) -> Dict[str, Any]:
    vocabulary_name = expected_vocabulary_name(config.qdrant_base_collection_name)
    vocabulary_created = False
    if vocabulary_state is not None and isinstance(vocabulary_state.artifact, dict) and "vocabulary_name" in vocabulary_state.artifact:
        vocabulary_name = require_string(vocabulary_state.artifact["vocabulary_name"], "SPARSE_VOCABULARY.vocabulary_name")
        vocabulary_created = vocabulary_state.created_in_this_run
    sparse_obj: Dict[str, Any] = {
        "strategy_kind": config.sparse_strategy_kind,
        "strategy_version": config.sparse_strategy_version,
        "tokenizer_library": config.sparse_tokenizer_library,
        "tokenizer_source": config.sparse_tokenizer_source,
        "preprocessing_kind": config.sparse_preprocessing_kind,
        "lowercase": config.sparse_lowercase,
        "min_token_length": config.sparse_min_token_length,
        "vocabulary_name": vocabulary_name,
        "vocabulary_created_in_this_run": vocabulary_created,
        "out_of_vocabulary_token_count": max(0, oov_token_count),
    }
    if config.sparse_tokenizer_revision is not None:
        sparse_obj["tokenizer_revision"] = config.sparse_tokenizer_revision

    chunks_processed = summary.created + summary.updated + summary.unchanged
    artifacts: Dict[str, Any] = {
        "vocabulary_path": config.artifacts_vocabulary_path,
        "manifest_path": config.artifacts_manifest_path,
    }
    if config.sparse_strategy_kind == "bm25_like" and config.sparse_bm25_term_stats_path is not None:
        artifacts["term_stats_path"] = config.sparse_bm25_term_stats_path

    manifest: Dict[str, Any] = {
        "run_id": runtime.run_id,
        "status": status,
        "started_at": runtime.started_at,
        "pipeline": {
            "name": config.pipeline_name,
            "ingest_config_version": config.ingest_config_version,
            "corpus_version": config.corpus_version,
        },
        "embedding": {
            "model_name": config.embedding_model_name,
            "dimension": config.embedding_model_dimension,
        },
        "sparse": sparse_obj,
        "qdrant": {
            "collection_name": config.qdrant_effective_collection_name,
            "dense_vector_name": config.qdrant_dense_vector_name,
            "sparse_vector_name": config.qdrant_sparse_vector_name,
            "distance": config.qdrant_collection_distance,
        },
        "artifacts": artifacts,
        "counts": {
            "chunks_total": summary.total,
            "chunks_processed": chunks_processed,
            "chunks_failed": summary.failed,
            "chunks_skipped": summary.skipped,
        },
    }
    if completed_at is not None:
        manifest["completed_at"] = completed_at
    if last_error:
        manifest["last_error"] = last_error
    return manifest


def validate_manifest(manifest: Dict[str, Any]) -> None:
    schema = require_dict(load_json_file(MANIFEST_SCHEMA_PATH), str(MANIFEST_SCHEMA_PATH))
    required = schema.get("required", [])
    require_exact_keys(manifest, required, ("completed_at", "last_error"), "HYBRID_MANIFEST")

    validate_uuid_string(require_string(manifest["run_id"], "HYBRID_MANIFEST.run_id"), "HYBRID_MANIFEST.run_id")
    status = require_string(manifest["status"], "HYBRID_MANIFEST.status")
    if status not in ("running", "completed", "failed"):
        raise IngestError("HYBRID_MANIFEST.status has unsupported value")
    validate_iso_datetime(require_string(manifest["started_at"], "HYBRID_MANIFEST.started_at"), "HYBRID_MANIFEST.started_at")
    if status in ("completed", "failed"):
        if "completed_at" not in manifest:
            raise IngestError("HYBRID_MANIFEST.completed_at required for terminal statuses")
        validate_iso_datetime(
            require_string(manifest["completed_at"], "HYBRID_MANIFEST.completed_at"),
            "HYBRID_MANIFEST.completed_at",
        )
    if status == "running" and "completed_at" in manifest:
        raise IngestError("HYBRID_MANIFEST.completed_at must be absent when status=running")

    counts = require_dict(manifest["counts"], "HYBRID_MANIFEST.counts")
    require_exact_keys(
        counts,
        ("chunks_total", "chunks_processed", "chunks_failed", "chunks_skipped"),
        (),
        "HYBRID_MANIFEST.counts",
    )
    chunks_total = require_int(counts["chunks_total"], "HYBRID_MANIFEST.counts.chunks_total", 0)
    chunks_processed = require_int(counts["chunks_processed"], "HYBRID_MANIFEST.counts.chunks_processed", 0)
    chunks_failed = require_int(counts["chunks_failed"], "HYBRID_MANIFEST.counts.chunks_failed", 0)
    chunks_skipped = require_int(counts["chunks_skipped"], "HYBRID_MANIFEST.counts.chunks_skipped", 0)
    if chunks_total != chunks_processed + chunks_failed + chunks_skipped:
        raise IngestError("HYBRID_MANIFEST counts invariant violated")


def write_manifest(config: AppConfig, manifest: Dict[str, Any]) -> None:
    validate_manifest(manifest)
    ensure_parent_dir(config.artifacts_manifest_path)
    Path(config.artifacts_manifest_path).write_text(
        json.dumps(manifest, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def print_normal_summary(summary: Summary, report_only: bool) -> int:
    print(
        f"chunks={summary.total} created={summary.created} updated={summary.updated} "
        f"unchanged={summary.unchanged} skipped={summary.skipped} "
        f"skip_and_log={summary.skip_and_log} failed={summary.failed}"
    )
    if summary.failed > 0:
        if report_only:
            print("WARN: hybrid ingest completed with failures")
            return 0
        print("FAIL: hybrid ingest failed")
        return 1
    print("OK: hybrid ingest completed")
    return 0


def run_ingest(
    chunks_path: Path,
    config: AppConfig,
    env: EnvConfig,
    report_only: bool,
    summary: Summary,
) -> Tuple[int, VocabularyState, int]:
    valid_chunks = load_and_validate_chunks(chunks_path, config, summary)
    vocabulary = VocabularyState(artifact={}, token_to_id={}, id_to_token={}, created_in_this_run=False)
    vocabulary_identity = build_vocabulary_identity(config)

    collection_status, collection_body = qdrant_get_collection(config, env)
    collection_created_in_run = False
    if collection_status == "missing":
        if not config.qdrant_create_if_missing:
            print("SKIP: collection does not exist and create_if_missing=false")
            return 0, vocabulary, 0
        qdrant_create_collection(config, env, vocabulary_identity)
        collection_created_in_run = True
    else:
        compatibility_errors = extract_collection_compatibility_errors(
            config,
            require_dict(collection_body, "collection_body"),
            vocabulary_identity,
        )
        if compatibility_errors:
            raise IngestError("; ".join(compatibility_errors))

    tokenizer = init_sparse_tokenizer(config)
    vocabulary = load_or_create_vocabulary(config, tokenizer, valid_chunks)

    bm25_model: Optional[Any] = None
    bm25_stats: Optional[Bm25StatsState] = None
    if config.sparse_strategy_kind == "bm25_like":
        corpus_tokens = build_corpus_tokens(config, tokenizer, valid_chunks, vocabulary)
        bm25_stats = load_or_create_bm25_stats(config, vocabulary, corpus_tokens)
        bm25_model = build_bm25_model(config, corpus_tokens)

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
    sparse_ready_inserts, oov_total = prepare_sparse_vectors_for_inserts(
        config=config,
        tokenizer=tokenizer,
        vocabulary=vocabulary,
        insert_chunks=inserts,
        summary=summary,
        bm25_model=bm25_model,
        bm25_stats=bm25_stats,
    )
    chunk_embeddings = process_embedding_batches(config, env, sparse_ready_inserts, summary)
    process_upsert_batches(config, env, chunk_embeddings, summary)
    process_updates(config, env, updates, summary)

    return print_normal_summary(summary, report_only), vocabulary, oov_total


def main() -> None:
    args = parse_args()
    exit_code = 1
    summary = Summary()
    vocabulary_state: Optional[VocabularyState] = None
    oov_total = 0
    config: Optional[AppConfig] = None
    manifest_runtime: Optional[ManifestRuntime] = None
    log_runtime("run start")
    try:
        config, env = load_runtime_config(Path(args.config_path), Path(args.env_file_path))
        manifest_runtime = parse_manifest_runtime(config.artifacts_manifest_path)
        write_manifest(
            config,
            build_manifest(
                config=config,
                runtime=manifest_runtime,
                summary=summary,
                vocabulary_state=vocabulary_state,
                oov_token_count=oov_total,
                status="running",
            ),
        )
        exit_code, vocabulary_state, oov_total = run_ingest(
            Path(args.chunks_path),
            config,
            env,
            bool(args.report_only),
            summary,
        )
        write_manifest(
            config,
            build_manifest(
                config=config,
                runtime=manifest_runtime,
                summary=summary,
                vocabulary_state=vocabulary_state,
                oov_token_count=oov_total,
                status="completed" if exit_code == 0 else "failed",
                completed_at=now_iso_utc(),
            ),
        )
    except SystemExit as exc:
        exit_code = int(exc.code)
        raise
    except IngestError as exc:
        print(f"FAIL: {exc}")
        exit_code = 1
        if config is not None and manifest_runtime is not None:
            try:
                write_manifest(
                    config,
                    build_manifest(
                        config=config,
                        runtime=manifest_runtime,
                        summary=summary,
                        vocabulary_state=vocabulary_state,
                        oov_token_count=oov_total,
                        status="failed",
                        completed_at=now_iso_utc(),
                        last_error=str(exc),
                    ),
                )
            except Exception as manifest_exc:
                log_runtime(f"manifest write failed error={manifest_exc}")
    finally:
        log_runtime(f"exit code={exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

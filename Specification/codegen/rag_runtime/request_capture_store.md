## 1) Purpose / Scope

`request_capture_store` persists `RequestCapture` values into request-capture storage.

This module:
- receives a fully assembled `RequestCapture`;
- validates `RequestCapture` before attempting persistence;
- maps `RequestCapture` into the storage representation required by `request_captures` through a dedicated internal storage row mapper;
- writes one request-capture record to PostgreSQL.

This module does not:
- assemble `RequestCapture`;
- perform input validation;
- perform retrieval;
- perform generation;
- compute evals;
- write `judge_*_results`;
- write `request_summaries`;
- read raw TOML directly;
- read raw environment variables directly.

## 2) Public Interface

```rust
pub struct RequestCaptureStore;

impl RequestCaptureStore {
    pub async fn store(
        capture: RequestCapture,
        settings: &RequestCaptureSettings,
    ) -> Result<(), RagRuntimeError>;
}
```

Interface rules:

- the interface must be async;
- the interface must consume `RequestCapture`;
- the interface must receive `&RequestCaptureSettings` explicitly;
- the interface must return `Result<(), RagRuntimeError>`;
- module-internal logic uses `RequestCaptureStoreError` before conversion to `RagRuntimeError`.

## 3) Input And Output Types

Input types:

- `RequestCapture`
- `RequestCaptureSettings`

Output types:

- none on success

Type rules:

- `RequestCapture` must follow the shared type contract defined in `Specification/codegen/rag_runtime/rag_runtime.md`;
- the semantic contract for `RequestCapture` is defined in `Specification/contracts/rag_runtime/request_capture.md`;
- the machine-readable schema for `RequestCapture` is `Execution/rag_runtime/schemas/request_capture.schema.json`;
- `RequestCaptureSettings` must be the typed settings section from `Settings.request_capture`.

## 4) Configuration Usage

`request_capture_store` must read only its own settings section:

- `Settings.request_capture`

For the current version, required `RequestCaptureSettings` fields are:

- `postgres_url`

The module must not:

- read raw TOML directly;
- read raw config maps directly;
- read raw environment variables directly;
- read settings that belong to input validation, retrieval, generation, or observability.

## 5) Validation Rules Before Write

Before attempting persistence, the module must validate the incoming `RequestCapture`.

Validation must follow the machine-readable schema defined in:

- `Execution/rag_runtime/schemas/request_capture.schema.json`

Validation must also enforce the required pre-write invariants derived from the storage compatibility contract defined in:

- `Specification/contracts/storage/request_captures_storage.md`

For the current version, the required pre-write invariants derived from storage compatibility include:

- `total_tokens = prompt_tokens + completion_tokens`

Validation failure is a module error and must be reported before any database write is attempted.

## 6) Storage Mapping Contract

The persistence target for this module is:

- table: `request_captures`

The canonical storage contract is defined in:

- `Specification/contracts/storage/request_captures_storage.md`

The executable SQL schema is defined in:

- `Execution/docker/postgres/init/001_request_captures.sql`

The module must define one internal mapping helper:

- `RequestCaptureStorageRowMapper`

`RequestCaptureStorageRowMapper` is the required internal boundary between domain `RequestCapture` and storage-facing write payload construction.

`RequestCaptureStorageRowMapper` responsibilities:

- accept a validated `RequestCapture`;
- construct the exact storage-facing payload used for insertion into `request_captures`;
- serialize `retrieval_results` into the JSON representation required by the storage contract;
- serialize `retrieval_stage_metrics` into the JSON representation required by the storage contract; write SQL `NULL` when the field is `None`;
- serialize `reranking_stage_metrics` into the JSON representation required by the storage contract; write SQL `NULL` when the field is `None`;
- preserve final reranked item order during payload construction;
- exclude storage-only fields that are produced by PostgreSQL itself, including `stored_at`.

`RequestCaptureStorageRowMapper` must not:

- perform database I/O;
- swallow validation or serialization failure;
- invent alternative storage field names or meanings.

Mapping rules:

- scalar `RequestCapture` fields map to same-meaning scalar columns in `request_captures`;
- `reranker_kind` must be serialized as the canonical text form of the semantic enum `RerankerKind`;
- `reranker_config` must be serialized as JSON and written to the `reranker_config` `jsonb` column;
- `retrieval_results` must be serialized as JSON and written to the `retrieval_results` `jsonb` column;
- `retrieval_results` item order must be preserved during serialization;
- each serialized retrieval item must preserve both `retrieval_score` and `rerank_score`;
- `retrieval_stage_metrics` must be serialized as JSON and written to the `retrieval_stage_metrics` `jsonb` column; `None` must be written as SQL `NULL`;
- `reranking_stage_metrics` must be serialized as JSON and written to the `reranking_stage_metrics` `jsonb` column; `None` must be written as SQL `NULL`;
- the JSON shape of `retrieval_stage_metrics` and `reranking_stage_metrics` must follow the `RetrievalQualityMetrics` shape defined in `Specification/contracts/rag_runtime/request_capture.md`;
- storage-specific fields that are not part of `RequestCapture`, including `stored_at`, must be produced by the storage layer rather than by the incoming `RequestCapture` value;
- the module must not invent alternative column meanings or alternative storage field names that diverge from the storage contract.

## 7) Duplicate Handling

Duplicate handling rules:

- `request_id` is the stable request-level identity key;
- if a row for the same `request_id` already exists, the store operation must fail with a duplicate-request module error;
- the current version must not silently overwrite, upsert, or merge an existing request capture row.

## 8) Store Failure Behavior

If persistence fails, `request_capture_store` must return a store-module failure to the caller.

This module must not:

- silently swallow persistence failures;
- convert persistence failure into synthetic success.

## 9) Error Model

The module must define:

- `RequestCaptureStoreError`

Required failure categories:

- request-capture validation failure;
- request-capture serialization failure;
- PostgreSQL connection failure;
- insert execution failure;
- duplicate request id;
- unexpected internal state.

Error rules:

- raw database client errors must not leak through the public module interface;
- module-level errors must preserve available diagnostic information;
- module-level errors must be converted to `RagRuntimeError` at module boundary.

## 10) Implementation Notes

The generated implementation must use:

- `jsonschema` for validation against `Execution/rag_runtime/schemas/request_capture.schema.json`;
- `serde` for typed serialization support;
- `serde_json` for JSON serialization of `retrieval_results`;
- `sqlx` for PostgreSQL access;
- `chrono` for timestamp handling.

Implementation rules:

- SQL statements must use parameterized queries;
- handwritten SQL string interpolation with embedded values is forbidden;
- handwritten JSON string construction is forbidden;
- PostgreSQL constraints are the final storage-level enforcement layer, not the first validation layer.

## 11) Orchestration Integration

`orchestration` is responsible for:

- assembling the domain `RequestCapture` value;
- passing `RequestCapture` and `&Settings.request_capture` to `request_capture_store` after a successful completed request.

`orchestration` must not:

- build storage-specific row shapes;
- serialize SQL payloads;
- issue direct SQL insert statements for `request_captures`.

## 12) Unit Test Requirements

Required generated unit tests for `request_capture_store` are defined in:

- `Specification/codegen/rag_runtime/unit_tests.md`

Generation for `request_capture_store` is incomplete if any required unit test for this module from `Specification/codegen/rag_runtime/unit_tests.md` is missing.

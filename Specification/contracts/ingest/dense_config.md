# Dense Ingest Config Contract

This document defines the contract for `CONFIG_PATH` used by `dense_ingest.py`.

## Format

`CONFIG_PATH` is a TOML ingest pipeline config file.
It must be read through a TOML parser:
- if `tomllib` is available in the current Python, use `tomllib`
- otherwise `tomli` is allowed

`CONFIG_PATH` is the source of truth for pipeline behavior.

Invalid `CONFIG_PATH`:
- `CONFIG_PATH` is invalid if TOML does not parse, if a required section or field is missing, if a value type does not match the contract, or if a value violates the constraints of this contract
- this is a whole-run error
- ingest must exit immediately
- such errors do not belong in failed chunk log

## Expected Structure

`[pipeline]`
- `name`: ingest pipeline name
- `chunk_schema_version`: chunk schema version compatible with this ingest pipeline
- `ingest_config_version`: version of the current ingest configuration
- `corpus_version`: human-readable version of the indexed corpus, for example `v1`
- `chunking_strategy`: chunking strategy applied to produce this corpus; allowed values: `structural`, `fixed`

`[embedding.model]`
- `name`: embedding model name
- `dimension`: expected dense vector length

`[embedding.input]`
- `text_source`: chunk field used as embedding input text

`[embedding.transport]`
- `timeout_sec`: timeout for HTTP request to the embedding service, in seconds
- `max_batch_size`: maximum number of texts in one request batch to the embedding service

`[embedding.retry]`
- `max_attempts`: maximum number of retry attempts for embedding requests
- `backoff`: backoff strategy type for embedding requests

`[qdrant.collection]`
- `name`: Qdrant collection name
- `distance`: distance metric for collection vectors
- `vector_name`: logical vector name
- `create_if_missing`: whether collection should be created if missing

`[qdrant.point_id]`
- `strategy`: how stable point identity is built
- `namespace_uuid`: fixed UUID namespace for deterministic point id derivation
- `format`: point id format

`[qdrant.transport]`
- `timeout_sec`: timeout for any HTTP request to Qdrant, in seconds
- `upsert_batch_size`: batch size for Qdrant upsert

`[qdrant.retry]`
- `max_attempts`: maximum number of retry attempts for Qdrant HTTP requests
- `backoff`: backoff strategy type for Qdrant HTTP requests

Fingerprint is the minimal set of fields used to decide whether a new embedding is needed for an existing point.
Fingerprint in this document applies only to point-level comparison between `chunk` and existing `point`.
Collection-level embedding representation changes, including embedding model change or vector dimension change, must not be encoded through `idempotency.fingerprint_fields`.

`[idempotency]`
- `strategy`: how representation fingerprint is built
- `fingerprint_fields`: tuple of fields used to compute fingerprint
- `on_fingerprint_change`: action when fingerprint changes
- `on_metadata_change`: action on metadata-only change

`[logging]`
- `failed_chunk_log_path`: path to JSONL log for hard failures
- `skipped_chunk_log_path`: path to JSONL log for skipped chunks

## Semantics Of Config Values

Below are config field values that are not arbitrary strings, but part of the ingest contract.

Field references to `chunk` fields:
- if a config field reference points to a field of `chunk`, it must use the explicit root `chunk`
- valid examples:
  - `chunk.text`
  - `chunk.content_hash`
  - `chunk.ingest.ingested_at`
- when resolving such a field reference, the implementation must treat `chunk` as the root entity name
- the implementation must not interpret the `chunk` prefix as a literal key that has to exist inside an already loaded chunk payload

`qdrant.point_id.strategy`
- `uuid5(chunk.chunk_id)` means:
  - `point.id` value is computed as UUIDv5
  - UUIDv5 name is taken from `chunk["chunk_id"]`
  - UUIDv5 namespace is taken from `CONFIG_PATH.qdrant.point_id.namespace_uuid`
  - for the same `chunk["chunk_id"]` and the same `namespace_uuid`, `point_id` must always be the same

`qdrant.point_id.namespace_uuid`
- means:
  - it is a canonical UUID string
  - it is a fixed namespace UUID that must be used in all `point_id` computations
  - a new namespace must not be generated per run, per batch, or per chunk

`qdrant.point_id.format`
- `canonical_uuid` means:
  - value is serialized as canonical UUID string
  - UUID must be computed deterministically from `chunk["chunk_id"]` and `CONFIG_PATH.qdrant.point_id.namespace_uuid`

`idempotency.strategy`
- `field_tuple_hash` means a specific fingerprint construction method:
  - fields defined in `idempotency.fingerprint_fields` must be taken from `chunk` or from `point` payload for which fingerprint is being computed
  - each field value must be canonicalized
  - canonicalized values must be assembled into an ordered tuple in the same order
  - fingerprint must be computed as deterministic hash of that tuple
  - canonicalization rules:
    - string -> byte-for-byte exactly as stored in the `chunk` field or `point` payload field; no whitespace normalization, trimming, or case normalization is allowed
    - int -> decimal string
    - list/dict -> deterministic JSON serialization with stable key ordering and no extra whitespace

`idempotency.fingerprint_fields`
- list of field references only from `chunk` payload that affect the decision whether a new embedding is needed for a point
- the same field references must be applied to existing `point` payload when computing its fingerprint
- collection-level settings, including `CONFIG_PATH.embedding.model.name` and `CONFIG_PATH.embedding.model.dimension`, do not belong in `idempotency.fingerprint_fields`
- if any field from this list changes, fingerprint is considered changed
- fields outside this list must not change fingerprint by themselves

`idempotency.on_fingerprint_change`
- `log_and_skip` means:
  - point must not be modified
  - new embedding must not be computed
  - new point must not be created
  - `chunk` must receive `ingest_status = skip_and_log`
  - chunk must be written to skipped chunk log
  - this is not a hard failure

`idempotency.on_metadata_change`
- `update_changed_fields` means:
  - update path is allowed only if fingerprint is unchanged
  - only actually changed payload fields outside fingerprint-defined representation must be updated
  - runtime field `ingest.ingested_at` must be ignored when deciding whether metadata changed
  - difference only in `ingest.ingested_at` must not trigger `ingest_status = update`
  - `text` must not be updated
  - new embedding must not be computed
  - update request to Qdrant must send full merged payload of the target point, not a partial payload fragment
  - implementation must read existing point payload, apply allowed metadata changes, and send resulting full payload object
  - nested `ingest` object must be updated to values of the current ingest run

`qdrant.collection.create_if_missing`
- `true` means:
  - ingest must check whether collection exists
  - if collection is missing, ingest must create it before processing chunks
- `false` would mean:
  - if collection is missing, ingest must exit before processing chunks

`qdrant.collection.vector_name`
- `default` means:
  - collection uses one dense vector
  - vector payload on Qdrant side is sent as single unnamed/default vector, not as multi-vector mapping

`qdrant.collection.distance`
- this string value must directly define Qdrant distance metric for the collection

`pipeline.chunking_strategy`
- identifies the chunking strategy applied to produce this corpus
- allowed values: `structural`, `fixed`
- this value must be written to the Qdrant collection metadata under the key `chunking_strategy` when the collection is created
- it must be verified against the existing collection metadata when the collection already exists; a mismatch is a compatibility error

`pipeline.corpus_version`
- human-readable version identifier of the indexed corpus
- valid examples:
  - `v1`
  - `v2`
  - `v3`
- this value must change when corpus contents change
- corpus-content change includes:
  - document addition
  - document removal
  - document replacement
  - re-chunking
  - material cleanup or extraction change that changes the indexed corpus
- this value is corpus data versioning, not application versioning

`embedding.retry.backoff`
- `exponential` means:
  - delay between retry attempts must grow exponentially
  - implementation may choose a specific formula, but growth must be exponential, not constant or linear

`qdrant.retry.backoff`
- `exponential` means:
  - delay between retry attempts must grow exponentially
  - implementation may choose a specific formula, but growth must be exponential, not constant or linear

`logging.failed_chunk_log_path`
- path to JSONL file of hard failures
- only hard failures must be written to this file

`logging.skipped_chunk_log_path`
- path to JSONL file of skipped chunks
- only fingerprint-change skips must be written to this file

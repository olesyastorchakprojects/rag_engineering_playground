# Hybrid Ingest Delta Spec

This document defines `hybrid_ingest.py` as a delta-spec on top of:

- [dense.md](/home/olesia/code/prompt_gen_proj/Specification/codegen/ingest/dense.md)

Hybrid-specific source-of-truth companions for this delta-spec are:

- `Specification/contracts/ingest/hybrid_config.md`
- `Specification/contracts/ingest/common/sparse_vocabulary.md`
- `Specification/contracts/ingest/hybrid_manifest.md`
- `Specification/contracts/ingest/common/sparse_text_space.md`
- `Specification/contracts/ingest/common/sparse_strategies/bag_of_words.md`
- `Specification/contracts/ingest/common/sparse_strategies/bm25_like.md`
- `Specification/contracts/ingest/common/bm25_term_stats.md`
- `Execution/ingest/schemas/hybrid_ingest_config.schema.json`
- `Execution/ingest/schemas/common/sparse_vocabulary.schema.json`
- `Execution/ingest/schemas/common/bm25_term_stats.schema.json`
- `Execution/ingest/schemas/hybrid_ingest_manifest.schema.json`

`hybrid_ingest.py` is a Python CLI ingest module.
It is a dense-ingest-style script with the hybrid delta defined here, not a
separate ingest family with a new mental model.

Implementation-output rule:

- the generated implementation must still be one Python script: `hybrid_ingest.py`
- that script should be implemented as a dense-ingest-style script plus the
  hybrid delta defined in this document
- do not split shared ingest logic into a new shared helper module as part of
  this generation task
- local helper functions inside `hybrid_ingest.py` are still allowed, exactly as
  in dense ingest

## 1) Inheritance Rule

All dense-ingest rules from [dense.md](/home/olesia/code/prompt_gen_proj/Specification/codegen/ingest/dense.md)
apply to `hybrid_ingest.py` unless this document explicitly overrides them.

This inheritance includes:

- CLI shape and argument meaning
- `CHUNKS_PATH` format and chunk validation
- `ENV_FILE_PATH` parsing rules
- use of the shared repository-root `.env` file as the runtime env source
- whole-run vs chunk-level failure-domain boundaries
- retry and fallback rules for embedding requests
- point-id derivation
- idempotency and fingerprint-field semantics
- payload-level chunk compatibility expectations
- logging/result reporting semantics
- implementation constraints for Python structure and stdlib-first I/O

`hybrid_ingest.py` must remain recognizably the same ingest pipeline family as
`dense_ingest.py`.

## 2) Purpose / Scope

`hybrid_ingest.py` does everything `dense_ingest.py` does, plus sparse-side
preparation required for hybrid retrieval.

For each valid chunk, hybrid ingest must prepare:

- one dense embedding
- one sparse vector
- one canonical payload
- one hybrid-ready Qdrant point that stores all of the above under one stable `point_id`

This module does not:

- perform retrieval
- perform reranking
- perform generation
- introduce a second external model-serving dependency for sparse representation

## 3) Reused Dense Behavior

The following behavior is inherited unchanged from dense ingest:

- the same `--chunks`, `--config`, `--env-file`, and `--report-only` CLI surface
- the same shared repository-root `.env` usage
- the same chunk schema:
  - `Execution/schemas/chunk.schema.json`
- the same additional validation rule:
  - `chunk.page_end >= chunk.page_start`
- the same embedding-service contract
- the same fallback from failed embedding batch to per-chunk embedding
- the same `qdrant.point_id` semantics
- the same `idempotency.strategy`
- the same `idempotency.fingerprint_fields`
- the same `idempotency.on_fingerprint_change = log_and_skip`
- the same `idempotency.on_metadata_change = update_changed_fields`
- the same failed-chunk log and skipped-chunk log semantics

Hybrid ingest does not define a separate env contract and must continue to use
the same repository-root `.env` file as dense ingest.

## 4) Hybrid-Specific Additions

### 4.1 Config Surface

Hybrid ingest has its own config contract surface and must not reuse dense
config with ad hoc extra keys.

Relative to dense ingest, hybrid config adds:

- `[sparse.strategy]`
  - `kind`
  - `version`
- `[sparse.input]`
  - `text_source`
- `[sparse.tokenizer]`
  - `library`
  - `source`
  - `revision`, when present
- `[sparse.preprocessing]`
  - `kind`
  - `lowercase`
  - `min_token_length`
- `[sparse.bag_of_words]`
  - `document`
  - `query`
- `[sparse.bm25_like]`
  - `document`
  - `query`
  - `k1`
  - `b`
  - `idf_smoothing`
- `[artifacts]`
  - `manifest_path`
- `[qdrant.collection]`
  - `dense_vector_name`
  - `sparse_vector_name`

Rules:

- `dense_vector_name` and `sparse_vector_name` must be distinct
- artifact paths must be derived by the implementation as repository-root-relative
  paths under `Execution/ingest/hybrid/artifacts/`
- repository-root-relative artifact paths must be resolved against repository
  root, not against the current working directory
- artifact paths must not be derived from `CHUNKS_PATH`

Concrete current baseline:

- `sparse.strategy.kind = "bag_of_words"`
- `sparse.strategy.version = "v1"`
- `sparse.tokenizer.library = "tokenizers"`
- `sparse.preprocessing.kind = "basic_word_v1"`

### 4.1.1 Sparse Strategy Selection

Hybrid ingest must read `CONFIG_PATH.sparse.strategy.kind` and dispatch sparse
vector construction through the matching shared strategy contract.

For the current version:

- if `kind = "bag_of_words"`, use:
  - `Specification/contracts/ingest/common/sparse_strategies/bag_of_words.md`
- if `kind = "bm25_like"`, use:
  - `Specification/contracts/ingest/common/sparse_strategies/bm25_like.md`
- any other value is a config error

Strategy selection affects:

- point-side sparse weight semantics
- query-side sparse weight semantics
- required runtime artifacts
- required strategy-owned config block
- required implementation dependency
- collection naming suffix
- collection compatibility identity

Strategy-owned config rule:

- if `kind = "bag_of_words"`, config must contain `[sparse.bag_of_words]`
- if `kind = "bm25_like"`, config must contain `[sparse.bm25_like]`
- strategy-specific weight semantics must be read from the selected block, not
  from a shared cross-strategy weights section

Strategy dependency rule:

- `bag_of_words` may be implemented with local deterministic logic
- `bm25_like` must use the library required by:
  - `Specification/contracts/ingest/common/sparse_strategies/bm25_like.md`
- `bm25_like` term statistics artifact must conform to:
  - `Specification/contracts/ingest/common/bm25_term_stats.md`
  - `Execution/ingest/schemas/common/bm25_term_stats.schema.json`

### 4.2 Singleton Vocabulary

Hybrid ingest introduces one sparse vocabulary mapping for one target collection.

Vocabulary semantics:

- vocabulary is a singleton keyed by the configured base collection name
  `CONFIG_PATH.qdrant.collection.name`
- vocabulary maps sparse token identity to stable token id
- vocabulary is created during ingest if it does not already exist
- vocabulary path is derived by the implementation
- vocabulary is immutable after first successful creation

Immutability rule:

- if vocabulary already exists, hybrid ingest must load and reuse it
- hybrid ingest must not append new token ids into an existing vocabulary
- hybrid ingest must not reorder ids in an existing vocabulary
- hybrid ingest must not silently rebuild vocabulary in place

Vocabulary naming rule:

- `vocabulary_name = "{CONFIG_PATH.qdrant.collection.name}__sparse_vocabulary"`
- the vocabulary artifact path must be the repository-root-relative path:
  `Execution/ingest/hybrid/artifacts/vocabularies/{CONFIG_PATH.qdrant.collection.name}__sparse_vocabulary.json`
- hybrid ingest must resolve that path against repository root
- the serialized vocabulary artifact must also store
  `collection_name = CONFIG_PATH.qdrant.collection.name`
  and `vocabulary_name`

### 4.3 Sparse Vector Generation

For every valid chunk, hybrid ingest must create a sparse vector in addition to
the dense embedding.

Sparse vector shape:

- `indices`: ordered integer token ids
- `values`: numeric weights aligned with `indices`

Rules:

- sparse vector generation must be deterministic
- sparse vector generation must use `CONFIG_PATH.sparse.input.text_source`
- sparse vector generation must use the singleton vocabulary for token ids
- every token occurrence is first converted into a canonical token string using
  the sparse text-space contract
- every canonical token string is mapped to integer token id through the
  singleton vocabulary
- per-point sparse vectors must use unique token ids
- if one token occurs multiple times in the chunk, all occurrences must be
  aggregated into one sparse value for that token id
- `indices` must be sorted in ascending numeric order before point assembly
- empty sparse vectors are invalid for non-empty chunk text
- if non-empty chunk text yields no retained in-vocabulary tokens after
  normalization and vocabulary lookup, the sparse vector is still considered
  empty and therefore invalid
- sparse vector generation failure is a chunk-level failure

### 4.4 Sparse Text Space

Sparse token extraction and normalization are defined by:

- `Specification/contracts/ingest/common/sparse_text_space.md`

Current sparse-strategy execution semantics are defined by:

- `Specification/contracts/ingest/common/sparse_strategies/bag_of_words.md`
- `Specification/contracts/ingest/common/sparse_strategies/bm25_like.md`

Hybrid ingest must use those documents as the source of truth for:

- tokenizer kind
- normalization rules
- token acceptance/rejection rules
- token ordering before vocabulary assignment
- token-id assignment bootstrap order

### 4.5 Additional Artifacts

Required additional artifacts:

derived vocabulary artifact path
- serialized singleton vocabulary for this collection

`CONFIG_PATH.artifacts.manifest_path`
- JSON run manifest whose semantic contract is defined by:
  - `Specification/contracts/ingest/hybrid_manifest.md`
- and whose machine-readable schema is:
  - `Execution/ingest/schemas/hybrid_ingest_manifest.schema.json`

derived BM25 term-stats artifact path, when
`CONFIG_PATH.sparse.strategy.kind = "bm25_like"`
- JSON corpus-statistics artifact whose semantic contract is defined by:
  - `Specification/contracts/ingest/common/bm25_term_stats.md`
- and whose machine-readable schema is:
  - `Execution/ingest/schemas/common/bm25_term_stats.schema.json`

BM25-like artifact lifecycle rule:

- if `sparse.strategy.kind = "bm25_like"`, hybrid ingest must resolve term stats
  before any point processing begins
- the BM25 term-stats artifact path must be:
  `Execution/ingest/hybrid/artifacts/term_stats/<effective_collection_name>__term_stats.json`
- that path is repository-root-relative and must be resolved against repository
  root
- if that derived term-stats path already exists, hybrid ingest must load and validate it
- if that derived term-stats path does not exist, hybrid ingest must build corpus-level
  term stats from the full validated `CHUNKS_PATH`, persist the artifact, and
  only then continue to per-chunk point preparation
- if an existing term-stats artifact is unreadable, schema-invalid, or
  incompatible with the current effective collection name, sparse strategy
  identity, or vocabulary identity, the run must fail before chunk processing
- hybrid ingest must not silently overwrite an incompatible existing
  term-stats artifact in place

Manifest naming rule:

- the basename of `CONFIG_PATH.artifacts.manifest_path` must be `run_manifest.json`
- the parent directory name of `CONFIG_PATH.artifacts.manifest_path` must be
  `<started_at>_<run_id>` where:
  - `started_at` is a filesystem-safe UTC timestamp
  - `run_id` is the ingest run UUID
- the manifest path should live under:
  - `Execution/ingest/hybrid/artifacts/manifests/<started_at>_<run_id>/run_manifest.json`
- `CONFIG_PATH.artifacts.manifest_path` is repository-root-relative and must be
  resolved against repository root

## 5) Hybrid-Specific Overrides

### 5.1 Collection Creation Overrides Dense Ingest

This section overrides dense-ingest collection-creation semantics.
Hybrid collection must be created as a collection that is compatible with:

- one dense vector slot named `CONFIG_PATH.qdrant.collection.dense_vector_name`
- one sparse vector slot named `CONFIG_PATH.qdrant.collection.sparse_vector_name`
- dense vector size equal to `CONFIG_PATH.embedding.model.dimension`
- dense vector distance equal to `CONFIG_PATH.qdrant.collection.distance`

Hybrid ingest must not treat the target collection as dense-only.

Collection naming rule:

- `CONFIG_PATH.qdrant.collection.name` is the configured base collection name
- hybrid ingest must derive the effective Qdrant collection name automatically
- derived strategy suffix must be selected through this exact mapping:
  - `bag_of_words` -> `bow`
  - `bm25_like` -> `bm25`
- effective collection name must equal:
  - `<CONFIG_PATH.qdrant.collection.name>_<derived_strategy_suffix>`
- changing sparse strategy should normally imply changing only the derived
  effective collection name, not the configured base name
- this is sufficient for the current contract because only
  `CONFIG_PATH.sparse.strategy.version = "v1"` is supported
- if another strategy version is added later, collection naming rules must be
  revised or a different base collection name must be used

Base-name validation rule:

- `CONFIG_PATH.qdrant.collection.name` must not already end with `_bow` or
  `_bm25`
- `CONFIG_PATH.qdrant.collection.name` must not end with `_`
- if those constraints are violated, config loading must fail with config error
- effective collection name must be formed by exactly one concatenation step and
  must not be post-processed by additional normalization

Collection metadata must include:

- `embedding_model_name`
- `chunking_strategy`
- `sparse_strategy_kind`
- `sparse_strategy_version`
- `corpus_version`
- `vocabulary_identity`

`vocabulary_identity` must be stored as a JSON object, not as an opaque string
or implementation-defined hash.

For the current version it must contain:

- `collection_name`
- `tokenizer_library`
- `tokenizer_source`
- `tokenizer_revision`, when present
- `preprocessing_kind`
- `lowercase`
- `min_token_length`

The values in `vocabulary_identity` must match the active config and the loaded
vocabulary artifact exactly.

Qdrant collection-creation endpoint:

- `PUT /collections/{effective_collection_name}`

Confirmed Qdrant API direction:

- dense vectors are configured in `vectors`
- sparse vectors are configured in `sparse_vectors`

This request shape was confirmed against the local Qdrant runtime that reported:

- version `1.16.3`
- image reference `qdrant/qdrant:latest`

For the current design, hybrid ingest must create a collection body equivalent
in shape to:

```json
{
  "vectors": {
    "<dense_vector_name>": {
      "size": 1024,
      "distance": "Cosine"
    }
  },
  "sparse_vectors": {
    "<sparse_vector_name>": {}
  },
  "metadata": {
    "embedding_model_name": "<embedding_model_name>",
    "chunking_strategy": "<chunking_strategy>",
    "sparse_strategy_kind": "<sparse_strategy_kind>",
    "sparse_strategy_version": "<sparse_strategy_version>",
    "corpus_version": "<corpus_version>",
    "vocabulary_identity": {
      "collection_name": "<collection_name>",
      "tokenizer_library": "<tokenizer_library>",
      "tokenizer_source": "<tokenizer_source>",
      "preprocessing_kind": "<preprocessing_kind>",
      "lowercase": true,
      "min_token_length": 2
    }
  }
}
```

### 5.2 Collection Compatibility Checks Override Dense Ingest

This section extends dense-ingest compatibility checks.
Before chunk processing begins, hybrid ingest must call:

- `GET /collections/{effective_collection_name}`

and inspect collection metadata from:

- `result.config.params.vectors`
- `result.config.params.sparse_vectors`
- `result.config.metadata`

Compatibility rule:

- `result.config.params.sparse_vectors` must be present
- if `sparse_vectors` is missing, the collection is not hybrid-compatible and
  the run must fail before chunk processing

Hybrid ingest must fail the whole run if the existing collection is
incompatible with any of the following:

- dense vector slot name
- sparse vector slot name
- dense vector dimension
- dense distance metric
- chunking strategy (`chunking_strategy` in collection metadata)
- sparse strategy identity
- sparse strategy version
- vocabulary identity

For `vocabulary identity`, compatibility means exact field-by-field equality of
the `vocabulary_identity` JSON object stored in collection metadata against the
current run's expected vocabulary identity.

Hybrid ingest must not silently mutate an incompatible dense-only collection
into a hybrid collection or reuse a collection created for another sparse
strategy identity only because the base collection name is similar.

### 5.3 Point Upsert Shape Overrides Dense Ingest

This section overrides dense-ingest point-upsert shape.

Each successfully prepared point must include:

- `id`
- dense vector under `CONFIG_PATH.qdrant.collection.dense_vector_name`
- sparse vector under `CONFIG_PATH.qdrant.collection.sparse_vector_name`
- canonical payload

Hybrid ingest must not emulate sparse retrieval by storing sparse vectors only in payload metadata.

Qdrant point-upsert endpoint:

- `PUT /collections/{effective_collection_name}/points`

For the current design, each point body must follow the named-vector shape:

```json
{
  "id": "<point_id>",
  "vector": {
    "<dense_vector_name>": [0.1, 0.2],
    "<sparse_vector_name>": {
      "indices": [1, 4, 8],
      "values": [2.0, 1.0, 3.0]
    }
  },
  "payload": {}
}
```

Qdrant point retrieve-by-id endpoint for compatibility checks:

- `POST /collections/{effective_collection_name}/points`

with body shape:

```json
{
  "ids": ["<point_id>"],
  "with_payload": true,
  "with_vector": true
}
```

Local verification note:

- on 2026-04-02 this retrieve-by-id shape returned both named vectors and
  payload for the temporary hybrid probe collection

### 5.4 Fingerprint Change Invalidates Both Representations

This section extends dense-ingest fingerprint semantics.

Dense ingest already uses fingerprint comparison to decide whether a point's
representation changed.

In hybrid ingest:

- if fingerprint changes, the existing dense vector must be treated as stale
- if fingerprint changes, the existing sparse vector must be treated as stale
- partial reuse of either representation on fingerprint change is forbidden

The inherited `log_and_skip` policy still applies, but now it prevents reuse of
both dense and sparse representations.

### 5.5 Metadata-Only Update Path Keeps Both Vectors Stable

This section extends dense-ingest metadata-only update semantics.

If fingerprint is unchanged and only allowed metadata changed:

- dense vector must remain unchanged
- sparse vector must remain unchanged
- only payload metadata may be updated

Difference only in `ingest.ingested_at` must still lead to `skip`, not `update`.

## 6) Failure-Domain Additions

The following are additional whole-run failures beyond dense ingest:

- vocabulary artifact cannot be created before processing begins
- existing vocabulary is unreadable or invalid
- existing vocabulary identity is incompatible with the current vocabulary
  contract inputs
- existing BM25-like term-stats artifact is unreadable, invalid, or
  incompatible with the current run
- existing collection is missing hybrid-required vector slots

The following are additional chunk-level failures beyond dense ingest:

- sparse vector generation failure
- point cannot be assembled with valid dense and sparse representations

## 7) Implementation Notes

`hybrid_ingest.py` is still one Python file, like dense ingest.

Recommended internal decomposition:

- config/env loading
- vocabulary loading/creation
- sparse preprocessing and sparse vector building
- dense embedding I/O
- collection compatibility checks
- point assembly
- Qdrant I/O
- artifact writing
- summary reporting

The implementation should feel like dense ingest with one added sparse branch,
not like a separate subsystem with unrelated conventions.

## 8) Non-Goals

This delta-spec does not add:

- query-time sparse retrieval implementation
- reranking
- generation
- mutable vocabulary growth during normal ingest
- automatic vocabulary rebuild on the fly
- a second external sparse model service

# Hybrid Ingest End-to-End Tests

This document reuses the runner structure and general conventions from:

- `Specification/testgen/ingest/dense/e2e.md`

Treat the dense document above as the baseline template for:

- CLI shape
- output formatting
- verbose behavior
- real-service rules
- black-box subprocess execution
- case structure
- fixture lifecycle

This hybrid document defines only the test subjects and hybrid-specific
assertions that differ from dense ingest.

## Hybrid E2E Delta

Relative to dense ingest, E2E tests for `hybrid_ingest.py` must additionally
account for:

- derived effective collection name:
  - `<base_collection_name>_bow`
  - `<base_collection_name>_bm25`
- hybrid collection create shape:
  - named dense vector slot
  - named sparse vector slot
  - hybrid metadata
- singleton vocabulary artifact behavior
- `bm25_like` term-stats artifact behavior when strategy requires it

## Test Set

Generate the following standalone Python runners:

- `qdrant_collection_metadata_roundtrip.py`
- `qdrant_collection_compatibility_e2e.py`
- `full_ingest_e2e.py`
- `ingest_status.py`
- `failed_chunk_log_e2e.py`
- `vocabulary_reuse_e2e.py`
- `bm25_term_stats_roundtrip.py`

## `qdrant_collection_metadata_roundtrip.py`

Use the dense test of the same name as the baseline runner shape, but change
the assertions.

The test must verify that `GET /collections/{effective_name}` returns:

- `result.config.params.vectors`
- `result.config.params.sparse_vectors`
- `result.config.metadata.embedding_model_name`
- `result.config.metadata.sparse_strategy_kind`
- `result.config.metadata.sparse_strategy_version`
- `result.config.metadata.corpus_version`
- `result.config.metadata.vocabulary_identity`

Checks:

- subprocess completes successfully
- collection exists under derived effective collection name, not base name
- dense vector slot name matches config
- sparse vector slot name matches config
- hybrid metadata fields match config and vocabulary artifact

## `qdrant_collection_compatibility_e2e.py`

Use the dense test of the same name as the baseline runner shape, but replace
the case matrix with hybrid compatibility cases.

Required cases:

- `collection_sparse_vectors_missing`
- `dense_vector_name_mismatch`
- `sparse_vector_name_mismatch`
- `embedding_model_name_mismatch`
- `sparse_strategy_kind_mismatch`
- `vocabulary_identity_mismatch`

Checks:

- subprocess exits with `1`
- no points are written
- collection remains readable after failure

## `full_ingest_e2e.py`

Use the dense `full_ingest_e2e.py` runner shape as the baseline.

The happy-path assertions must be extended to verify:

- collection exists under derived effective name
- point is stored with named dense vector and named sparse vector
- payload still matches inherited dense payload contract
- hybrid metadata matches config
- vocabulary artifact exists and is valid

For the current version this runner should target:

- `bag_of_words`

## `ingest_status.py`

Use the dense test runner shape as the baseline, but keep status assertions
hybrid-aware.

The cases should still cover:

- `insert`
- `update`
- `skip`
- `skip_and_log`

Additional hybrid requirement:

- when vectors are expected to remain stable, both dense and sparse
  representations must remain stable

## `failed_chunk_log_e2e.py`

Use the dense runner shape as the baseline.

Hybrid-specific failure triggers may include:

- incompatible existing hybrid collection metadata
- unreadable or incompatible vocabulary artifact
- empty sparse vector after normalization and vocabulary lookup

## `vocabulary_reuse_e2e.py`

This is a new hybrid-specific E2E test.

Goal:

- verify that second run reuses existing singleton vocabulary
- verify that vocabulary artifact is not mutated in place

Checks:

- first run creates vocabulary
- second run succeeds with the same vocabulary
- vocabulary file contents remain byte-for-byte unchanged between runs

## `bm25_term_stats_roundtrip.py`

This is a new hybrid-specific E2E test for:

- `sparse.strategy.kind = "bm25_like"`

Goal:

- verify term-stats artifact lifecycle against real services

Checks:

- first run creates valid `term_stats_path`
- second run loads and reuses the same artifact
- artifact naming follows `<effective_collection_name>__term_stats.json`

# Hybrid Ingest Integration Tests

This document reuses the runner structure and general conventions from:

- `Specification/testgen/ingest/dense/integration.md`

Treat the dense document above as the baseline template for:

- CLI shape
- output formatting
- verbose behavior
- stub-service rules
- subprocess execution

This hybrid document defines only the integration-test subjects and the
hybrid-specific request/response expectations that differ from dense ingest.

## Hybrid Integration Delta

Compared with dense ingest, integration tests for `hybrid_ingest.py` must
account for:

- hybrid collection create shape:
  - `vectors`
  - `sparse_vectors`
  - `metadata`
- hybrid point upsert shape:
  - named dense vector
  - named sparse vector
  - payload
- derived effective collection name
- vocabulary and `bm25_like` term-stats lifecycle

## Test Set

Generate the following standalone Python runners:

- `embedding_retry.py`
- `qdrant_retry.py`
- `embedding_batch_fallback.py`
- `upsert_batch_fallback.py`
- `hybrid_collection_create_shape.py`
- `vocabulary_bootstrap_and_reuse.py`
- `bm25_term_stats_lifecycle.py`

## Stub Qdrant Delta

Use the dense stub-Qdrant rules as the baseline, but update the expected
shapes.

For hybrid collection `PUT /collections/{name}` success cases, the stub must
understand:

- `vectors` as named-vector object
- `sparse_vectors`
- `metadata`

For hybrid point upsert `PUT /collections/{name}/points`, the stub must expect:

- `points`
- for each point:
  - `id`
  - `vector.<dense_vector_name>`
  - `vector.<sparse_vector_name>.indices`
  - `vector.<sparse_vector_name>.values`
  - `payload`

## `embedding_retry.py`

Clone dense runner structure with hybrid config and hybrid create-collection
shape, but keep the same subject:

- retry on embedding failures

## `qdrant_retry.py`

Clone dense runner structure with hybrid request shapes.

The retry subject remains the same:

- retry on Qdrant failures during collection read/create/upsert

## `embedding_batch_fallback.py`

Clone dense runner structure.

Assertions remain the same for embedding transport behavior, but the hybrid
runner must still be able to continue into sparse-vector and hybrid-point
assembly after successful per-chunk embedding fallback.

## `upsert_batch_fallback.py`

Clone dense runner structure, but update Qdrant request-body assertions to the
hybrid point shape.

Goal:

- batch hybrid upsert fails
- fallback to per-point hybrid upsert succeeds or fails per case

## `hybrid_collection_create_shape.py`

New hybrid-specific integration test.

Goal:

- verify that collection-create request sent by ingest script has the exact
  hybrid shape

Checks:

- derived effective collection name is used
- request body contains named `vectors`
- request body contains `sparse_vectors`
- request body contains hybrid `metadata`

## `vocabulary_bootstrap_and_reuse.py`

New hybrid-specific integration test.

Goal:

- verify create-if-missing and reuse-if-exists behavior for singleton vocabulary

Cases:

- vocabulary missing -> bootstrap + persist
- vocabulary exists and compatible -> load + reuse
- vocabulary exists and incompatible -> fail whole-run before point processing

## `bm25_term_stats_lifecycle.py`

New hybrid-specific integration test.

Goal:

- verify `bm25_like` term-stats lifecycle without real containers

Cases:

- `term_stats_path` missing -> build then continue
- `term_stats_path` valid existing -> reuse
- `term_stats_path` invalid existing -> fail before point processing

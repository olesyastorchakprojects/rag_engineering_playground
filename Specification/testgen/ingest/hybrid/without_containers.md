# Hybrid Ingest Tests Without Containers

This document reuses the runner structure and general conventions from:

- `Specification/testgen/ingest/dense/without_containers.md`

Treat the dense document above as the baseline template for:

- CLI shape
- output formatting
- verbose behavior
- case structure

This hybrid document defines only the test subjects that differ from dense
ingest.

## Test Set

Generate the following standalone Python runners:

- `config_validation.py`
- `chunks_input_validation.py`
- `point_id_determinism.py`
- `effective_collection_name_derivation.py`
- `vocabulary_contract.py`
- `bm25_term_stats_contract.py`

## `config_validation.py`

Use the dense config-validation runner as the baseline, but target:

- `Execution/ingest/schemas/hybrid_ingest_config.schema.json`
- canonical hybrid config template

In addition to dense-like negative cases, cover:

- missing `[sparse.strategy]`
- unsupported `sparse.strategy.kind`
- both `[sparse.bag_of_words]` and `[sparse.bm25_like]` present at once
- `bag_of_words` selected but `[sparse.bag_of_words]` missing
- `bm25_like` selected but `[sparse.bm25_like]` missing
- `qdrant.collection.name` ending with `_bow`
- `qdrant.collection.name` ending with `_bm25`
- `qdrant.collection.name` ending with `_`

Note:

- `dense_vector_name != sparse_vector_name` is a runtime validation rule, not a
  pure schema rule, so this case should be covered as contract-level negative
  validation inside the runner even if schema alone cannot express it.

## `chunks_input_validation.py`

Clone the dense runner shape.

The subject remains the same:

- invalid JSONL
- schema mismatch
- `page_end >= page_start`

Hybrid-specific addition:

- if a non-empty chunk would inevitably produce empty sparse vector after
  normalization and vocabulary lookup, the runner should treat that as expected
  chunk-level invalidity for hybrid ingest

## `point_id_determinism.py`

Clone dense runner shape without hybrid-specific changes.

The point-id contract is inherited unchanged.

## `effective_collection_name_derivation.py`

New hybrid-specific non-container test.

Goal:

- verify deterministic mapping from strategy kind to effective collection name

Cases:

- `bag_of_words` -> `<base>_bow`
- `bm25_like` -> `<base>_bm25`
- invalid base name ending with `_bow`
- invalid base name ending with `_bm25`
- invalid base name ending with `_`

## `vocabulary_contract.py`

New hybrid-specific non-container test.

Goal:

- verify singleton vocabulary contract and bootstrap order

Checks:

- first-seen token assignment order
- contiguous `token_id` values from `0`
- immutable reuse semantics
- OOV tokens are ignored on later runs

## `bm25_term_stats_contract.py`

New hybrid-specific non-container test.

Goal:

- verify semantic and naming contract for `bm25_like` term-stats artifact

Checks:

- required fields exist
- `collection_name` is derived effective collection name
- `vocabulary_name` matches the shared vocabulary artifact
- basename follows `<effective_collection_name>__term_stats.json`

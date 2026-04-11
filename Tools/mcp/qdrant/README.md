# Qdrant MCP

This MCP server exposes live retrieval truth in Qdrant.

It covers two main scenarios:

- live inspection of collections, points, and payloads
- compatibility/debugging against the ingest-owned source of truth

It does not replace:

- `Project Context MCP` for the broader operational picture
- `Spec MCP` for formal contracts and schemas
- `Observability MCP` for traces, dashboards, and collector wiring
- `Postgres MCP` for eval truth

The current repository config surface defines six collection names across dense and hybrid ingest variants:

- `chunks_dense_qwen3`
- `chunks_dense_qwen3_fixed`
- `chunks_hybrid_qwen3`
- `chunks_hybrid_qwen3_fixed`
- `chunks_hybrid_fixed_qwen3`
- `chunks_hybrid_structural_qwen3`

## Tool Surface

- `check_connection()`
- `get_connection_defaults()`
- `list_collections()`
- `get_collection_info(collection_name="", config_path="")`
- `get_collection_compatibility(collection_name="", config_path="")`
- `get_sample_points(collection_name="", limit=10, config_path="")`
- `get_point_by_id(point_id, collection_name="", config_path="")`
- `find_points_by_chunk_id(chunk_id, collection_name="", limit=20, config_path="")`
- `get_point_by_chunk_id(chunk_id, collection_name="", config_path="")`
- `find_points_by_content_hash(content_hash, collection_name="", limit=20, config_path="")`
- `find_points_by_document_id(document_id, collection_name="", limit=20, config_path="")`
- `get_retrieval_payload_health(collection_name="", sample_limit=25, config_path="")`

## When To Use It

Use this server when you want to inspect what is actually in retrieval storage right now.

Good examples:

- "is the local Qdrant instance up?"
- "what collections exist?"
- "does this live collection still match the ingest config?"
- "what point corresponds to this `chunk_id`?"
- "do these payloads look healthy enough for retrieval debugging?"

## Semantics

- if `collection_name` is omitted, the server tries to infer it from the ingest config
- the default ingest config is `Execution/ingest/dense/ingest.toml`
- for hybrid ingest, the effective collection name is derived from `qdrant.collection.name` and `sparse.strategy.kind`
- the default Qdrant URL is `QDRANT_URL` from the environment, otherwise `http://localhost:6333`
- responses are intentionally lightweight:
  - vectors are not fetched by default
  - the server focuses on payloads, counts, and compatibility signals
- `list_collections()` reports the live collection set, which may be smaller or larger than the six config-driven names depending on what has actually been ingested into Qdrant

## Compatibility Truth

For dense ingest, the important fields include:

- `qdrant.collection.name`
- `qdrant.collection.distance`
- `embedding.model.dimension`
- `embedding.model.name`

A live collection is considered compatible when:

- the collection exists
- vector size matches the ingest config
- distance matches the ingest config
- `config.metadata.embedding_model_name` matches the ingest config

For hybrid ingest, the additional fields are:

- effective collection name derived from strategy kind
- `qdrant.collection.dense_vector_name`
- `qdrant.collection.sparse_vector_name`
- `sparse.strategy.kind`
- `sparse.strategy.version`

The server supports both dense single-vector layouts and hybrid named-vector plus sparse-vector layouts.
If a collection becomes more complex than the curated checks, the server returns the raw vector config and marks the layout as non-simple.

## Limits

- the server is designed for the local stack and config-driven defaults
- payload search is best-effort through Qdrant scroll/filter
- duplicate checks by `chunk_id` use a bounded scan and flag truncation explicitly
- empty sample payload checks are reported as `insufficient_sample`
- the server does not do live vector search from raw user text
- the server is not a bulk dump tool for the entire collection

## Local Run

```bash
./.venv/bin/python Tools/mcp/qdrant/server.py
```

## Expected MCP Registration

This server is intended to be registered as a local stdio MCP server in the local Codex configuration.

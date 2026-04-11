# Hybrid Ingest Tests Matrix

Below is the initial test matrix for `hybrid_ingest`, split by layer and marked to show where containers are required.

## Without Containers

| Test Name | What It Tests | Briefly | Containers Required |
| --- | --- | --- | --- |
| `config_validation.py` | Validation of `CONFIG_PATH` | TOML parse, schema validation, strategy blocks, derived collection-name guards, `term_stats_path` for `bm25_like` | No |
| `chunks_input_validation.py` | Validation of `CHUNKS_PATH` | empty input, invalid JSONL, schema mismatch, `page_end >= page_start` | No |
| `point_id_determinism.py` | Determinism of `point_id` | same `chunk_id` -> same UUID, different `chunk_id` -> different UUID | No |
| `effective_collection_name_derivation.py` | Deterministic mapping from strategy to suffix | `bag_of_words -> bow`, `bm25_like -> bm25`, invalid base-name cases | No |
| `vocabulary_contract.py` | Singleton vocabulary contract | bootstrap order, immutable reuse, OOV handling, path/name contract | No |
| `bm25_term_stats_contract.py` | `term_stats_path` contract | required fields, naming, collection/strategy/vocabulary linkage | No |

## Integration Tests Without Containers

| Test Name | What It Tests | Briefly | Containers Required |
| --- | --- | --- | --- |
| `embedding_retry.py` | Retry for embedding requests | transient failure -> retry -> success, retry exhaustion | No |
| `qdrant_retry.py` | Retry for Qdrant requests | transient Qdrant error -> retry -> success, retry exhaustion | No |
| `embedding_batch_fallback.py` | Fallback `embedding batch -> per-chunk` | batch request failed, then per-chunk success/fail split | No |
| `upsert_batch_fallback.py` | Fallback `upsert batch -> per-point` | batch upsert failed, then per-point success/fail split for the hybrid point shape | No |
| `hybrid_collection_create_shape.py` | Create-collection request shape | `vectors`, `sparse_vectors`, `metadata`, derived effective collection name | No |
| `vocabulary_bootstrap_and_reuse.py` | Vocabulary lifecycle | create-if-missing, reuse-if-exists, fail on incompatible existing vocabulary | No |
| `bm25_term_stats_lifecycle.py` | `bm25_like` term-stats lifecycle | load existing stats, build missing stats, fail on incompatible existing stats | No |

## End-to-End with Containers

| Test Name | What It Tests | Briefly | Containers Required |
| --- | --- | --- | --- |
| `qdrant_collection_metadata_roundtrip.py` | Real Qdrant collection API for hybrid | create collection, `GET /collections/{name}` returns dense + sparse config and hybrid metadata | Yes, Qdrant |
| `qdrant_collection_compatibility_e2e.py` | Real fail-fast on an incompatible hybrid collection | missing `sparse_vectors`, metadata mismatch, vector-slot mismatch, vocabulary mismatch | Yes, Qdrant |
| `full_ingest_e2e.py` | Full happy-path hybrid ingest | chunks -> embeddings + sparse vectors -> hybrid upsert into Qdrant -> summary | Yes, Qdrant + embedding service |
| `ingest_status.py` | `insert`, `update`, `skip`, `skip_and_log` through the real hybrid ingest flow | controlled collection state and controlled chunk inputs, validation of final ingest outcomes through side effects | Yes, Qdrant |
| `failed_chunk_log_e2e.py` | Real failed chunk log | broken existing point payload or incompatible sparse prerequisites -> failed log entry | Yes, Qdrant |
| `vocabulary_reuse_e2e.py` | Reuse of an existing vocabulary | second run reuses the singleton vocabulary and does not mutate it | Yes, Qdrant + embedding service |
| `bm25_term_stats_roundtrip.py` | `bm25_like` corpus-stats artifact | first run builds `term_stats`, second run validates and reuses it | Yes, Qdrant + embedding service |

## Where Containers Are Actually Required

- Only where the real Qdrant API shape, collection metadata, named dense+sparse vectors, and real side effects in the collection must be verified.
- For retry, fallback, naming/contract validation, vocabulary lifecycle, and `bm25_like` term-stats lifecycle, containers are not needed; fake HTTP services and local temporary artifacts are preferable there.

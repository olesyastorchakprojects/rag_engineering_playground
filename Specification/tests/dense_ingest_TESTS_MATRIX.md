# Dense Ingest Tests Matrix

Below is the initial test matrix for `dense_ingest`, split by layer and marked to show where containers are required.

## Without Containers

| Test Name | What It Tests | Briefly | Containers Required |
| --- | --- | --- | --- |
| `config_validation.py` | Validation of `CONFIG_PATH` | TOML parse, schema validation, required fields, unsupported enum values, invalid scalar values | No |
| `env_validation.py` | Validation of `ENV_FILE_PATH` | env parsing, required keys, invalid lines, schema validation | No |
| `chunks_input_validation.py` | Validation of `CHUNKS_PATH` | empty input, invalid JSONL, non-object lines, schema mismatch, `page_end >= page_start` | No |
| `point_id_determinism.py` | Determinism of `point_id` | same `chunk_id` -> same UUID, different `chunk_id` -> different UUID, canonical UUID format | No |

## Integration Tests Without Containers

| Test Name | What It Tests | Briefly | Containers Required |
| --- | --- | --- | --- |
| `embedding_retry.py` | Retry for embedding requests | transient failure -> retry -> success, retry exhaustion | No |
| `qdrant_retry.py` | Retry for Qdrant requests | transient Qdrant error -> retry -> success, retry exhaustion | No |
| `embedding_batch_fallback.py` | Fallback `embedding batch -> per-chunk` | batch request failed, then per-chunk success/fail split | No |
| `upsert_batch_fallback.py` | Fallback `upsert batch -> per-point` | batch upsert failed, then per-point success/fail split | No |

## End-to-End with Containers

| Test Name | What It Tests | Briefly | Containers Required |
| --- | --- | --- | --- |
| `qdrant_collection_metadata_roundtrip.py` | Real Qdrant collection API | create collection with metadata, `GET /collections/{name}` returns metadata + `vectors.size` + distance | Yes, Qdrant |
| `qdrant_collection_compatibility_e2e.py` | Real fail-fast on an incompatible collection | metadata missing, model mismatch, dimension mismatch, distance mismatch | Yes, Qdrant |
| `full_ingest_e2e.py` | Full happy-path ingest | chunks -> embeddings -> upsert into Qdrant -> summary | Yes, Qdrant + embedding service |
| `ingest_status.py` | `insert`, `update`, `skip`, `skip_and_log` through the real ingest flow | controlled collection state and controlled chunk inputs, validation of final ingest outcomes through side effects | Yes, Qdrant |
| `failed_chunk_log_e2e.py` | Real failed chunk log on a broken existing point payload | destructive payload mutation removes `content_hash`, second run fails and writes one failed log entry | Yes, Qdrant |

## Where Containers Are Actually Required

- Only where the real Qdrant API shape and real side effects in the collection must be verified.
- For retry, fallback, error parsing, and logging, containers are not needed; fake HTTP services are preferable there.

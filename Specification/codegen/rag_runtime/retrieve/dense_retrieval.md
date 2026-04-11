## 1) Purpose / Scope

`dense_retrieval` performs dense retrieval for a validated user query.

This module:
- receives `ValidatedUserRequest`;
- may receive `GoldenRetrievalTargets`;
- creates a query embedding;
- sends vector search requests to Qdrant;
- maps returned points into `RetrievedChunk`;
- returns `RetrievalOutput` in dense-retrieval rank order for downstream reranking or direct generation.

This module does not:
- perform input validation;
- perform reranking;
- perform hybrid retrieval;
- assemble the final prompt for the LLM;
- call the generation module;
- read SQL or other secondary storage if the required data is already present in Qdrant payload.

## 2) Public Interface

The public retriever interface for `dense_retrieval` is defined in:

- `Specification/codegen/rag_runtime/retrieve/integration.md`

Interface rules:

- the dense retrieval implementation must conform to the `Retriever` interface defined in the retrieve integration contract;
- the interface must be async;
- the interface must receive `&ValidatedUserRequest`;
- the interface must receive `Option<&GoldenRetrievalTargets>`;
- the interface must receive `&RetrievalSettings` explicitly;
- `RetrievalSettings` must be the typed settings section taken from `Settings.retrieval`;
- the interface must return `RetrievalOutput` on success;
- the interface must return `RagRuntimeError` on failure;
- module-internal logic uses `RetrievalError` before conversion to `RagRuntimeError`.

## 3) Input And Output Types

Input types:

- `ValidatedUserRequest`
- `GoldenRetrievalTargets`
- `RetrievalSettings`

Output types:

- `RetrievedChunk`
- `RetrievalOutput`

Type rules:

- `ValidatedUserRequest` must follow the shared type contract defined in `rag_runtime.md`;
- `GoldenRetrievalTargets` must follow the interface-type contract defined in `rag_runtime.md` when present;
- `RetrievalOutput` must follow the shared type contract defined in `rag_runtime.md`;
- `RetrievedChunk` must follow the shared type contract defined in `rag_runtime.md`;
- `RetrievalSettings` must be the typed settings section from `Settings.retrieval`.
- `RetrievalOutput` is the raw retrieval-stage result and must not contain rerank-specific scores;
- `RetrievalOutput.metrics`, when present, contains dense-retrieval-stage metric values computed at `RetrievalSettings.top_k`.

## 4) Configuration Usage

`dense_retrieval` must read only its own settings section:

- `Settings.retrieval`

`RetrievalSettings` fields are defined in the crate-level `Settings` contract in `rag_runtime.md`.

The module must not:

- read raw TOML directly;
- read config maps directly;
- read settings that belong to generation;
- read ingest config directly inside the retrieval module;
- redefine ingest-owned compatibility settings locally.

## 5) External Service Usage

Embedding service usage
-----------------------

Base embedding service contract is defined in:

- `Specification/contracts/external/embedding_service.md`

Retrieval-specific embedding usage:

- Ollama base URL must be `RetrievalSettings.ollama_url`;
- retrieval must call endpoint `POST /api/embed` on that base URL;
- retrieval must send exactly one validated query string in `request.input`;
- request `model` must be `RetrievalSettings.ingest.embedding_model_name`;
- the number of returned embeddings must be exactly `1`;
- the length of the returned embedding must equal `RetrievalSettings.ingest.embedding_dimension`.

Embedding retry logic:

- embedding requests must use `RetrievalSettings.embedding_retry.max_attempts` and `RetrievalSettings.embedding_retry.backoff`;
- if an embedding request fails, retrieval must retry until `max_attempts` is exhausted;
- fail embedding request includes transport error, HTTP status not `2xx`, and invalid response;
- retrieval retry/backoff execution must use the `backon` crate;
- handwritten retry/backoff implementations are forbidden;
- retry execution must be built from a shared reusable retry helper or retry policy abstraction rather than duplicated per-callsite loops;
- retry strategy selection must be represented as a typed internal config value rather than used as an unchecked runtime string;
- `exponential` backoff means:
  - delay between retry attempts must grow exponentially;
  - implementation uses an explicit exponential formula;
  - growth must be exponential, not constant or linear;
  - bounded jitter must be applied to retry delays;
  - jitter must not remove the exponential growth property.

Qdrant search usage
-------------------

Base Qdrant HTTP contract is defined by the official Qdrant API:

- `https://api.qdrant.tech/`

Retrieval-specific Qdrant usage:

- Qdrant base URL must be `RetrievalSettings.qdrant_url`;
- retrieval must use endpoint `POST /collections/{RetrievalSettings.ingest.qdrant_collection_name}/points/query`;
- retrieval must not use deprecated endpoint `POST /collections/{RetrievalSettings.ingest.qdrant_collection_name}/points/search`;
- collection name must be `RetrievalSettings.ingest.qdrant_collection_name`;
- the search request must include the query embedding created by retrieval;
- the search request must set `query` to the dense query embedding;
- if `RetrievalSettings.ingest.qdrant_vector_name != "default"`, the search request must set `using` to `RetrievalSettings.ingest.qdrant_vector_name`;
- if `RetrievalSettings.ingest.qdrant_vector_name == "default"`, the search request must not send `using`;
- the search request must set `limit` to `RetrievalSettings.top_k`;
- the search request must set `score_threshold` to `RetrievalSettings.score_threshold`;
- the search request must set `with_payload` to `true`;
- the search request must set `with_vector` to `false`;
- the search request must request payloads for returned points;
- returned hits must include score and payload;
- payload must be sufficient to construct `RetrievedChunk`.

Qdrant retry logic:

- Qdrant requests must use `RetrievalSettings.qdrant_retry.max_attempts` and `RetrievalSettings.qdrant_retry.backoff`;
- if a Qdrant request fails, retrieval must retry until `max_attempts` is exhausted;
- fail Qdrant request includes transport error, HTTP status not `2xx`, and invalid response;
- retrieval retry/backoff execution must use the `backon` crate;
- handwritten retry/backoff implementations are forbidden;
- retry execution must be built from a shared reusable retry helper or retry policy abstraction rather than duplicated per-callsite loops;
- retry strategy selection must be represented as a typed internal config value rather than used as an unchecked runtime string;
- `exponential` backoff means:
  - delay between retry attempts must grow exponentially;
  - implementation uses an explicit exponential formula;
  - growth must be exponential, not constant or linear;
  - bounded jitter must be applied to retry delays;
  - jitter must not remove the exponential growth property.

## 6) Retrieval Algorithm

For each request:

1. Read the validated query from `ValidatedUserRequest.query`.
2. Build the embedding service request with:
   - `model = RetrievalSettings.ingest.embedding_model_name`
   - `input = [ValidatedUserRequest.query]`
3. Call the embedding service.
4. Validate the embedding response.
5. Extract the single query embedding from the response.
6. Validate that embedding length matches `RetrievalSettings.ingest.embedding_dimension`.
7. Build the Qdrant search request with:
   - endpoint `POST /collections/{RetrievalSettings.ingest.qdrant_collection_name}/points/query`
   - `query = query_embedding`
   - `using = RetrievalSettings.ingest.qdrant_vector_name` only if `RetrievalSettings.ingest.qdrant_vector_name != "default"`
   - `limit = RetrievalSettings.top_k`
   - `score_threshold = RetrievalSettings.score_threshold`
   - `with_payload = true`
   - `with_vector = false`
8. Call Qdrant search.
9. Validate the Qdrant response:
   - HTTP status must be `2xx`
   - body must parse as JSON object
   - `result.points` array must exist
   - each returned hit must contain `score`
   - each returned hit must contain `payload`
10. Read returned hits from `result.points` in response order.
11. For each returned hit, map response score and payload into `RetrievedChunk`.
12. When `GoldenRetrievalTargets` is present, compute dense-retrieval-stage metrics from:
   - the ordered retrieval output chunk ids
   - `RetrievalSettings.top_k`
   - `GoldenRetrievalTargets`
   according to:
   - `Specification/codegen/rag_runtime/retrieval_metrics.md`
13. Return `RetrievalOutput { chunks, metrics }`.

Ordering rule:

- `RetrievalOutput.chunks` preserves Qdrant response order;
- that order is the retrieval-stage candidate order, not the final generation-context order when reranking is enabled.

Empty-result rule:

- if Qdrant returns zero hits, retrieval must return `RetrievalOutput { chunks: vec![], metrics: None }`;
- zero retrieval hits is a valid successful result, not an error.

## 7) Payload / Mapping Contract

Qdrant hit mapping rules:

- each returned hit must provide a score;
- each returned hit must provide a payload object;
- payload must satisfy the chunk contract defined in `Specification/contracts/chunk/spec.md`;
- the machine-readable schema for the same payload is `Execution/schemas/chunk.schema.json`.

`RetrievedChunk` mapping rules:

- `RetrievedChunk.chunk` must be built from Qdrant payload;
- `RetrievedChunk.score` must be built from the hit score returned by Qdrant;
- `RetrievedChunk` must not contain raw Qdrant response fragments.

Payload validation rules:

- missing required chunk fields in payload is a retrieval error;
- invalid field types in payload is a retrieval error;
- payload that cannot be mapped to the chunk contract is a retrieval error.
- serde deserialization into a Rust `Chunk` struct alone is not sufficient payload validation;
- retrieval must validate mapped payloads against the canonical chunk contract defined by:
  - `Specification/contracts/chunk/spec.md`
  - `Execution/schemas/chunk.schema.json`
- retrieval must also enforce the business rule `page_end >= page_start`;
- a payload that deserializes into a Rust struct but violates the canonical chunk contract remains a retrieval error.

## 8) Error Model

The module must define:

- `RetrievalError`

`RetrievalError` must include module-specific variants for retrieval failures.

Required failure categories:

- embedding request failure;
- embedding response validation failure;
- embedding dimension mismatch;
- Qdrant request failure;
- Qdrant response validation failure;
- payload mapping failure;
- retrieval metrics helper failure;
- unexpected internal state.

Metric rules:

- `dense_retrieval` must use the retrieval metrics helper defined by:
  - `Specification/codegen/rag_runtime/retrieval_metrics.md`
- `dense_retrieval` must not duplicate retrieval-quality formulas inline across multiple call sites;
- if the retrieval metrics helper rejects invalid metric inputs, `dense_retrieval` must surface that failure as a retrieval-owned failure;
- when orchestration passes `None` for the current request, `RetrievalOutput.metrics` must be `None`;
- when orchestration passes `Some(&GoldenRetrievalTargets)` for the current request, `RetrievalOutput.metrics` must contain dense-retrieval-stage metrics computed at `RetrievalSettings.top_k`.

Failure-domain rules:

## 9) Collection Metadata And `chunking_strategy`

`DenseRetriever` must fetch and cache `chunking_strategy` from the Qdrant collection metadata.

Fetch rules:

- on first `retrieve` call, before vector search, retrieval must call `GET /collections/{RetrievalSettings.ingest.qdrant_collection_name}` on `RetrievalSettings.qdrant_url`;
- the response field path is `result.config.metadata.chunking_strategy`;
- if the field is missing or the request fails, retrieval must return a `RetrievalError`;
- the value must be cached inside the `DenseRetriever` instance after first successful fetch;
- subsequent requests must use the cached value and must not repeat the Qdrant metadata call.

Output rules:

- `RetrievalOutput` must include `chunking_strategy: String`;
- retrieval must populate `RetrievalOutput.chunking_strategy` from the cached value;
- `chunking_strategy` is metadata about the collection, not a per-request computed value.

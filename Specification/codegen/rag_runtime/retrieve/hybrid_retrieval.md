## 1) Purpose / Scope

`hybrid_retrieval` performs hybrid retrieval for a validated user query.

This module:
- receives `ValidatedUserRequest`;
- may receive `GoldenRetrievalTargets`;
- creates a dense query embedding;
- creates a sparse query vector from the same validated query;
- sends a hybrid search request to Qdrant;
- maps returned points into `RetrievedChunk`;
- returns `RetrievalOutput` in hybrid-retrieval rank order for downstream reranking or direct generation.

This module does not:
- perform input validation;
- perform reranking;
- perform dense-only retrieval;
- assemble the final prompt for the LLM;
- call the generation module;
- read SQL or other secondary storage if the required data is already present in Qdrant payload.

## 2) Public Interface

The public retriever interface for `hybrid_retrieval` is defined in:

- `Specification/codegen/rag_runtime/retrieve/integration.md`

Interface rules:

- the hybrid retrieval implementation must conform to the `Retriever` interface defined in the retrieve integration contract;
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
- `RetrievalSettings` must be the typed settings section from `Settings.retrieval`;
- `RetrievalSettings.ingest` must be `HybridRetrievalIngest`;
- `RetrievalOutput` is the raw retrieval-stage result and must not contain rerank-specific scores;
- `RetrievalOutput.metrics`, when present, contains hybrid-retrieval-stage metric values computed at `RetrievalSettings.top_k`.

## 4) Configuration Usage

`hybrid_retrieval` must read only its own settings section:

- `Settings.retrieval`

`RetrievalSettings` fields are defined in the crate-level `Settings` contract in `rag_runtime.md`.

The module must not:

- read raw TOML directly;
- read config maps directly;
- read settings that belong to generation;
- read ingest config directly inside the retrieval module;
- redefine ingest-owned compatibility settings locally.

`hybrid_retrieval` must use the following `RetrievalSettings.ingest` fields:

- `embedding_model_name`
- `embedding_dimension`
- `qdrant_collection_name`
- `dense_vector_name`
- `sparse_vector_name`
- `corpus_version`
- `tokenizer_library`
- `tokenizer_source`
- `tokenizer_revision`, when present
- `preprocessing_kind`
- `lowercase`
- `min_token_length`
- `vocabulary_path`
- `strategy`

## 5) External Service Usage

Embedding service usage
-----------------------

Base embedding service contract is defined in:

- `Specification/contracts/external/embedding_service.md`

Retrieval-specific embedding usage:

- Ollama base URL must be `RetrievalSettings.ollama_url`;
- hybrid retrieval must call endpoint `POST /api/embed` on that base URL;
- hybrid retrieval must send exactly one validated query string in `request.input`;
- request `model` must be `RetrievalSettings.ingest.embedding_model_name`;
- the number of returned embeddings must be exactly `1`;
- the length of the returned embedding must equal `RetrievalSettings.ingest.embedding_dimension`.

Embedding retry logic:

- embedding requests must use `RetrievalSettings.embedding_retry.max_attempts` and `RetrievalSettings.embedding_retry.backoff`;
- if an embedding request fails, hybrid retrieval must retry until `max_attempts` is exhausted;
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

Sparse query construction usage
-------------------------------

Sparse text-to-token rules are defined in:

- `Specification/contracts/ingest/common/sparse_text_space.md`

Sparse vocabulary contract is defined in:

- `Execution/ingest/schemas/common/sparse_vocabulary.schema.json`

Strategy-specific sparse query rules are defined in:

- `Specification/contracts/ingest/common/sparse_strategies/bag_of_words.md`
- `Specification/contracts/ingest/common/sparse_strategies/bm25_like.md`

BM25 term-stats contract is defined in:

- `Specification/contracts/ingest/common/bm25_term_stats.md`

Retrieval-specific sparse query usage:

- hybrid retrieval must tokenize and normalize query text according to the sparse text-space contract;
- `RetrievalSettings.ingest.vocabulary_path` is the repository-root-relative vocabulary directory path, not a vocabulary filename;
- hybrid retrieval must derive the vocabulary artifact filename inside `RetrievalSettings.ingest.vocabulary_path`;
- the derived vocabulary artifact loaded from `RetrievalSettings.ingest.vocabulary_path` must correspond to ingest config `qdrant.collection.name`;
- the vocabulary identity must be constructed from ingest config `qdrant.collection.name` as:
  - `vocabulary_name = <qdrant.collection.name>__sparse_vocabulary`
  - vocabulary filename = `<qdrant.collection.name>__sparse_vocabulary.json`
- the derived vocabulary artifact path must be the repository-root-relative path:
  - `<RetrievalSettings.ingest.vocabulary_path>/<qdrant.collection.name>__sparse_vocabulary.json`
- runtime must resolve `RetrievalSettings.ingest.vocabulary_path` against repository root before constructing the derived vocabulary artifact path;
- hybrid retrieval must map canonical query tokens through that vocabulary;
- hybrid retrieval must ignore out-of-vocabulary tokens in the current version;
- sparse query vector shape must contain aligned `indices` and `values`;
- `indices` must be sorted ascending;
- sparse query vector weighting must follow the concrete strategy selected in `RetrievalSettings.ingest.strategy`;
- if sparse query vector construction produces zero sparse terms after normalization and vocabulary lookup, hybrid retrieval must fail with a retrieval error in the current version;
- when `RetrievalSettings.ingest.strategy = RetrievalStrategy::Bm25Like(Bm25LikeRetrievalStrategy)`, hybrid retrieval must derive the BM25 term-stats artifact filename inside `Bm25LikeRetrievalStrategy.term_stats_path`;
- `Bm25LikeRetrievalStrategy.term_stats_path` is the repository-root-relative term-stats directory path, not a term-stats filename;
- the derived BM25 term-stats artifact path must be the repository-root-relative path:
  - `<Bm25LikeRetrievalStrategy.term_stats_path>/<effective_qdrant_collection_name>__term_stats.json`
- runtime must resolve `Bm25LikeRetrievalStrategy.term_stats_path` against repository root before constructing the derived BM25 term-stats artifact path.

Qdrant search usage
-------------------

Base Qdrant HTTP contract is defined by the official Qdrant API:

- `https://api.qdrant.tech/`

Retrieval-specific Qdrant usage:

- Qdrant base URL must be `RetrievalSettings.qdrant_url`;
- hybrid retrieval must derive the effective Qdrant collection name from `RetrievalSettings.ingest.qdrant_collection_name` and the selected sparse strategy;
- the effective Qdrant collection name must be:
  - `<RetrievalSettings.ingest.qdrant_collection_name>_bow` when `RetrievalStrategy::BagOfWords(BagOfWordsRetrievalStrategy)` is selected
  - `<RetrievalSettings.ingest.qdrant_collection_name>_bm25` when `RetrievalStrategy::Bm25Like(Bm25LikeRetrievalStrategy)` is selected
- hybrid retrieval must use endpoint `POST /collections/{<effective_qdrant_collection_name>}/points/query`;
- hybrid retrieval must not use deprecated endpoint `POST /collections/{<effective_qdrant_collection_name>}/points/search`;
- collection name used in Qdrant requests must be the effective Qdrant collection name derived by the retriever, not the unsuffixed `RetrievalSettings.ingest.qdrant_collection_name`;
- the search request must use Qdrant hybrid fusion with `prefetch` and `query.fusion`;
- the dense query embedding created by hybrid retrieval must be sent as one prefetch branch;
- the sparse query vector created by hybrid retrieval must be sent as one prefetch branch;
- `prefetch[0]` must be the dense branch;
- `prefetch[1]` must be the sparse branch;
- the dense prefetch branch must target `RetrievalSettings.ingest.dense_vector_name`;
- the sparse prefetch branch must target `RetrievalSettings.ingest.sparse_vector_name`;
- the current fusion method must be reciprocal-rank fusion:
  - `query = { "fusion": "rrf" }`
- the request shape for the current version must be:

```json
{
  "prefetch": [
    {
      "query": [0.1, 0.2, 0.3],
      "using": "<dense_vector_name>",
      "limit": 50
    },
    {
      "query": {
        "indices": [1, 7, 42],
        "values": [1.0, 1.0, 1.0]
      },
      "using": "<sparse_vector_name>",
      "limit": 50
    }
  ],
  "query": {
    "fusion": "rrf"
  },
  "limit": 10,
  "score_threshold": 0.2,
  "with_payload": true,
  "with_vector": false
}
```

- where:
  - dense `prefetch[0].query` must be the full dense embedding vector of length `RetrievalSettings.ingest.embedding_dimension`
  - sparse `prefetch[1].query.indices` and `prefetch[1].query.values` must be aligned arrays
  - both prefetch branches must use branch `limit = RetrievalSettings.top_k` in the current version
- the search request must set `limit` to `RetrievalSettings.top_k`;
- the search request must set `score_threshold` to `RetrievalSettings.score_threshold`;
- `score_threshold` applies to the fused top-level `result.points` returned by Qdrant, not to branch-local dense or sparse prefetch candidate generation;
- the search request must set `with_payload` to `true`;
- the search request must set `with_vector` to `false`;
- the search request must request payloads for returned points;
- the successful response shape for the current version must be:

```json
{
  "result": {
    "points": [
      {
        "id": "point-id",
        "score": 0.5,
        "payload": {
          "chunk_id": "..."
        }
      }
    ]
  },
  "status": "ok",
  "time": 0.01
}
```

- returned hits must be read from `result.points`;
- each returned hit must include score and payload;
- payload must be sufficient to construct `RetrievedChunk`.

Qdrant retry logic:

- Qdrant requests must use `RetrievalSettings.qdrant_retry.max_attempts` and `RetrievalSettings.qdrant_retry.backoff`;
- if a Qdrant request fails, hybrid retrieval must retry until `max_attempts` is exhausted;
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
7. Tokenize and normalize `ValidatedUserRequest.query` according to the sparse text-space contract.
8. Load the derived sparse vocabulary artifact from `RetrievalSettings.ingest.vocabulary_path`.
9. Map canonical query tokens through the vocabulary and ignore out-of-vocabulary tokens.
10. Build the sparse query vector according to `RetrievalSettings.ingest.strategy`.
11. If sparse query vector construction yields zero sparse terms, fail with a retrieval error.
12. Build the Qdrant search request with:
   - endpoint `POST /collections/{<effective_qdrant_collection_name>}/points/query`
   - `prefetch[0]` dense branch built from the dense query embedding and `RetrievalSettings.ingest.dense_vector_name`
   - `prefetch[1]` sparse branch built from the sparse query vector and `RetrievalSettings.ingest.sparse_vector_name`
   - fusion query `{ "fusion": "rrf" }`
   - `prefetch[0].limit = RetrievalSettings.top_k`
   - `prefetch[1].limit = RetrievalSettings.top_k`
   - `limit = RetrievalSettings.top_k`
   - `score_threshold = RetrievalSettings.score_threshold`
   - `with_payload = true`
   - `with_vector = false`
13. Call Qdrant search.
14. Validate the Qdrant response:
   - HTTP status must be `2xx`
   - body must parse as JSON object
   - `result.points` array must exist
   - each returned hit must contain `score`
   - each returned hit must contain `payload`
15. Read returned hits from `result.points` in response order.
16. For each returned hit, map response score and payload into `RetrievedChunk`.
17. When `GoldenRetrievalTargets` is present, compute hybrid-retrieval-stage metrics from:
   - the ordered retrieval output chunk ids
   - `RetrievalSettings.top_k`
   - `GoldenRetrievalTargets`
   according to:
   - `Specification/codegen/rag_runtime/retrieval_metrics.md`
18. Return `RetrievalOutput { chunks, metrics }`.

Ordering rule:

- `RetrievalOutput.chunks` preserves Qdrant response order;
- that order is the retrieval-stage candidate order, not the final generation-context order when reranking is enabled.

Empty-result rule:

- if Qdrant returns zero hits, hybrid retrieval must return `RetrievalOutput { chunks: vec![], metrics: None }`;
- zero retrieval hits is a valid successful result, not an error.

## 7) Strategy-Specific Sparse Query Rules

`RetrievalStrategy::BagOfWords(BagOfWordsRetrievalStrategy)`
------------------------------------------------------------

For the current version:

- query weighting must follow the `bag_of_words` strategy contract;
- `query_weighting` comes from the `BagOfWordsRetrievalStrategy` value contained in `RetrievalSettings.ingest.strategy`;
- current supported strategy version must be `v1`;
- unsupported `bag_of_words` strategy versions are a retrieval error;
- current supported query-side weighting is `binary_presence`;
- sparse value must equal `1.0` when a token appears at least once in the validated query.

`RetrievalStrategy::Bm25Like(Bm25LikeRetrievalStrategy)`
--------------------------------------------------------

For the current version:

- query weighting must follow the `bm25_like` strategy contract;
- `query_weighting` comes from the `Bm25LikeRetrievalStrategy` value contained in `RetrievalSettings.ingest.strategy`;
- current supported strategy version must be `v1`;
- unsupported `bm25_like` strategy versions are a retrieval error;
- current supported `idf_smoothing` value is `standard`;
- unsupported `bm25_like.idf_smoothing` values are a retrieval error;
- BM25-like query weighting must use:
  - `k1`
  - `b`
  - `idf_smoothing`
  - `term_stats_path`
- BM25 term-stats loading must validate at minimum:
  - the artifact parses successfully;
  - the stored strategy identity matches the selected `bm25_like` strategy;
  - the stored collection identity matches the target hybrid collection family;
- query-side weighting must reuse the same vocabulary and corpus statistics identity as the target hybrid collection.

## 8) Payload / Mapping Contract

Qdrant hit mapping rules:

- each returned hit must provide a score;
- each returned hit must provide a payload object;
- payload must satisfy the chunk contract defined in `Specification/contracts/chunk/spec.md`;
- the machine-readable schema for the same payload is `Execution/schemas/chunk.schema.json`.

`RetrievedChunk` mapping rules:

- `RetrievedChunk.chunk` must be built from Qdrant payload;
- `RetrievedChunk.score` must be built from the fused hit score returned by Qdrant `result.points[*].score`;
- `RetrievedChunk.score` must not be interpreted as branch-local dense similarity or branch-local sparse relevance;
- fused hybrid retrieval scores must not be treated as the same semantic score scale as dense-only retrieval scores;
- `RetrievedChunk` must not contain raw Qdrant response fragments.

Payload validation rules:

- missing required chunk fields in payload is a retrieval error;
- invalid field types in payload is a retrieval error;
- payload that cannot be mapped to the chunk contract is a retrieval error;
- serde deserialization into a Rust `Chunk` struct alone is not sufficient payload validation;
- hybrid retrieval must validate mapped payloads against the canonical chunk contract defined by:
  - `Specification/contracts/chunk/spec.md`
  - `Execution/schemas/chunk.schema.json`
- hybrid retrieval must also enforce the business rule `page_end >= page_start`;
- a payload that deserializes into a Rust struct but violates the canonical chunk contract remains a retrieval error.

## 9) Error Model

The module must define:

- `RetrievalError`

`RetrievalError` must include module-specific variants for retrieval failures.

Required failure categories:

- embedding request failure;
- embedding response validation failure;
- embedding dimension mismatch;
- sparse vocabulary read failure;
- sparse vocabulary validation failure;
- empty sparse query vector;
- sparse query construction failure;
- unsupported retrieval strategy version;
- hybrid query request construction failure;
- BM25 term-stats read failure;
- BM25 term-stats validation failure;
- Qdrant request failure;
- Qdrant response validation failure;
- payload mapping failure;
- retrieval metrics helper failure;
- unexpected internal state.

Failure-domain rules:

- sparse strategy mismatch or unsupported hybrid strategy is a retrieval failure;
- raw third-party errors must not leak through the public interface;
- hybrid retrieval failures must surface as `RagRuntimeError::Retrieval(...)`;
- module-level errors must be converted to `RagRuntimeError` at the module boundary.

Metric rules:

- `hybrid_retrieval` must use the retrieval metrics helper defined by:
  - `Specification/codegen/rag_runtime/retrieval_metrics.md`
- `hybrid_retrieval` must not duplicate retrieval-quality formulas inline across multiple call sites;
- if the retrieval metrics helper rejects invalid metric inputs, `hybrid_retrieval` must surface that failure as a retrieval-owned failure;
- when orchestration passes `None` for the current request, `RetrievalOutput.metrics` must be `None`;
- when orchestration passes `Some(&GoldenRetrievalTargets)` for the current request, `RetrievalOutput.metrics` must contain hybrid-retrieval-stage metrics computed at `RetrievalSettings.top_k`.

## Collection Metadata And `chunking_strategy`

`HybridRetriever` must fetch and cache `chunking_strategy` from the Qdrant collection metadata.

Fetch rules:

- on first `retrieve` call, before vector search, retrieval must call `GET /collections/{effective_collection_name}` on `RetrievalSettings.qdrant_url`;
- `effective_collection_name` is the strategy-derived collection name, same as used for vector search;
- the response field path is `result.config.metadata.chunking_strategy`;
- if the field is missing or the request fails, retrieval must return a `RetrievalError`;
- the value must be cached inside the `HybridRetriever` instance after first successful fetch;
- subsequent requests must use the cached value and must not repeat the Qdrant metadata call.

Output rules:

- `RetrievalOutput` must include `chunking_strategy: String`;
- retrieval must populate `RetrievalOutput.chunking_strategy` from the cached value;
- `chunking_strategy` is metadata about the collection, not a per-request computed value.


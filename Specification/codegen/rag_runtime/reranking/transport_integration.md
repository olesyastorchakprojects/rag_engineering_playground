## 1) Purpose / Scope

This document defines the transport-integration contract for transport-backed cross-encoder reranking in `rag_runtime`.

It defines:
- the normalized reranking transport interface;
- transport request and response types;
- transport-owned batching behavior;
- transport-owned token counting behavior;
- tokenizer usage rules;
- response normalization rules;
- transport-owned retry and failure behavior.

This document does not define:
- crate-level pipeline sequencing;
- crate-level shared types;
- request-capture assembly;
- provider wire contracts.

Those concerns are defined in:
- `Specification/codegen/rag_runtime/rag_runtime.md`
- `Specification/codegen/rag_runtime/orchestration.md`
- `Specification/codegen/rag_runtime/reranking/cross_encoder.md`
- `Specification/codegen/rag_runtime/reranking/mixedbread_ai_api.md`
- `Specification/codegen/rag_runtime/reranking/voyageai_api.md`

## 2) Transport Responsibility

Transport-backed cross-encoder reranking uses a dedicated transport abstraction.

The transport owns:
- provider request construction;
- batching;
- provider call execution;
- retry loop execution;
- provider response validation;
- provider response normalization;
- reranking token counting.

The transport does not own:
- reranker selection;
- retrieval-quality metric computation;
- final `RerankedRetrievalOutput` construction;
- request-capture assembly.

For the current version, the transport abstraction must have exactly two concrete implementations:
- `MixedbreadAiRerankingTransport`
- `VoyageAiRerankingTransport`

Required settings-to-implementation mapping:
- `CrossEncoderTransportSettings::MixedbreadAi(...)` must be executed by `MixedbreadAiRerankingTransport`
- `CrossEncoderTransportSettings::VoyageAi(...)` must be executed by `VoyageAiRerankingTransport`

## 3) Normalized Transport Interface

Required transport interface:

```rust
#[async_trait::async_trait]
pub trait RerankingTransport: Send + Sync {
    async fn rerank(
        &self,
        request: RerankingTransportRequest,
        settings: &CrossEncoderTransportSettings,
    ) -> Result<RerankingTransportResponse, RerankingError>;
}
```

Required normalized request type:

```rust
pub struct RerankingTransportRequest {
    pub query: String,
    pub documents: Vec<String>,
    pub top_k: Option<usize>,
}
```

Required normalized response type:

```rust
pub struct RerankingTransportResponse {
    pub results: Vec<RerankingTransportResult>,
    pub total_tokens: Option<usize>,
}
```

```rust
pub struct RerankingTransportResult {
    pub index: usize,
    pub score: f32,
}
```

Interface rules:
- `query` is the validated user query for the current request;
- `documents` contains one batch of candidate texts in batch order;
- `top_k` is transport-visible because some providers require an explicit reranked result count;
- `settings` is the active typed cross-encoder transport settings enum;
- `results` must be normalized into transport-agnostic `{ index, score }` items;
- `RerankingTransportResult.index` must be a zero-based index into `RerankingTransportRequest.documents`;
- `total_tokens` is the reranking-stage total token count for the current rerank request after aggregation across all transport-owned batch calls.

## 4) Batching Rules

The transport owns batching.

Rules:
- batching must use the active transport settings `batch_size`;
- if the candidate count is less than or equal to `batch_size`, transport must execute one batch;
- if the candidate count is greater than `batch_size`, transport must split candidates into consecutive batches while preserving input order inside each batch;
- each batch must reuse the same validated query;
- each batch request must contain only the batch-local candidate texts.

Aggregation rules:
- the transport must map every batch result back to the corresponding original request-local candidate index;
- after all batches complete successfully, the transport must return one normalized score per input candidate;
- the transport must treat model scores returned across different batches as directly comparable for one rerank request;
- the final normalized result order must be produced only after batch aggregation completes.

## 5) Token Counting

The transport owns token counting.

Rules:
- `total_tokens` in `RerankingTransportResponse` is the reranking-stage total token count for the current request;
- when the provider returns token usage, the transport must use provider-reported token usage;
- when the provider does not return token usage, the transport must compute an estimated token count locally;
- transport-owned token counting must aggregate across all transport-owned batch calls for the current request.

Provider-specific rules:
- `MixedbreadAi` must compute estimated `total_tokens` locally;
- for `MixedbreadAi`, estimated `total_tokens` must count only text content used by the rerank interaction;
- for `MixedbreadAi`, estimated `total_tokens` must include query text, document text, and text-bearing response fields returned by the provider;
- for `MixedbreadAi`, estimated `total_tokens` must not include JSON field names, numeric metadata, indices, scores, or other non-text transport envelope fields;
- `VoyageAI` must use `usage.total_tokens` from the provider response.

## 6) Tokenizer Usage

Tokenizer usage for reranking is transport-owned.

Rules:
- only `MixedbreadAi` uses a local tokenizer for reranking token counting;
- `MixedbreadAi` must use `tokenizer_source` from the active transport settings;
- tokenizer usage exists only to estimate reranking `total_tokens` when the provider does not report usage;
- tokenizer resources must be initialized and reused according to the general runtime tokenizer rules defined in `Specification/codegen/rag_runtime/rag_runtime.md`;
- the token-count estimate should cover the effective query-plus-document payload semantics of the transport request as closely as practical.

## 7) Response Normalization

The transport must normalize provider-specific responses into `RerankingTransportResponse`.

Rules:
- response-to-candidate identity must be resolved by provider-reported candidate index;
- the transport must validate indices by request-local positional coverage, not by text equality;
- every returned index must be within the bounds of `RerankingTransportRequest.documents`;
- the returned index set must contain no duplicates;
- the returned index set must cover every request-local document position exactly once;
- normalized `score` must contain the provider rerank score for the candidate;
- normalized result order must follow provider response order after validation succeeds;
- every input candidate in the current rerank request must be represented exactly once in the normalized response.

## 8) Retry And Failure Rules

Retry policy is transport-owned.

Rules:
- transport retry policy comes from the active transport settings;
- transport must own retry loop execution for provider calls;
- retry must apply at the transport-call level;
- retry backoff must be exponential;
- provider-specific retryable readiness semantics, such as Mixedbread `warming`, are defined by the corresponding provider API contract and executed by the transport.

Retryable failures:
- network connection errors;
- timeout errors;
- HTTP `429`;
- HTTP `5xx`.

Provider-specific readiness handling:
- provider-specific retryable readiness semantics, such as Mixedbread `warming`, are defined by the corresponding provider API contract and executed by the transport;
- a retryable readiness signal must not be treated as a terminal failure when the provider contract allows inference requests to complete the warmup;
- for Mixedbread specifically, a `warming` health response means the service is reachable but the model may still be lazily loading, so the transport may continue to the rerank call for the same attempt;
- if the subsequent rerank call still fails with a retryable error, the retry loop must handle that failure according to the active retry policy.

Non-retryable failures:
- HTTP `4xx`, except `429`;
- invalid request construction;
- invalid JSON response;
- missing required response fields;
- malformed candidate indices;
- malformed scores;
- duplicate indices;
- out-of-range indices;
- non-finite scores;
- response coverage mismatch.

## 9) Provider Notes

`MixedbreadAi`
- uses the API contract defined in `mixedbread_ai_api.md`;
- does not provide provider-reported token usage;
- requires local token-count estimation through `tokenizer_source`.

`VoyageAI`
- uses the API contract defined in `voyageai_api.md`;
- requires `top_k` in the request;
- provides provider-reported `usage.total_tokens`.

## 1) Purpose / Scope

This document defines the `CrossEncoderReranker` contract for `rag_runtime`.

It defines:
- cross-encoder reranker inputs;
- transport dependency contract;
- scoring and ranking behavior;
- output rules;
- reranker-owned failures;
- reranker observability hook.

This document does not define:
- provider wire contracts;
- transport-owned batching behavior;
- transport-owned tokenizer usage;
- transport-owned token counting;
- transport-owned retry behavior.

Those concerns are defined in:
- `Specification/codegen/rag_runtime/reranking/transport_integration.md`
- `Specification/codegen/rag_runtime/reranking/mixedbread_ai_api.md`
- `Specification/codegen/rag_runtime/reranking/voyageai_api.md`

## 2) Role Of The Cross-Encoder Reranker

The cross-encoder reranker is a transport-backed model reranker implementation.

Its purpose is:
- to score already retrieved candidates with a stronger learned relevance model;
- to preserve the full candidate set while changing candidate order;
- to provide a higher-quality reranking baseline than the heuristic implementation.

It is not:
- a retrieval engine;
- a generation model;
- a truncation stage;
- a provider-specific HTTP client.

## 3) Inputs

The cross-encoder reranker consumes:
- `ValidatedUserRequest.query`
- `Option<&GoldenRetrievalTargets>`
- `RetrievalOutput`
- `CrossEncoderRerankerSettings`
- `BoxedRerankingTransport`

Candidate count is controlled by:
- `RerankingSettings.candidate_k`

`RerankingSettings.final_k` is not used to truncate the cross-encoder reranker output.
It remains the metric cutoff and orchestration-owned generation-context cutoff after reranking returns the full candidate order.

When orchestration passes `Some(&GoldenRetrievalTargets)` for the current request:
- the cross-encoder reranker must compute reranking-stage retrieval-quality metrics at `RerankingSettings.final_k`;
- the cross-encoder reranker must call the helper defined by:
  - `Specification/codegen/rag_runtime/retrieval_metrics.md`
  with:
  - the current request's `GoldenRetrievalTargets`
  - the ordered reranked chunk-id list produced by the cross-encoder reranker
  - `RerankingSettings.final_k`
- the returned `RetrievalQualityMetrics` bundle must be written into `RerankedRetrievalOutput.metrics`.

## 4) Dependency Contract

The cross-encoder reranker must receive:
- fully typed `CrossEncoderRerankerSettings`;
- a boxed transport dependency.

The crate-level source of truth for those contracts is:
- `Specification/codegen/rag_runtime/rag_runtime.md`
- `Specification/codegen/rag_runtime/reranking/transport_integration.md`

Rules:
- the cross-encoder reranker must not read raw TOML or raw environment variables directly;
- the cross-encoder reranker must not construct provider-specific transport payloads directly;
- the boxed transport dependency must be typed as `Box<dyn RerankingTransport + Send + Sync>`;
- the concrete transport implementation is created by orchestration, boxed, and passed into the cross-encoder reranker as a dependency;
- the cross-encoder reranker must call transport through the normalized transport interface defined in `transport_integration.md`.

## 5) Transport Request / Response Flow

For one rerank execution, the cross-encoder reranker must:
- build one normalized `RerankingTransportRequest` from the validated query and the current retrieval candidates;
- pass that normalized request together with the active `CrossEncoderTransportSettings` to the injected transport;
- receive one normalized `RerankingTransportResponse` from the transport.

Request-construction rules:
- `RerankingTransportRequest.query` must come from `ValidatedUserRequest.query`;
- `RerankingTransportRequest.documents` must contain the retrieved candidate texts in retrieval order;
- `RerankingTransportRequest.top_k` must be chosen according to the active transport contract.

Response-interpretation rules:
- `RerankingTransportResponse.results` is the source of truth for final cross-encoder candidate ordering;
- `RerankingTransportResponse.results[*].score` must be written into `RerankedChunk.rerank_score`;
- `RerankingTransportResponse.results[*].index` must be used to recover the matching retrieval candidate;
- `RerankedRetrievalOutput.total_tokens` must come from `RerankingTransportResponse.total_tokens`.

## 6) Scoring And Ranking Rules

The cross-encoder reranker must:
- read one normalized model score for every input candidate;
- store that model score as `rerank_score`;
- preserve the original retrieval score as `retrieval_score`;
- not apply any heuristic combination on top of the transport score;
- preserve the final candidate order produced by the normalized transport response;
- preserve all candidates returned by retrieval;
- return the full reranked candidate set without truncation;
- preserve chunk payloads unchanged.

Tie-breaking rule:
- when two candidates have equal `rerank_score`, preserve their original retrieval/input order.

## 7) Output Contract

The cross-encoder reranker returns:
- `RerankedRetrievalOutput`

Output rules:
- every candidate in the input retrieval output must appear exactly once in the output;
- output order must reflect final cross-encoder reranking order;
- output items must contain both `retrieval_score` and `rerank_score`;
- output must preserve the full candidate set exactly once;
- `RerankedRetrievalOutput.total_tokens` must contain the transport-produced reranking token count when available;
- `RerankedRetrievalOutput.metrics`, when present, contains cross-encoder-reranking-stage metric values computed at `RerankingSettings.final_k`.

## 8) Failure Rules

The cross-encoder reranker may fail for:
- invalid `CrossEncoderRerankerSettings`;
- transport execution failure;
- invalid normalized response-to-candidate mapping;
- retrieval metrics helper failure;
- non-finite scores.

The cross-encoder reranker must not fail merely because:
- retrieval returned one candidate;
- retrieval already returned a good order;
- the model score is negative.

## 9) Observability Hook

The cross-encoder reranker uses the `reranking` stage observability contract defined by:
- `Specification/codegen/rag_runtime/reranking/integration.md`
- `Specification/codegen/rag_runtime/observability/spans.md`
- `Specification/codegen/rag_runtime/observability/metrics.md`
- `Specification/codegen/rag_runtime/observability/openinference_spans.md`

It must at minimum support:
- reranking stage latency;
- OpenInference `RERANKER` span classification;
- `reranker.kind`;
- `reranker.retrieval_scores`;
- `reranker.rerank_scores`;
- `reranker.result_indices`.

Metric rules:
- the cross-encoder reranker must use the retrieval metrics helper defined by:
  - `Specification/codegen/rag_runtime/retrieval_metrics.md`
- the cross-encoder reranker must not duplicate retrieval-quality formulas inline across multiple call sites;
- if the retrieval metrics helper rejects invalid metric inputs, the cross-encoder reranker must surface that failure as a reranking-owned failure;
- when orchestration passes `None` for the current request, `RerankedRetrievalOutput.metrics` must be `None`;
- when orchestration passes `Some(&GoldenRetrievalTargets)` for the current request, `RerankedRetrievalOutput.metrics` must contain cross-encoder-reranking-stage metrics computed at `RerankingSettings.final_k`.

## 10) Unit-Test Hook

Required generated tests for the cross-encoder reranker are defined in:
- `Specification/codegen/rag_runtime/unit_tests.md`

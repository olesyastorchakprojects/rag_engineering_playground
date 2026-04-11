## 1) Purpose / Scope

This document defines the module-level integration contract for `reranking`.

It defines:
- the responsibility boundary of the `reranking` module;
- the public reranker interface;
- pass-through behavior;
- reranking-owned error categories;
- reranking-owned observability requirements.

This document does not define:
- crate-level pipeline sequencing;
- crate-level shared types;
- crate-level settings-loading rules;
- request-capture assembly rules;
- heuristic scoring details.
- cross-encoder HTTP payload details.

Those concerns are defined in:
- `Specification/codegen/rag_runtime/rag_runtime.md`
- `Specification/codegen/rag_runtime/orchestration.md`
- `Specification/codegen/rag_runtime/reranking/heuristic.md`
- `Specification/codegen/rag_runtime/reranking/cross_encoder.md`
- `Specification/codegen/rag_runtime/reranking/mixedbread_ai_api.md`
- `Specification/codegen/rag_runtime/reranking/voyageai_api.md`
- `Specification/codegen/rag_runtime/reranking/transport_integration.md`

## 2) Module Responsibility

`reranking` is the post-retrieval ordering module inside `rag_runtime`.

This module:
- receives a validated request together with raw retrieval output;
- may receive per-request golden retrieval targets from orchestration during evaluated batch execution;
- applies the reranker implementation selected by orchestration;
- computes one final rerank score per candidate;
- returns final candidate order for downstream generation and request-capture assembly.

This module does not:
- select which reranker implementation to instantiate;
- own crate-level pipeline sequencing;
- call the embedding service;
- call Qdrant;
- assemble prompts for generation;
- call the chat model;
- write request-capture records directly;
- read raw TOML or raw environment variables directly.

Construction rule:
- orchestration owns reranker selection and concrete reranker construction based on `Settings.reranking.reranker`;
- for the current version, orchestration constructs:
  - `PassThroughReranker::new()` for `RerankerSettings::PassThrough`
  - `HeuristicReranker::new(settings.weights.clone())` for `RerankerSettings::Heuristic(settings)`
  - `CrossEncoderReranker::new(settings.clone(), transport)` for `RerankerSettings::CrossEncoder(settings)`
- `reranking` owns only execution of the selected reranker implementation through the declared module interface.

## 3) Public Module Interface

The module must expose an async interface.

Required public interface:

```rust
#[async_trait::async_trait]
pub trait Reranker {
    async fn rerank(
        &self,
        request: &ValidatedUserRequest,
        golden_targets: Option<&GoldenRetrievalTargets>,
        retrieval_output: RetrievalOutput,
    ) -> Result<RerankedRetrievalOutput, RagRuntimeError>;
}
```

Interface rules:
- the interface must be asynchronous;
- the generated implementation must use the `async-trait` crate for this interface;
- the interface must receive `&ValidatedUserRequest`;
- the interface must receive `Option<&GoldenRetrievalTargets>`;
- `golden_targets` comes from orchestration and is present only during evaluated batch execution for requests that have a matching companion entry;
- the interface must consume `RetrievalOutput`;
- the interface must return `RerankedRetrievalOutput` on success;
- the interface must return `RagRuntimeError` on failure;
- module-internal logic uses `RerankingError` before conversion to `RagRuntimeError`.

Implementation rule:
- `pass_through`, `heuristic`, `cross_encoder`, and future rerankers must conform to the same interface.
- when orchestration passes `Some(&GoldenRetrievalTargets)` for the current request, reranker implementations must compute retrieval-quality metrics according to:
  - `Specification/codegen/rag_runtime/retrieval_metrics.md`
- when orchestration passes `Some(&GoldenRetrievalTargets)` for the current request, reranker implementations must call the helper defined by:
  - `Specification/codegen/rag_runtime/retrieval_metrics.md`
  with:
  - the current request's `GoldenRetrievalTargets`
  - the ordered reranked output chunk-id list produced by the reranker
  - the effective reranking-stage `k`
- the returned `RetrievalQualityMetrics` bundle must be written into `RerankedRetrievalOutput.metrics`;
- if the retrieval metrics helper rejects invalid metric inputs, reranker implementations must treat that failure as a reranking-owned failure;
- helper failures must be wrapped into `RerankingError` rather than exposed as an independent public error domain;
- when orchestration passes `None` for the current request, reranker implementations must not synthesize retrieval-quality metrics.

## 4) Pass-Through Contract

`pass_through` is a valid reranker implementation.

Required behavior:
- copy every input candidate from `RetrievalOutput.chunks` into output in the same order;
- preserve every candidate `chunk` exactly as received from `retrieval`;
- preserve every candidate `retrieval_score` exactly as received from `retrieval`;
- set `rerank_score = retrieval_score` for every candidate;
- return `RerankedRetrievalOutput` with the same candidate count as the input `RetrievalOutput`.

Rules:
- pass-through must be implemented as a real reranker implementation, not as a pipeline bypass;
- pass-through must still execute through the reranking interface;
- pass-through must still emit reranking observability.
- when orchestration passes `Some(&GoldenRetrievalTargets)` for the current request, pass-through must compute reranking-stage retrieval-quality metrics at `Settings.reranking.final_k` through the shared retrieval metrics helper;
- when orchestration passes `None` for the current request, pass-through must return `RerankedRetrievalOutput.metrics = None`.

## 5) Error Model

The module must define:
- `RerankingError`

Required failure categories:
- invalid reranker configuration;
- invalid internal scoring state;
- retrieval metrics helper failure;
- unexpected candidate transformation failure.

Rules:
- unsupported reranker kind is not a reranking-module runtime failure; reranker-kind selection belongs to orchestration and startup/configuration handling;
- reranking errors remain reranking-owned failures;
- reranking failures must surface as `RagRuntimeError::Reranking(...)`;
- raw third-party errors must not leak through the public interface;
- module-level errors must be converted to `RagRuntimeError` at the module boundary.

## 6) Observability Requirements

`reranking` is an observability-owning stage.

The observability source of truth for this module is:
- `Specification/codegen/rag_runtime/observability/observability.md`
- `Specification/codegen/rag_runtime/observability/spans.md`
- `Specification/codegen/rag_runtime/observability/metrics.md`

Required rules:
- `reranking` must emit its own stage span;
- reranking stage latency must be recorded through `rag_stage_duration_ms`;
- reranking observability must work for `pass_through`, `heuristic`, and `cross_encoder`.

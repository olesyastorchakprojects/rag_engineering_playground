## 1) Purpose / Scope

This document defines the module-level integration contract for `retrieve`.

It defines:
- the responsibility boundary of the `retrieve` module;
- the public retriever interface;
- retrieval-owned error categories;
- retrieval-owned observability requirements.

This document does not define:
- crate-level pipeline sequencing;
- crate-level shared types;
- crate-level settings-loading rules;
- retriever-implementation-specific request details.

Those concerns are defined in:
- `Specification/codegen/rag_runtime/rag_runtime.md`
- `Specification/codegen/rag_runtime/orchestration.md`
- `Specification/codegen/rag_runtime/retrieve/dense_retrieval.md`
- `Specification/codegen/rag_runtime/retrieve/hybrid_retrieval.md`

## 2) Module Responsibility

`retrieve` is the retrieval-execution module inside `rag_runtime`.

This module:
- receives a validated request;
- may receive per-request golden retrieval targets from orchestration during evaluated batch execution;
- applies the retriever implementation selected by orchestration;
- executes retrieval through the selected implementation;
- returns `RetrievalOutput` for downstream reranking or generation.

This module does not:
- select which retriever implementation to instantiate;
- own crate-level pipeline sequencing;
- perform reranking;
- assemble prompts for generation;
- call the chat model;
- write request-capture records directly;
- read raw TOML or raw environment variables directly.

## 3) Public Module Interface

The module must expose an async interface.

Required public interface:

```rust
#[async_trait::async_trait]
pub trait Retriever {
    async fn retrieve(
        &self,
        request: &ValidatedUserRequest,
        golden_targets: Option<&GoldenRetrievalTargets>,
        settings: &RetrievalSettings,
    ) -> Result<RetrievalOutput, RagRuntimeError>;
}
```

Interface rules:
- the interface must be asynchronous;
- the generated implementation must use the `async-trait` crate for this interface;
- the interface must receive `&ValidatedUserRequest`;
- the interface must receive `Option<&GoldenRetrievalTargets>`;
- `golden_targets` comes from orchestration and is present only during evaluated batch execution for requests that have a matching companion entry;
- the interface must receive `&RetrievalSettings` explicitly;
- the interface must return `RetrievalOutput` on success;
- the interface must return `RagRuntimeError` on failure;
- module-internal logic uses `RetrievalError` before conversion to `RagRuntimeError`.

Implementation rule:
- `dense`, `hybrid`, and future retrievers must conform to the same interface.
- when orchestration passes `Some(&GoldenRetrievalTargets)` for the current request, retriever implementations must compute retrieval-quality metrics according to:
  - `Specification/codegen/rag_runtime/retrieval_metrics.md`
- if the retrieval metrics helper rejects invalid metric inputs, retriever implementations must treat that failure as a retrieval-owned failure;
- helper failures must be wrapped into `RetrievalError` rather than exposed as an independent public error domain;
- when orchestration passes `None` for the current request, retriever implementations must not synthesize retrieval-quality metrics.

## 4) Error Model

The module must define:
- `RetrievalError`

Required failure categories:
- invalid retriever configuration;
- invalid retriever settings shape;
- retrieval execution failure;
- retrieval metrics helper failure;
- unexpected internal retrieval state.

Rules:
- retriever selection and retriever construction are orchestration-owned concerns and are outside the scope of this module-level integration contract;
- retrieval failures must surface as `RagRuntimeError::Retrieval(...)`;
- raw third-party errors must not leak through the public interface;
- module-level errors must be converted to `RagRuntimeError` at the module boundary.

## 5) Observability Requirements

`retrieve` is an observability-owning stage.

The observability source of truth for this module is:
- `Specification/codegen/rag_runtime/observability/observability.md`
- `Specification/codegen/rag_runtime/observability/spans.md`
- `Specification/codegen/rag_runtime/observability/metrics.md`

Required rules:
- `retrieve` must emit its own stage span;
- retrieve stage latency must be recorded through `rag_stage_duration_ms`;
- retrieval observability must work for `dense`, `hybrid`, and future retriever implementations.

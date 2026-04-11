## 1) Purpose / Scope

`orchestration` sequences the request flow across `input_validation`, `retrieval`, `reranking`, `generation`, and the request-capture persistence boundary.

During evaluated batch execution, `orchestration` also owns:

- loading the golden retrieval companion file passed through `--golden-retrievals-file`;
- building question-to-golden lookup state by raw batch question text;
- validating that all batch questions have a matching golden entry before stage execution begins;
- passing the matching per-question golden retrieval targets into retrieval and reranking;
- deriving request-level retrieval-quality attributes for the root request span from stage-returned metric bundles;
- emission of request-level retrieval-quality attributes on `rag.request`.

This module does not:
- validate raw user input by itself;
- perform retrieval logic;
- perform reranking logic;
- perform generation logic;
- build prompts;
- call external providers directly;
- compute rerank scores;
- read raw TOML directly;
- read raw config maps directly.

## 2) Public Interface

```rust
pub struct Orchestrator;

impl Orchestrator {
    pub async fn handle(
        request: UserRequest,
        settings: &Settings,
    ) -> Result<UserResponse, RagRuntimeError>;
}
```

`UserRequest`, `GenerationRequest`, `GenerationResponse`, `UserResponse`, and `Settings` are defined by the crate-level contract in `rag_runtime.md`.

## 3) Configuration Usage

`orchestration` receives `&Settings`.

Request-handling rules:

- `orchestration` must pass `&Settings.input_validation` to `input_validation`;
- `orchestration` must pass `&Settings.generation` to `generation`;
- `orchestration` must use `&Settings.request_capture` only for passing it to the request-capture persistence boundary after successful request completion;
- `orchestration` must not read raw TOML or raw config maps during request handling.
- `orchestration` must select the concrete retriever implementation from `Settings.retrieval.ingest`;
- `orchestration` must construct that retriever before invoking the retrieval stage;
- `orchestration` must select the concrete reranker implementation from `Settings.reranking.reranker`;
- `orchestration` must construct that reranker before invoking the reranking stage;
- `orchestration` must provide reranker-owned typed settings to the concrete reranker at construction time;
- `orchestration` must construct the concrete cross-encoder transport implementation before constructing `CrossEncoderReranker`;
- `orchestration` must select the concrete transport implementation from `Settings.generation.transport` and pass it to `Generator::new`; see Transport selection rules.
- when evaluated batch execution is enabled through `--golden-retrievals-file`, `orchestration` must load the golden retrieval companion file defined by:
  - `Specification/contracts/rag_runtime/golden_retrieval_companion.md`
- when evaluated batch execution is enabled through `--golden-retrievals-file`, `orchestration` must build question-to-golden lookup state keyed by `questions[<query>].question` from the companion file;
- when evaluated batch execution is enabled through `--golden-retrievals-file`, `orchestration` must validate before stage execution begins that every non-empty line from `--questions-file` has a matching companion entry where `questions[<query>].question` is exactly equal to that batch question string;
- if any non-empty line from `--questions-file` does not have a matching companion entry where `questions[<query>].question` is exactly equal to that batch question string, orchestration must fail the batch run with an orchestration-owned error before retrieval, reranking, or generation is invoked for any request in that batch run.

Retriever selection rules:

- `Settings.retrieval.ingest = RetrievalIngest::Dense(DenseRetrievalIngest)` must construct a `DenseRetriever` implementation of `Retriever`;
- `Settings.retrieval.ingest = RetrievalIngest::Hybrid(HybridRetrievalIngest)` must construct a `HybridRetriever` implementation of `Retriever`;
- unknown `Settings.retrieval.ingest` is a startup/configuration error and must fail before request handling begins;
- after selection, orchestration must hold the chosen retriever as `Box<dyn Retriever + Send + Sync>`.

Reranker selection rules:

- `Settings.reranking.reranker = RerankerSettings::PassThrough` must construct `PassThroughReranker::new()`;
- `Settings.reranking.reranker = RerankerSettings::Heuristic(settings)` must construct `HeuristicReranker::new(settings.weights.clone())`;
- `Settings.reranking.reranker = RerankerSettings::CrossEncoder(settings)` must construct `CrossEncoderReranker::new(settings.clone(), transport)`;
- after selection, orchestration must hold the chosen reranker as `Box<dyn Reranker + Send + Sync>`.

Cross-encoder transport selection rules:

- `settings.transport = CrossEncoderTransportSettings::MixedbreadAi(_)` must construct `MixedbreadAiRerankingTransport::new()`;
- `settings.transport = CrossEncoderTransportSettings::VoyageAi(_)` must construct `VoyageAiRerankingTransport::new()`;
- after construction, the transport must be boxed as `Box<dyn RerankingTransport + Send + Sync>`;
- the boxed transport must be passed to `CrossEncoderReranker::new(...)`.

Transport selection rules:

- `Settings.generation.transport = TransportSettings::Ollama(_)` must construct `OllamaTransport::new()`;
- `Settings.generation.transport = TransportSettings::OpenAi(_)` must construct `OpenAiTransport::new()`;
- unknown `Settings.generation.transport` variant is a startup/configuration error and must fail before request handling begins;
- after construction, the transport must be passed to `Generator::new(transport)`;
- at request time, `Generator.generate` is called with `&Settings.generation`.

## 4) Algorithm

For each request:

1. Receive `UserRequest`.
2. Call `input_validation` with the received `UserRequest` and `&Settings.input_validation`.
3. Select and construct the concrete retriever implementation from `Settings.retrieval.ingest`.
4. When evaluated batch execution is enabled, resolve the current request's `GoldenRetrievalTargets` by exact raw `UserRequest.query`.
5. Call the selected retriever with `&ValidatedUserRequest` returned by `input_validation`, the current request's `Option<&GoldenRetrievalTargets>`, and `&Settings.retrieval`.
6. If `RetrievalOutput.chunks` is empty, return an error.
7. Select and construct the concrete reranker implementation from `Settings.reranking.reranker`.
8. When the selected reranker is `CrossEncoder`, first construct the concrete cross-encoder transport, box it, and pass it into `CrossEncoderReranker::new(...)`.
9. Call the selected reranker with the `ValidatedUserRequest`, the current request's `Option<&GoldenRetrievalTargets>`, and `RetrievalOutput`.
10. Require that reranking returns the full candidate set without truncation.
11. Select the first `Settings.reranking.final_k` candidates from `RerankedRetrievalOutput.chunks` for the generation context.
12. Build `GenerationRequest` from `ValidatedUserRequest.query` and that selected reranked prefix.
13. Pass the selected reranked prefix into `GenerationRequest.chunks` in final reranked order.
14. Do not call `generation` if `RetrievalOutput.chunks` is empty.
15. Call `generation` with `GenerationRequest` and `&Settings.generation`.
16. When `RetrievalOutput.metrics` and `RerankedRetrievalOutput.metrics` are present, derive and write request-level retrieval-quality attributes on the root request span from those two metric bundles.
17. Build `RequestCapture` from the successful completed request state, including `retriever_kind`, `retriever_config`, `reranker_kind`, and `reranker_config`.
    - populate `retrieval_stage_metrics` from `RetrievalOutput.metrics` returned at step 5; set to `None` when `RetrievalOutput.metrics` is `None`;
    - populate `reranking_stage_metrics` from `RerankedRetrievalOutput.metrics` returned at step 9; set to `None` when `RerankedRetrievalOutput.metrics` is `None`.
18. Pass `RequestCapture` and `&Settings.request_capture` to the request-capture persistence boundary.
19. Build `UserResponse` from `GenerationResponse.answer`.
20. Return `UserResponse`.

`RequestCapture` field population rules are defined in:

- `Specification/codegen/rag_runtime/rag_runtime.md`

`orchestration` is responsible only for assembling the domain `RequestCapture` value from the successful completed request state and passing that value to the request-capture persistence boundary.

Request-capture boundary rules:

- `orchestration` assembles the domain `RequestCapture` type;
- `orchestration` must not construct storage-specific row shapes;
- `orchestration` must not perform SQL serialization;
- `orchestration` must not issue database queries directly.

Request-capture failure policy:

- after successful generation, request-capture persistence is best effort;
- if request-capture persistence fails, `orchestration` must not replace a successful `UserResponse` with that failure;
- request-capture persistence failure may be logged or traced by `orchestration`;
- request-capture persistence failure does not change successful request completion into request failure.

## 5) Error Model

The module must define:

- `OrchestrationError`

`OrchestrationError` must include module-specific variants for orchestration failures.

Required failure categories:

- empty retrieval output;
- evaluated batch question missing from golden retrieval companion file;
- unexpected internal state.

Failure-domain rules:

- `input_validation`, `retrieval`, `reranking`, and `generation` must return `RagRuntimeError` at their module boundaries;
- `orchestration` must not reinterpret module failures as different module failures;
- reranking failures must propagate as `RagRuntimeError::Reranking(...)` rather than being wrapped into `OrchestrationError`;
- orchestration-owned failures must be converted to `RagRuntimeError::Orchestration(...)` at module boundary.

## 6) Constraints / Non-Goals

This module must not:

- perform input validation logic by itself;
- perform retrieval logic by itself;
- perform reranking logic by itself;
- perform generation logic by itself;
- build prompts;
- call external provider APIs directly;
- compute rerank scores or reorder candidates by itself;
- compute retrieval-stage or reranking-stage retrieval-quality metric values by itself;
- mutate the validated query semantically;
- expose module-private intermediate types at crate boundary.

## 7) Unit Test Requirements

Required generated unit tests for `orchestration` are defined in:

- `Specification/codegen/rag_runtime/unit_tests.md`

Generation for `orchestration` is incomplete if any required unit test for this module from `Specification/codegen/rag_runtime/unit_tests.md` is missing.

## 1) Purpose / Scope

This document defines the mandatory generated unit-test contract for the `rag_runtime` crate.

This document is the single source of truth for:
- shared unit-test generation rules;
- required shared test helpers;
- required module-level unit-test cases;
- required coverage tooling;
- required coverage interpretation rules;
- required module-level coverage thresholds.

Code generation for `rag_runtime` is incomplete if the generated Rust source omits any required unit tests or omits required coverage measurement support defined by this document.

`main.rs` is outside the mandatory unit-test scope of this document.

## 2) General Generation Rules

Generated unit tests must satisfy all of the following rules:

- unit tests must be generated in the same generation pass as the runtime implementation;
- unit tests must use the actual function names, type names, field names, and error enum variants present in the generated Rust code;
- unit tests must be deterministic;
- unit tests must not depend on external network access;
- unit tests must not depend on running Docker containers, collector processes, Qdrant processes, Ollama processes, or Hugging Face availability;
- unit tests must execute locally inside the Rust test process;
- unit tests must assert exact contract-relevant outcomes;
- success-path tests must assert exact returned values and exact request payload structure when request construction is part of the contract;
- failure-path tests must assert the exact returned error variant;
- if a returned error variant contains structured fields, tests must assert the relevant field values;
- required tests must be implemented as executable Rust tests;
- comments, TODO items, prose test plans, pseudo-tests, placeholder test functions without assertions, and empty test modules do not satisfy any required unit-test case from this document;
- tests must not introduce new public runtime APIs solely for testability;
- tests must cover public entrypoints and contract-relevant private helpers;
- tests for HTTP-calling modules must use local mock HTTP servers created inside Rust tests;
- tests for startup/config logic must use temporary files and temporary environment-variable setup created inside Rust tests.
- tests must not write request-capture rows into a live `request_captures` table as part of normal unit-test execution;
- tests that execute the real orchestration/runtime request path must use a no-op or mocked request-capture persistence boundary instead of the production PostgreSQL writer;
- code generation is incomplete if the generated test path can write `question`, `hello world`, or other deterministic test payloads into a live eval database through the production request-capture persistence path.

Required test placement rules:

- required module unit tests live inline under `#[cfg(test)] mod tests` inside the corresponding Rust module file;
- the only mandatory out-of-line test artifact is `Execution/rag_runtime/tests/e2e_smoke.rs`;
- shared test helpers live in `Execution/rag_runtime/src/test_support.rs` or another internal test-only Rust file under `Execution/rag_runtime/src/`;
- generation is incomplete if a required module test set is replaced by comments, TODO markers, or a non-executable checklist.

## 3) Required Shared Test Helpers

Generated unit tests must include shared helper code that provides all of the following capabilities:

- construction of a deterministic test tokenizer for `input_validation`;
- construction of deterministic test `Settings` values for `retrieval`, `generation`, `orchestration`, `request_capture_store`, and `lib`;
- construction of disabled observability runtime state for tests that do not require live exporters;
- local HTTP mock-server support that:
  - listens on `127.0.0.1` on an ephemeral port;
  - accepts test requests from the runtime under test;
  - returns preconfigured HTTP responses in deterministic order;
  - records observed request bodies for later assertions;
- temporary-directory support for config-loading tests;
- temporary environment-variable setup and restoration for config-loading tests;
- current-working-directory setup and restoration when config-loading tests require isolated startup context.

The generated test helper code must remain internal to test builds.
The generated production API must not expose test-only helpers.
Shared test helpers live in a dedicated internal test-only module under `Execution/rag_runtime/src/`.

Environment-sensitive HTTP test fallback rules:

- tests that require local mock HTTP servers are normal non-ignored tests when the execution environment permits loopback socket binding;
- if the execution environment initially forbids loopback socket binding or other capabilities required by the generated required tests, the generator or validating agent must request the elevated privileges needed to execute those tests normally;
- required environment-sensitive HTTP tests must remain normal non-ignored tests and must be executed once the required privileges or capabilities are granted;
- inability to execute a required test in the current sandbox is not a reason to replace that test with `#[ignore]`;
- non-network unit tests remain non-ignored;
- `#[ignore]` is forbidden for required core module tests and required environment-sensitive HTTP tests;
- ignored tests do not count toward the minimum executable test counts defined by this document.

## 4) Required Unit Tests By Module

4.1) `input_validation`
------------------------

Generated unit tests for `input_validation` must include all of the following cases:

- non-empty query passes validation and returns normalized `ValidatedUserRequest.query`;
- whitespace-only query is rejected when `reject_empty_query = true`;
- leading and trailing whitespace is removed when `trim_whitespace = true`;
- repeated internal whitespace is collapsed when `collapse_internal_whitespace = true`;
- normalization preserves original spacing when normalization flags are disabled;
- query exactly at the token limit passes validation when token count is computed after enabled normalization steps;
- query above the token limit fails with the exact token-limit error variant when token count is computed after enabled normalization steps;
- validation fails with the exact empty-query error variant when normalized query becomes empty;
- identical input and identical settings produce the same normalized output;
- startup-time tokenizer initialization fails when tokenizer artifacts cannot be loaded from the configured Hugging Face repo id;
- startup-time tokenizer initialization fails when the tokenizer download returns non-2xx HTTP status;
- startup-time tokenizer initialization fails when downloaded tokenizer bytes are not a valid tokenizer artifact.

4.2) `retrieval`
----------------

Generated unit tests for `retrieval` must include all of the following cases:

- tests that cover retry behavior verify that retry execution follows the configured retry policy;
- one unit test covers transient embedding failure followed by success before `max_attempts` is exhausted;
- one unit test covers embedding retry exhaustion after `max_attempts`;
- one unit test covers transient Qdrant failure followed by success before `max_attempts` is exhausted;
- one unit test covers Qdrant retry exhaustion after `max_attempts`;
- when orchestration passes `Some(&GoldenRetrievalTargets)`, retrieval computes `RetrievalOutput.metrics` from the helper result and preserves the retrieved chunk order in `RetrievalOutput.chunks`;
- when orchestration passes `None`, retrieval returns `RetrievalOutput.metrics = None` and does not synthesize retrieval-quality values;
- if the retrieval metrics helper rejects invalid metric input, retrieval returns the exact retrieval-owned error variant for helper failure.

4.2r) `retrieval_metrics`
-------------------------

Generated unit tests for `retrieval_metrics` must include all of the following cases:

- recall uses the deduplicated `ActualTopK_dedup` view rather than counting repeated chunk ids multiple times;
- `rr_at_k_soft` returns `1 / rank` of the first soft-relevant chunk in `ActualTopK_dedup`;
- `rr_at_k_strict` returns `0` when no strict-relevant chunk exists in `ActualTopK_dedup`;
- `first_relevant_rank_soft` and `first_relevant_rank_strict` are derived from `ActualTopK_dedup` and are omitted when no matching relevant chunk exists;
- `num_relevant_soft` and `num_relevant_strict` count unique relevant chunk ids in `ActualTopK_dedup`;
- `ndcg_at_k` uses the deduplicated actual ranking and the ideal ranking derived from unique graded relevance items sorted by descending score;
- duplicate chunk ids in the raw ranked input do not increase recall, reciprocal-rank, relevant-count, DCG, or nDCG values after the first occurrence;
- helper rejects invalid input when `soft_positive_chunk_ids` is empty;
- helper rejects invalid input when `strict_positive_chunk_ids` is empty;
- helper rejects invalid input when `strict_positive_chunk_ids` is not a subset of `soft_positive_chunk_ids`;
- helper rejects invalid input when a soft-positive or strict-positive chunk id is missing from `graded_relevance`;
- helper rejects invalid input when `graded_relevance` contains unsupported score values outside the current contract.

Placement rule for `retrieval_metrics` tests:

- these tests must live in the dedicated helper module defined by `Specification/codegen/rag_runtime/retrieval_metrics.md`;
- these helper-module tests are required in addition to the retrieval, reranking, orchestration, and observability test sets that depend on the helper.

4.2a) `retrieval.dense`
-----------------------

Generated unit tests for dense retrieval must include all of the following cases:

- successful embedding response with exactly one embedding and valid Qdrant response returns `RetrievalOutput`, preserving Qdrant hit order in `RetrievalOutput.chunks`;
- embedding request transport failure returns the exact embedding-request error variant;
- embedding non-2xx HTTP status returns the exact embedding-request error variant;
- embedding success response with invalid JSON shape returns the exact embedding-response-validation error variant;
- embedding success response without `embeddings` returns the exact embedding-response-validation error variant;
- embedding success response with `embeddings` not being an array returns the exact embedding-response-validation error variant;
- embedding success response with embedding item not being an array returns the exact embedding-response-validation error variant;
- embedding success response with zero embeddings fails with the exact embedding-response-validation error variant;
- embedding success response with more than one embedding fails with the exact embedding-response-validation error variant;
- embedding dimension mismatch fails with the exact embedding-dimension-mismatch error variant;
- Qdrant request transport failure returns the exact Qdrant-request error variant;
- Qdrant non-2xx HTTP status returns the exact Qdrant-request error variant;
- Qdrant success response without `result` returns the exact Qdrant-response-validation error variant;
- Qdrant success response with `result` that is neither an array nor an object with `points` returns the exact Qdrant-response-validation error variant;
- Qdrant hit without `score` returns the exact Qdrant-response-validation error variant;
- Qdrant hit without `payload` returns the exact Qdrant-response-validation error variant;
- payload that cannot be mapped into `Chunk` returns the exact payload-mapping error variant;
- payload that deserializes into `Chunk` but violates the canonical chunk contract returns the exact payload-mapping error variant;
- empty Qdrant result returns `RetrievalOutput { chunks: vec![] }`;
- tests that cover request construction for Qdrant query inspect the request body sent to the mocked Qdrant endpoint and verify:
  - `with_payload = true`
  - `with_vector = false`
  - no `using` field when `qdrant_vector_name = "default"`;

4.2b) `retrieval.hybrid`
------------------------

Generated unit tests for hybrid retrieval must include all of the following cases:

- successful hybrid retrieval with valid embedding response, valid sparse query vector construction, and valid Qdrant response returns `RetrievalOutput`, preserving Qdrant fused hit order in `RetrievalOutput.chunks`;
- hybrid sparse query construction follows the configured sparse vocabulary and ignores out-of-vocabulary query tokens;
- `RetrievalStrategy::BagOfWords(BagOfWordsRetrievalStrategy)` constructs a sparse query vector with the expected `indices` and `values` for controlled test tokens;
- `RetrievalStrategy::Bm25Like(Bm25LikeRetrievalStrategy)` constructs a sparse query vector with the expected `indices` and `values` for controlled test tokens and controlled term stats;
- hybrid retrieval fails with the exact sparse-vocabulary-loading error variant when `vocabulary_path` cannot be read;
- hybrid retrieval fails with the exact sparse-query-construction error variant when the sparse vocabulary artifact is invalid for the required schema;
- hybrid retrieval fails with the exact term-stats-loading error variant when `term_stats_path` cannot be read for `bm25_like`;
- hybrid retrieval fails with the exact term-stats-validation error variant when the BM25 term-stats artifact is invalid for the required schema;
- tests that cover hybrid Qdrant request construction inspect the request body sent to the mocked Qdrant endpoint and verify:
  - endpoint path uses the effective hybrid collection name;
  - top-level `query = { "fusion": "rrf" }`;
  - `prefetch` contains exactly one dense branch and exactly one sparse branch;
  - dense prefetch uses the configured dense vector name;
  - sparse prefetch uses the configured sparse vector name;
  - top-level `limit = RetrievalSettings.top_k`;
  - top-level `with_payload = true`;
  - top-level `with_vector = false`;
- hybrid Qdrant success response with `result.points` missing returns the exact Qdrant-response-validation error variant;
- hybrid Qdrant success response with `result.points` in invalid shape returns the exact Qdrant-response-validation error variant;

4.3) `generation`
-----------------

Tests in this section use a mock `GenerationTransport` implementation. They do not make real HTTP calls.

Generated unit tests for `generation` must include all of the following cases:

- `GenerationRequest.chunks = []` fails with the exact invalid-generation-input error variant;
- `GenerationRequest.chunks.len() > GenerationSettings.max_context_chunks` fails with the exact chunk-limit-exceeded error variant;
- fully assembled chat prompt exactly at `GenerationSettings.max_prompt_tokens` passes prompt-token validation;
- fully assembled chat prompt above `GenerationSettings.max_prompt_tokens` fails with the exact prompt-token-limit-exceeded error variant;
- a single-page chunk renders label `[page N]`;
- a multi-page chunk renders label `[pages N-M]`;
- multiple chunk blocks are joined with exactly `"\n\n"` in input order;
- user prompt substitution replaces `{{question}}` and `{{context_chunks}}` correctly;
- chunk text is inserted into the user prompt exactly as provided, including preserved leading and trailing whitespace inside `RetrievedChunk.chunk.text`;
- prompt token counting uses the generation tokenizer and is computed on the fully assembled chat prompt, not on the raw query alone;
- when mock transport returns `ModelAnswer.prompt_tokens = None` and `ModelAnswer.completion_tokens = None`, completion token counting uses the generation tokenizer and is computed on `ModelAnswer.content`;
- when mock transport returns `ModelAnswer.prompt_tokens = Some(p)` and `ModelAnswer.completion_tokens = Some(c)`, those values are used directly and local tokenizer counting is not applied;
- `GenerationResponse.total_tokens` equals `prompt_tokens + completion_tokens` in both token-count paths;
- generation preserves reranked chunk order exactly as received in `GenerationRequest.chunks`;
- mock transport failure returns the exact generation-request-failure error variant;
- startup-time generation tokenizer initialization fails when tokenizer artifacts cannot be loaded from the configured Hugging Face repo id;
- startup-time generation tokenizer initialization fails when the tokenizer download returns non-2xx HTTP status;
- startup-time generation tokenizer initialization fails when downloaded tokenizer bytes are not a valid tokenizer artifact.

4.3a) `OllamaTransport`
-----------------------

Tests in this section use a local mock HTTP server. They test the transport in isolation.

Generated unit tests for `OllamaTransport` must include all of the following cases:

- valid Ollama response returns `ModelAnswer.content` equal to `message.content` with `prompt_tokens = None` and `completion_tokens = None`;
- request body sent to the mock server contains exactly: `model = OllamaTransportSettings.model_name`, `stream = false`, `options.temperature = GenerationSettings.temperature`, exactly two `messages` with `role = "system"` and `role = "user"` in that order, and no other top-level fields;
- HTTP or network transport failure returns the exact generation-request-failure error variant;
- non-2xx HTTP response returns the exact generation-request-failure error variant;
- response body that is not a valid JSON object returns the exact generation-response-validation error variant;
- response body without `message` returns the exact generation-response-validation error variant;
- response body without `message.content` returns the exact generation-response-validation error variant;
- `transport` not matching `TransportSettings::Ollama` returns the exact unexpected-internal-state error variant;
- retry is attempted on transport failure and succeeds on the next attempt when the mock server fails once then succeeds.

4.3b) `OpenAiTransport`
-----------------------

Tests in this section use a local mock HTTP server. They test the transport in isolation.

Generated unit tests for `OpenAiTransport` must include all of the following cases:

- valid OpenAI-compatible response returns `ModelAnswer.content` equal to `choices[0].message.content` with `prompt_tokens = Some(usage.prompt_tokens)` and `completion_tokens = Some(usage.completion_tokens)`;
- request body sent to the mock server contains exactly: `model = OpenAiTransportSettings.model_name`, `temperature = GenerationSettings.temperature`, exactly two `messages` with `role = "system"` and `role = "user"` in that order, and no other top-level fields;
- request includes `Authorization: Bearer <api_key>` header with the value from `OpenAiTransportSettings.api_key`;
- HTTP or network transport failure returns the exact generation-request-failure error variant;
- non-2xx HTTP response returns the exact generation-request-failure error variant;
- response body that is not a valid JSON object returns the exact generation-response-validation error variant;
- response body without `choices` or with empty `choices` returns the exact generation-response-validation error variant;
- response body without `choices[0].message.content` returns the exact generation-response-validation error variant;
- response body without `usage` returns the exact generation-response-validation error variant;
- response body without `usage.prompt_tokens` or `usage.completion_tokens` returns the exact generation-response-validation error variant;
- `transport` not matching `TransportSettings::OpenAi` returns the exact unexpected-internal-state error variant;
- retry is attempted on transport failure and succeeds on the next attempt when the mock server fails once then succeeds.

4.4) `orchestration`
--------------------

Generated unit tests for `orchestration` must include all of the following cases:

- `Settings.retrieval.ingest = RetrievalIngest::Dense(DenseRetrievalIngest)` selects the dense retriever implementation;
- `Settings.retrieval.ingest = RetrievalIngest::Hybrid(HybridRetrievalIngest)` selects the hybrid retriever implementation;
- `Settings.reranking.reranker = RerankerSettings::PassThrough` selects the pass-through reranker implementation;
- `Settings.reranking.reranker = RerankerSettings::Heuristic(_)` selects the heuristic reranker implementation;
- `Settings.reranking.reranker = RerankerSettings::CrossEncoder(_)` selects the cross-encoder reranker implementation;
- `CrossEncoderTransportSettings::MixedbreadAi(_)` constructs and boxes `MixedbreadAiRerankingTransport` before passing it into `CrossEncoderReranker`;
- `CrossEncoderTransportSettings::VoyageAi(_)` constructs and boxes `VoyageAiRerankingTransport` before passing it into `CrossEncoderReranker`;
- happy-path request handling returns `UserResponse.answer` equal to the answer returned by `generation`;
- normalized query produced by `input_validation` is propagated into downstream request handling;
- `retrieval` output is passed to `reranking` before `generation`;
- final reranked chunks are passed to `generation` in reranked order;
- orchestration truncates reranked output to `Settings.reranking.final_k` only after reranking completes;
- empty retrieval output returns `RagRuntimeError::Orchestration(OrchestrationError::EmptyRetrievalOutput)`;
- `generation` is not called when retrieval output is empty;
- input-validation failure stops the pipeline before retrieval begins;
- retrieval failure stops the pipeline before generation begins;
- reranking failure stops the pipeline before generation begins;
- generation failure is propagated after successful retrieval;
- request-capture-store failure after successful generation does not replace a successful `UserResponse`;
- assembled request capture preserves both `retrieval_score` and `rerank_score` for each retrieval item;
- assembled request capture preserves `retriever_kind` for the selected retriever implementation;
- assembled request capture preserves `retriever_config` for the selected retriever implementation;
- evaluated batch execution fails before stage execution begins when any non-empty line from `--questions-file` does not exactly match a `questions[<query>].question` entry in the golden retrieval companion file;
- during evaluated batch execution, orchestration passes the matching `Some(&GoldenRetrievalTargets)` into both retrieval and reranking for the current request;
- when both stage metric bundles are available, orchestration derives request-level retrieval aggregate attributes from `RetrievalOutput.metrics` and `RerankedRetrievalOutput.metrics` without recomputing stage metrics itself.

4.4a) `reranking`
-----------------

Generated unit tests for `reranking` must include all of the following cases:

- `pass_through` reranking preserves candidate order;
- `pass_through` reranking preserves each candidate `retrieval_score` and copies it into `rerank_score`;
- heuristic reranking can reorder candidates when heuristic scores differ from retrieval order;
- cross-encoder reranking can reorder candidates when model scores differ from retrieval order;
- cross-encoder reranking consumes a boxed transport dependency rather than constructing provider-specific transport internals directly;
- heuristic reranking preserves the candidate set exactly once and does not drop or duplicate candidates;
- cross-encoder reranking preserves the candidate set exactly once and does not drop or duplicate candidates;
- reranking returns the full candidate set and does not truncate to `final_k`;
- heuristic reranking is deterministic for identical inputs and settings;
- cross-encoder reranking sorts by descending `rerank_score`, with equal-score order preserving original retrieval order;
- empty retrieval output returns `RerankedRetrievalOutput { chunks: vec![] }`;
- single-candidate retrieval output remains stable after reranking;
- changing configured heuristic weights can change final candidate ordering predictably in a controlled test input;
- reranking output exposes both `retrieval_score` and `rerank_score` for every returned item;
- cross-encoder reranking writes `RerankedRetrievalOutput.total_tokens` from `RerankingTransportResponse.total_tokens`;
- when orchestration passes `Some(&GoldenRetrievalTargets)`, reranking computes `RerankedRetrievalOutput.metrics` from the helper result using the reranked output order and `final_k`;
- when orchestration passes `None`, reranking returns `RerankedRetrievalOutput.metrics = None` and does not synthesize retrieval-quality values;
- if the retrieval metrics helper rejects invalid metric input, reranking returns the exact reranking-owned error variant for helper failure.

Generated unit tests for `orchestration` must use real module instances and local mock HTTP servers.

For the current version, generated unit tests for `orchestration` must also follow these isolation rules:

- the tests must still execute the real orchestration flow through input validation, retrieval, reranking, and generation;
- the tests must not use the production request-capture PostgreSQL writer;
- the generated code must therefore provide an internal no-op or mocked request-capture persistence boundary for test builds;
- the production runtime path must keep real request-capture persistence enabled outside test builds.

4.5) `config`
-------------

Generated unit tests for `config` must include all of the following cases:

- valid runtime config, valid ingest config, and required environment variables produce a valid merged `Settings`;
- missing required environment variable causes startup failure;
- schema-invalid `rag_runtime.toml` causes startup failure;
- `retrieval.kind = dense` is loaded into typed `Settings.retrieval.kind`;
- `retrieval.kind = hybrid` is loaded into typed `Settings.retrieval.kind`;
- valid hybrid ingest config produces typed `RetrievalIngest::Hybrid(HybridRetrievalIngest)` with typed `RetrievalStrategy`;
- `RetrievalSettings.top_k > GenerationSettings.max_context_chunks` is accepted and produces `Settings.reranking.candidate_k > Settings.reranking.final_k` when configured that way;
- reranking settings are loaded into `Settings.reranking`, including the active `RerankerSettings` variant, configured heuristic weights when present, configured cross-encoder transport settings when present, derived `candidate_k`, and derived `final_k`;
- `reranking.cross_encoder.transport_kind = "mixedbread-ai"` produces `CrossEncoderTransportSettings::MixedbreadAi(...)`;
- `reranking.cross_encoder.transport_kind = "voyageai"` produces `CrossEncoderTransportSettings::VoyageAi(...)`;
- generation tokenizer source and `generation.max_prompt_tokens` are loaded into `Settings.generation`;
- helper logic for TOML and JSON reading is covered by direct unit tests;
- default config-path helpers return repository paths defined by the crate contract.

4.6) `request_capture_store`
----------------------------

Generated unit tests for `request_capture_store` must include all of the following cases:

- valid `RequestCapture` passes JSON-schema validation before database write is attempted;
- invalid `RequestCapture` with empty required string field fails with the exact validation error variant before database write;
- invalid `RequestCapture` with `total_tokens != prompt_tokens + completion_tokens` fails with the exact validation error variant before database write;
- invalid `RequestCapture` with empty `retrieval_results` fails with the exact validation error variant before database write;
- invalid `RequestCapture` without any `selected_for_generation = true` item fails with the exact validation error variant before database write;
- valid dense `RequestCapture` preserves `retriever_kind = Dense`;
- valid dense `RequestCapture` preserves the expected `retriever_config` snapshot shape;
- valid heuristic `RequestCapture` preserves both `reranker_kind` and `reranker_config`;
- valid pass-through `RequestCapture` preserves `reranker_kind` and stores no `reranker_config`;
- `RequestCaptureStorageRowMapper` constructs the exact storage-facing payload shape required by the storage contract;
- `RequestCaptureStorageRowMapper` serializes `retrieval_results` into the exact JSON array shape required by the storage contract;
- `RequestCaptureStorageRowMapper` preserves final reranked item order during payload construction;
- `RequestCaptureStorageRowMapper` excludes storage-only fields that are produced by PostgreSQL rather than by `RequestCapture`.

Generated unit tests for `request_capture_store` must not require a live PostgreSQL instance, Docker container, or database connection.

For the current version, generated unit tests for `request_capture_store` must also follow these stability rules:

- tests that exercise JSON-schema validation failures must assert the exact `RequestCaptureStoreError::Validation` variant, but must not depend on the exact validator-produced error message text;
- mapper tests for `RetrievalResultItem.retrieval_score` and `RetrievalResultItem.rerank_score` must assert JSON shape and semantic value preservation, but must not depend on an exact decimal string representation of `f32` values such as `0.95`.

4.7) `lib`
----------

Generated unit tests for `lib` must include all of the following cases:

- `RagRuntime::handle_request(...)` returns a successful `UserResponse` on a valid end-to-end request;
- `RagRuntime::handle_request(...)` propagates request-level failure returned by downstream orchestration;
- `RagRuntime::from_config_paths(...)` constructs a runnable runtime from valid config files and required environment variables.

For the current version, generated unit tests for `lib` must also preserve request-capture isolation:

- `RagRuntime::handle_request(...)` tests must not write into a live `request_captures` table;
- `RagRuntime::from_config_paths(...)` tests may still construct a production-shaped runtime, but test execution must route request-capture persistence through the same internal no-op or mocked test boundary used by orchestration tests.

4.8) `observability`
--------------------

Generated unit tests for `observability` must include all of the following cases:

- initialization succeeds when tracing and metrics are both disabled;
- metric-recording methods do not panic when metrics are disabled;
- request-label construction returns the required semantic keys;
- stage-label construction returns the required semantic keys and status label;
- stage-label construction supports `reranking` as a valid stage label;
- dependency-label construction returns the required semantic keys and status label;
- retrieval-quality span attributes are omitted when the owning stage receives no golden retrieval targets for the current request;
- retrieval-quality span attributes are emitted with the expected names and values on `retrieval.vector_search` when retrieval-stage metrics are available;
- retrieval-quality span attributes are emitted with the expected names and values on the reranking-owned span when reranking-stage metrics are available;
- OpenInference reranking span emits `reranking.total_tokens` when `RerankedRetrievalOutput.total_tokens = Some(...)`;
- OpenInference reranking span emits `reranking.total_cost_usd` when reranking token count is available and reranking cost is computable from transport settings;
- request-level retrieval aggregate attributes are emitted on `rag.request` only when both stage metric bundles are available;
- `StatusLabel` maps to the exact string values required by the observability contract.

4.9) `errors`
-------------

Generated unit tests for `errors` must include all of the following cases:

- `RagRuntimeError::startup(...)` returns the crate-level startup error variant;
- every `error_type()` method returns the exact stable string required by the error taxonomy for each error enum variant that exists in the generated code.

## 5) Minimum Executable Test Counts

Generated test code must satisfy all of the following minimum executable test counts in a normal local environment:

- `input_validation`: at least `12` executable tests;
- `retrieval`: at least `34` executable tests;
- `reranking`: at least `11` executable tests;
- `generation`: at least `20` executable tests;
- `orchestration`: at least `12` executable tests;
- `request_capture_store`: at least `11` executable tests;
- `config`: at least `11` executable tests;
- `lib`: at least `3` executable tests;
- `observability`: at least `12` executable tests;
- `errors`: at least `2` executable tests.

Executable test count rules:

- each `#[test]` or `#[tokio::test]` function that runs without `#[ignore]` counts as one executable test;
- a single executable test does not satisfy multiple separately listed required cases unless this document explicitly says that one test must cover multiple scenarios;
- the generated crate must contain enough non-ignored tests to satisfy these minimums in a normal local environment.

## 6) Coverage Tooling

Coverage measurement for `rag_runtime` must use `cargo-llvm-cov`.

Required installation commands:

```bash
rustup component add llvm-tools-preview
cargo install cargo-llvm-cov
```

Required coverage commands:

```bash
cd Execution/rag_runtime
cargo llvm-cov --package rag_runtime --tests
cargo llvm-cov --package rag_runtime --tests --html
```

The HTML report output path is:

- `Execution/rag_runtime/target/llvm-cov/html/index.html`

## 7) Coverage Interpretation Rules

Coverage interpretation must follow all of the following rules:

- line coverage is the acceptance metric;
- region coverage is recorded but does not replace line coverage acceptance;
- per-module line coverage thresholds take precedence over aggregate crate coverage;
- ignored tests do not count toward default coverage acceptance in a normal local environment that supports execution of the non-ignored test suite;
- `main.rs` is excluded from mandatory coverage acceptance;
- aggregate crate coverage is evaluated after excluding `main.rs` from acceptance judgment.
- coverage thresholds are required for a normal local environment with loopback socket support;
- if a restricted execution environment blocks required tests, the generator or validating agent must request the privileges needed to execute them and must still satisfy the required coverage thresholds.

## 8) Coverage Thresholds

Required minimum line coverage by module:

- `Execution/rag_runtime/src/input_validation/mod.rs >= 90%`
- `Execution/rag_runtime/src/retrieval/mod.rs >= 90%`
- `Execution/rag_runtime/src/reranking/mod.rs >= 90%`
- `Execution/rag_runtime/src/generation/mod.rs >= 90%`
- `Execution/rag_runtime/src/orchestration/mod.rs >= 90%`
- `Execution/rag_runtime/src/request_capture_store/mod.rs >= 85%`
- `Execution/rag_runtime/src/config/mod.rs >= 85%`
- `Execution/rag_runtime/src/lib.rs >= 85%`
- `Execution/rag_runtime/src/errors/mod.rs >= 85%`
- `Execution/rag_runtime/src/observability/mod.rs >= 60%`

Required aggregate line coverage for `rag_runtime`:

- total crate line coverage excluding `main.rs >= 90%`

Code generation for `rag_runtime` is incomplete if any required module threshold is not met or if the aggregate crate threshold excluding `main.rs` is not met in a normal local environment with loopback socket support.

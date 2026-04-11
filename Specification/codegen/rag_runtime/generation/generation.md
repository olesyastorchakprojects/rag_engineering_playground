# Generation Module

## 1) Purpose / Scope

`generation` builds a prompt from the user query and final reranked chunks and returns the model answer.

This module:
- receives `GenerationRequest`;
- builds the chat prompt;
- delegates the provider call to the configured `GenerationTransport`;
- validates the provider response and extracts the final answer;
- returns `GenerationResponse`.

This module does not:
- perform retrieval;
- perform reranking;
- select chunks;
- validate raw `UserRequest`;
- read ingest config directly;
- expose raw provider request or response objects at module boundary;
- select or construct the active transport implementation — transport selection is owned by the orchestrator.

## 2) Public Interface

```rust
pub struct Generator<T: GenerationTransport> {
    transport: T,
}

impl<T: GenerationTransport> Generator<T> {
    pub fn new(transport: T) -> Self;

    pub async fn generate(
        &self,
        request: GenerationRequest,
        settings: &GenerationSettings,
    ) -> Result<GenerationResponse, RagRuntimeError>;
}
```

`GenerationRequest`, `GenerationSettings`, and `GenerationResponse` are defined by the
crate-level contract in `rag_runtime.md`.

`GenerationTransport`, `ChatPrompt`, and `ModelAnswer` are defined in:

- `Specification/codegen/rag_runtime/generation/transport_integration.md`

Transport wire formats are defined in:

- `Specification/codegen/rag_runtime/generation/ollama_transport.md`
- `Specification/codegen/rag_runtime/generation/openai_transport.md`

The orchestrator instantiates the correct transport based on config and passes it to
`Generator::new`. `Generator` does not select or construct its own transport.

`Generator` may still inspect `settings.transport` by pattern-match for transport-dependent
metadata that remains generator-owned, such as observability attributes or request-capture-facing
effective configuration snapshots. This does not make `Generator` responsible for transport
selection or construction.

## 2.1) Internal Module Layout

The `generation` implementation must use an internal module layout under:

- `Execution/rag_runtime/src/generation/`

Required `generation` module layout:

- `Execution/rag_runtime/src/generation/mod.rs` — generator-facing module entrypoint; owns prompt assembly, token accounting, and the public `generation` module boundary;
- `Execution/rag_runtime/src/generation/transport.rs` — shared transport-facing types and helpers, including `GenerationTransport`, `ChatPrompt`, `ModelAnswer`, transport runtime inputs, and shared retry helpers;
- `Execution/rag_runtime/src/generation/ollama.rs` — `OllamaTransport` implementation;
- `Execution/rag_runtime/src/generation/openai.rs` — `OpenAiTransport` implementation;
- `Execution/rag_runtime/src/generation/tokenizer.rs` — generation tokenizer loading and token-counting helpers.

Layout rules:

- `generation` must not collapse generator logic, transport trait definitions, transport implementations, and tokenizer-loading helpers back into one large file;
- `mod.rs` remains the required `generation` module entrypoint and owns the public module boundary;
- `transport.rs`, `ollama.rs`, `openai.rs`, and `tokenizer.rs` are required internal decomposition files for the current version;
- transport selection ownership still belongs outside the `generation` module boundary even when transport-related helper functions live under `Execution/rag_runtime/src/generation/`.

## 3) Configuration Usage

`generation` must read only its own settings section:

- `Settings.generation`

`GenerationSettings` fields are defined in the crate-level `Settings` contract in `rag_runtime.md`.

For the current version, required `GenerationSettings` fields are:

- `transport: TransportSettings` — selects and carries config for `OllamaTransport` or `OpenAiTransport`
- `tokenizer_source`
- `retry`
- `temperature`
- `max_context_chunks`
- `max_prompt_tokens`

Transport-specific fields (`model_name`, `url`, `timeout_sec`, cost fields) are defined inside
`OllamaTransportSettings` and `OpenAiTransportSettings` per `transport_integration.md`.

The transport-specific settings must not duplicate shared generation settings such as:

- `retry`
- `temperature`
- `tokenizer_source`
- `max_context_chunks`
- `max_prompt_tokens`

The module must not:

- read raw TOML directly;
- read config maps directly;
- read settings that belong to retrieval or input validation;
- read ingest config directly inside the generation module.

Generation tokenizer rules:

- generation token accounting must use a Hugging Face compatible tokenizer loaded from
  tokenizer artifacts resolved from `GenerationSettings.tokenizer_source`;
- the preferred Rust implementation path is the `tokenizers` crate;
- for the current version, `GenerationSettings.tokenizer_source` must be a Hugging Face repo id;
- the implementation must resolve `GenerationSettings.tokenizer_source` to
  `https://huggingface.co/<tokenizer_source>/resolve/main/tokenizer.json`;
- generation tokenizer instances are runtime-owned initialized resources rather than raw config values;
- the module must not construct a generation tokenizer per request;
- the module uses a generation tokenizer instance that is created during runtime initialization
  and reused across requests handled by the same owning runtime component;
- failure to load generation tokenizer artifacts is a startup error, not a request-level
  generation error.

Token accounting rules:

- `ModelAnswer.prompt_tokens` and `ModelAnswer.completion_tokens` are `Option<usize>`;
- when both are `Some`, those values must be used directly as `prompt_tokens` and
  `completion_tokens` for the `GenerationResponse`;
- when either is `None`, the generation module must count tokens using the local generation
  tokenizer: prompt tokens from the assembled `ChatPrompt`, completion tokens from
  `ModelAnswer.content`;
- `GenerationResponse.total_tokens` must always equal `prompt_tokens + completion_tokens`.

## 4) Prompt Templates

- the machine-readable prompt template source of truth is
  `Specification/codegen/rag_runtime/prompts.json`;
- the generated implementation must read `prompt_template.id`, `prompt_template.version`,
  `system_prompt`, and `user_prompt` from `Specification/codegen/rag_runtime/prompts.json`
  during code generation;
- the system prompt from `Specification/codegen/rag_runtime/prompts.json` must be copied into
  the generated Rust code as a valid Rust string literal;
- the user prompt from `Specification/codegen/rag_runtime/prompts.json` must be copied into
  the generated Rust code as a valid Rust string literal;
- `prompt_template.id` and `prompt_template.version` are defined in
  `Specification/codegen/rag_runtime/prompts.json`;
- the generated code must not read prompt templates from files under `Specification/` at runtime;
- `system prompt` is the string built from the copied system prompt template;
- `user prompt` is the string built from the copied user prompt template after placeholder
  substitution.

## 5) Chunk Labels

- if `RetrievedChunk.chunk.page_start == RetrievedChunk.chunk.page_end`, the chunk label
  must be `[page <page_start>]`;
- if `RetrievedChunk.chunk.page_start != RetrievedChunk.chunk.page_end`, the chunk label
  must be `[pages <page_start>-<page_end>]`;

## 6) Chat Prompt Construction

Prompt construction rules (shared across all transports):

- `ChatPrompt.system` is the system prompt string built from the copied system prompt template;
- `ChatPrompt.user` is the user prompt string built after placeholder substitution;
- to build the user prompt:
  - replace `{{question}}` with `GenerationRequest.query`;
  - replace `{{context_chunks}}` with a string built from `GenerationRequest.chunks`;
- `GenerationRequest.chunks` must not be empty;
- `RetrievedChunk.chunk.text` must be used exactly as provided;
- chunk text must not be trimmed before prompt construction;
- after placeholder substitution, the resulting string is the user prompt;
- the string used to replace `{{context_chunks}}` must be built from chunk blocks in input order;
- generation input order is the final chunk order produced by the reranking stage or by
  `pass_through` reranking;
- each chunk block must be built exactly as `<chunk_label>\n<RetrievedChunk.chunk.text>`;
- `chunk_label` must be built according to section `5) Chunk Labels`;
- chunk blocks must be joined with exactly `"\n\n"`.

The assembled `system` and `user` strings are passed to the transport as `ChatPrompt`.

How the transport serializes these into its wire format is defined in the transport spec.

## 7) Generation Algorithm

For each request:

1. If `GenerationRequest.chunks` is empty, return `invalid generation input`.
2. If `GenerationRequest.chunks.len()` exceeds `GenerationSettings.max_context_chunks`,
   return an error.
3. Build `ChatPrompt` from system and user prompt strings.
4. Count prompt tokens for the fully assembled chat prompt using the generation tokenizer.
5. If prompt token count exceeds `GenerationSettings.max_prompt_tokens`, return generation
   error before sending the provider request.
6. Call `transport.complete(prompt, &settings.transport, GenerationTransportRuntime { retry: &settings.retry, temperature: settings.temperature })`.
7. Use `ModelAnswer.content` as the final answer.
8. Use token counts from `ModelAnswer` (see token accounting rules in § 3).
9. Return `GenerationResponse { answer, prompt_tokens, completion_tokens, total_tokens }`.

## 8) Error Model

The module must define:

- `GenerationError`

`GenerationError` must include module-specific variants for generation failures.

Required failure categories:

- invalid generation input;
- chunk limit exceeded;
- prompt token limit exceeded;
- request assembly failure;
- generation request failure;
- generation response validation failure;
- unexpected internal state.

Failure-domain rules:

- provider transport and response failures are generation failures;
- invalid provider response shape is a generation failure;
- module-level errors must preserve all available diagnostic information;
- module-level errors must be converted to `RagRuntimeError::Generation(...)` at module boundary.

## 9) Generation Retry Logic

Generation retry logic is required for the current version.

- retry is owned by the transport implementation, not by `Generator`;
- `GenerationSettings.retry` is passed through to the transport through `GenerationTransportRuntime`;
- retry execution must use `GenerationSettings.retry.max_attempts`;
- retry settings must be deserialized into typed Rust config structures;
- retry instrumentation must record retry attempts through the observability contract when
  one or more retries occur;
- if all retry attempts are exhausted, the transport must return a generation request failure;
- retry logic must not duplicate prompt assembly work per attempt.

## 10) Constraints / Non-Goals

This module must not:

- perform retrieval;
- perform reranking;
- choose top chunks by itself when more chunks were returned than allowed;
- reorder chunks received from orchestration;
- silently drop extra chunks beyond `max_context_chunks`;
- rewrite the validated user query semantically;
- mutate retrieved chunk text semantically before sending it to the model;
- expose raw provider requests or raw provider responses at module boundary;
- select which transport to use — this is owned by the orchestrator.

## 11) Unit Test Requirements

Required generated unit tests for `generation` are defined in:

- `Specification/codegen/rag_runtime/unit_tests.md`

Generation for `generation` is incomplete if any required unit test for this module from
`Specification/codegen/rag_runtime/unit_tests.md` is missing.

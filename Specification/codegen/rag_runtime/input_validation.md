## 1) Purpose / Scope

`input_validation` validates and normalizes incoming user requests before later pipeline stages run.

This module:
- receives `UserRequest`;
- validates the incoming query;
- normalizes the incoming query according to config;
- returns `ValidatedUserRequest`.

This module does not:
- perform retrieval;
- perform generation;
- rewrite the query semantically;
- call external services.

## 2) Public Interface

The module must expose an async interface.

Required public module interface:

```rust
pub struct InputValidator;

impl InputValidator {
    pub async fn validate(
        request: UserRequest,
        settings: &InputValidationSettings,
    ) -> Result<ValidatedUserRequest, RagRuntimeError>;
}
```

Interface rules:

- the interface must be async;
- the interface must consume `UserRequest`;
- the interface must receive `&InputValidationSettings` explicitly;
- the interface must return `ValidatedUserRequest` on success;
- the interface must return `RagRuntimeError` on failure;
- module-internal logic uses `InputValidationError` before conversion to `RagRuntimeError`.

## 3) Input And Output Types

Input types:

- `UserRequest`
- `InputValidationSettings`

Output types:

- `ValidatedUserRequest`

Type rules:

- `UserRequest` must follow the shared type contract defined in `rag_runtime.md`;
- `ValidatedUserRequest` must follow the shared type contract defined in `rag_runtime.md`;
- `InputValidationSettings` must be the typed settings section from `Settings.input_validation`.

## 4) Validation And Normalization Rules

The module must use the following settings:

- `max_query_tokens`
- `tokenizer_source`
- `reject_empty_query`
- `trim_whitespace`
- `collapse_internal_whitespace`

Normalization rules:

- if `trim_whitespace = true`, leading and trailing whitespace must be removed;
- if `collapse_internal_whitespace = true`, repeated internal whitespace must be collapsed to single spaces;
- normalization must be deterministic.

Validation rules:

- if `reject_empty_query = true`, empty query input must be rejected after enabled normalization steps are applied;
- token count must be computed on the normalized query;
- token counting must be aligned with the embedding model tokenizer;
- for the current version, the implementation must use a Hugging Face compatible tokenizer loaded from tokenizer artifacts resolved from `InputValidationSettings.tokenizer_source`;
- the preferred Rust implementation path is the `tokenizers` crate;
- for the current version, `tokenizer_source` must be a Hugging Face repo id;
- the implementation must resolve `tokenizer_source` to `https://huggingface.co/<tokenizer_source>/resolve/main/tokenizer.json`;
- tokenizer instances are runtime-owned initialized resources rather than raw config values;
- the module must not construct a tokenizer per request;
- the module uses a tokenizer instance that is created during runtime initialization and reused across requests handled by the same owning runtime component;
- failure to load tokenizer artifacts is a startup error, not a request-level validation error;
- if normalized query token count exceeds `max_query_tokens`, validation must fail;
- validation output must contain the normalized query string;
- validation output must contain the token count computed for the normalized query.

## 5) Error Model

The module must define:

- `InputValidationError`

`InputValidationError` must include module-specific variants for validation failures.

Required failure categories:

- empty query rejected;
- query token limit exceeded;
- token counting failure.

Error rules:

- module-level errors must preserve all available diagnostic information;
- module-level errors must be converted to `RagRuntimeError::InputValidation(...)` at module boundary.

## 6) Configuration Usage

`input_validation` must read only its own settings section:

- `Settings.input_validation`

The module must not:

- read raw TOML directly;
- read config maps directly;
- read settings that belong to retrieval or generation.

## 7) Algorithm

For each request:

1. Read `request.query`.
2. If `trim_whitespace = true`, trim leading and trailing whitespace.
3. If `collapse_internal_whitespace = true`, collapse repeated internal whitespace to single spaces.
4. If `reject_empty_query = true` and the normalized query is empty, return validation error.
5. Compute token count for the normalized query using the embedding-model-aligned tokenizer.
6. If token count exceeds `max_query_tokens`, return validation error.
7. Return `ValidatedUserRequest { query: normalized_query, input_token_count }`.

## 8) Constraints / Non-Goals

This module must not:

- perform semantic query rewriting;
- perform spelling correction;
- perform synonym expansion;
- attach retrieval metadata;
- call embedding services;
- call vector databases;
- call LLMs.

## 9) Unit Test Requirements

Required generated unit tests for `input_validation` are defined in:

- `Specification/codegen/rag_runtime/unit_tests.md`

Generation for `input_validation` is incomplete if any required unit test for this module from `Specification/codegen/rag_runtime/unit_tests.md` is missing.

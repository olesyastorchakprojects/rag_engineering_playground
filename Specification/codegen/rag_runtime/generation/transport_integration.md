# Generation Transport Integration

## 1) Shared Types

```rust
pub struct ChatPrompt {
    pub system: String,
    pub user: String,
}

pub struct ModelAnswer {
    pub content: String,
    pub prompt_tokens: Option<usize>,
    pub completion_tokens: Option<usize>,
}

pub struct GenerationTransportRuntime<'a> {
    pub retry: &'a RetrySettings,
    pub temperature: f32,
}
```

`prompt_tokens` and `completion_tokens` are `None` when the provider does not return usage counts.

## 2) Transport Trait

```rust
pub trait GenerationTransport: Send + Sync {
    async fn complete(
        &self,
        prompt: ChatPrompt,
        transport: &TransportSettings,
        runtime: GenerationTransportRuntime<'_>,
    ) -> Result<ModelAnswer, GenerationError>;
}
```

`GenerationTransport` must not receive the whole `GenerationSettings`.

- shared generation settings must not be duplicated into `OllamaTransportSettings` or `OpenAiTransportSettings`;
- the transport receives only:
  - `ChatPrompt`;
  - the active `TransportSettings` value;
  - the minimal shared runtime values it needs for request execution through `GenerationTransportRuntime`.

## 3) complete() Algorithm

Each transport implementation handles only its own `TransportSettings` variant. Receiving the wrong variant is `GenerationError::UnexpectedInternalState`.

**OllamaTransport:**

1. Match `transport` as `TransportSettings::Ollama(s)`; return `UnexpectedInternalState` if variant does not match.
2. Build the request body from `prompt`, `s.model_name`, and `runtime.temperature` per `ollama_transport.md`.
3. Execute the HTTP request to `s.url` with `s.timeout_sec` and retry per § 4 Retry rules.
4. Validate the response per `ollama_transport.md` Invalid Response rules.
5. Extract `content` from `message.content`; set `prompt_tokens = None`, `completion_tokens = None`.
6. Return `ModelAnswer { content, prompt_tokens, completion_tokens }`.

**OpenAiTransport:**

1. Match `transport` as `TransportSettings::OpenAi(s)`; return `UnexpectedInternalState` if variant does not match.
2. Build the request body from `prompt`, `s.model_name`, and `runtime.temperature` per `openai_transport.md`.
3. Execute the HTTP request to `s.url` with `Authorization: Bearer s.api_key`, `s.timeout_sec`, and retry per § 5 Retry rules.
4. Validate the response per `openai_transport.md` Invalid Response rules.
5. Extract `content` from `choices[0].message.content`; set `prompt_tokens = Some(usage.prompt_tokens)`, `completion_tokens = Some(usage.completion_tokens)`.
6. Return `ModelAnswer { content, prompt_tokens, completion_tokens }`.

## 4) OllamaTransport


Wire format: `Specification/codegen/rag_runtime/generation/ollama_transport.md`

### Configuration

`transport` matched as `TransportSettings::Ollama(s)`:

| Field                            | Value                              |
|----------------------------------|------------------------------------|
| `url`                            | `s.url`                            |
| `model_name`                     | `s.model_name`                     |
| `timeout_sec`                    | `s.timeout_sec`                    |
| `input_cost_per_million_tokens`  | `s.input_cost_per_million_tokens`  |
| `output_cost_per_million_tokens` | `s.output_cost_per_million_tokens` |

### Response Mapping

| `ModelAnswer` field | Source                             |
|---------------------|------------------------------------|
| `content`           | `message.content`                  |
| `prompt_tokens`     | `None` (API does not return usage) |
| `completion_tokens` | `None` (API does not return usage) |

### Retry

- must use `GenerationTransportRuntime.retry.max_attempts`
- must use the `backon` crate; custom retry implementations are forbidden
- backoff must be exponential with bounded jitter
- retry attempts must be recorded through the observability contract when one or more retries occur
- if all retry attempts are exhausted, return `GenerationError::GenerationRequestFailure`

### Error Mapping

| Condition                            | Error                                                  |
|--------------------------------------|--------------------------------------------------------|
| HTTP or network failure              | `GenerationError::GenerationRequestFailure`            |
| Non-2xx response                     | `GenerationError::GenerationRequestFailure`            |
| Response parse or validation failure | `GenerationError::GenerationResponseValidationFailure` |

## 5) OpenAiTransport

Wire format: `Specification/codegen/rag_runtime/generation/openai_transport.md`

### Configuration

`transport` matched as `TransportSettings::OpenAi(s)`:

| Field                            | Value                              |
|----------------------------------|------------------------------------|
| `url`                            | `s.url`                            |
| `api_key`                        | `s.api_key`                        |
| `model_name`                     | `s.model_name`                     |
| `timeout_sec`                    | `s.timeout_sec`                    |
| `input_cost_per_million_tokens`  | `s.input_cost_per_million_tokens`  |
| `output_cost_per_million_tokens` | `s.output_cost_per_million_tokens` |

### Response Mapping

| `ModelAnswer` field | Source                          |
|---------------------|---------------------------------|
| `content`           | `choices[0].message.content`    |
| `prompt_tokens`     | `Some(usage.prompt_tokens)`     |
| `completion_tokens` | `Some(usage.completion_tokens)` |

### Retry

- must use `GenerationTransportRuntime.retry.max_attempts`
- must use the `backon` crate; custom retry implementations are forbidden
- backoff must be exponential with bounded jitter
- retry attempts must be recorded through the observability contract when one or more retries occur
- if all retry attempts are exhausted, return `GenerationError::GenerationRequestFailure`

### Error Mapping

| Condition                            | Error                                                  |
|--------------------------------------|--------------------------------------------------------|
| HTTP or network failure              | `GenerationError::GenerationRequestFailure`            |
| Non-2xx response                     | `GenerationError::GenerationRequestFailure`            |
| Response parse or validation failure | `GenerationError::GenerationResponseValidationFailure` |

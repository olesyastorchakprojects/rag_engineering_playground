## 1) Purpose / Scope

This document defines the external HTTP API contract for the VoyageAI cross-encoder reranker transport used by `rag_runtime`.

It defines:
- request shape;
- successful response shape;
- response-to-candidate mapping rules;
- token-usage source.

This document does not define:
- orchestration-owned reranker selection;
- batching policy ownership;
- tokenizer-based token estimation;
- crate-level shared types.

Those concerns are defined in:
- `Specification/codegen/rag_runtime/reranking/cross_encoder.md`
- `Specification/codegen/rag_runtime/reranking/transport_integration.md`
- `Specification/codegen/rag_runtime/rag_runtime.md`

## 2) Rerank Endpoint

The service must expose:
- `POST /v1/rerank`

### 2.1) Request Shape

`rag_runtime` must send:

```json
{
  "model": "rerank-2.5",
  "query": "What is eventual consistency?",
  "documents": [
    "candidate chunk text 1",
    "candidate chunk text 2"
  ],
  "top_k": 2
}
```

Rules:
- `model` must be the configured VoyageAI reranker model name;
- `query` must be the validated user query for the current request;
- `documents` order must preserve the current batch candidate order;
- `top_k` must equal the number of items in `documents` so that the response covers the full batch;

### 2.2) Successful Response Shape

Successful response JSON:

```json
{
  "object": "list",
  "data": [
    {
      "relevance_score": 0.734375,
      "index": 1
    },
    {
      "relevance_score": 0.51171875,
      "index": 0
    }
  ],
  "model": "rerank-2.5",
  "usage": {
    "total_tokens": 4262
  }
}
```

Field semantics:
- `data`
  - ordered list sorted by descending relevance score
- `data[*].index`
  - zero-based index into the input `documents` array
- `data[*].relevance_score`
  - rerank score returned by the model
- `model`
  - provider-reported model identifier for the current call
- `usage.total_tokens`
  - provider-reported total token count for the current call

## 3) Response Mapping Rules

The runtime transport wrapper must:
- map response items back to input candidates by `data[*].index`;
- treat `data[*].index` as the source of truth for response-to-candidate identity;
- write `data[*].relevance_score` into the normalized transport score field;
- use provider response order as the reranked order for the current batch;
- use `usage.total_tokens` as the token-usage source for the current batch.

Validation rules:
- every returned `index` must be within input bounds;
- duplicate `index` values are invalid;
- every returned `relevance_score` must be finite;
- the response must cover every input candidate in the batch exactly once;
- `usage.total_tokens` must be a non-negative integer when present.

## 4) Failure Contract

The API-facing transport wrapper must fail for:
- non-2xx response from `POST /v1/rerank`;
- invalid JSON response;
- missing `data`;
- malformed `data[*].index`;
- malformed `data[*].relevance_score`;
- duplicate `data[*].index`;
- response coverage mismatch between input `documents` and response `data`;
- malformed `usage.total_tokens` when `usage` is present.

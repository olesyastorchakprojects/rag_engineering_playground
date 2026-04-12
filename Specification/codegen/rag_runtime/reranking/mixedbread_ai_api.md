## 1) Purpose / Scope

This document defines the external HTTP API contract for the cross-encoder reranker service used by `rag_runtime`.

It defines:
- readiness probing;
- request shape;
- successful response shape;
- response-to-candidate mapping rules.

This document does not define:
- orchestration-owned reranker selection;
- batching policy ownership;
- request-capture assembly;
- crate-level shared types.

Those concerns are defined in:
- `Specification/codegen/rag_runtime/reranking/cross_encoder.md`
- `Specification/codegen/rag_runtime/reranking/transport_integration.md`
- `Specification/codegen/rag_runtime/orchestration.md`
- `Specification/codegen/rag_runtime/rag_runtime.md`

## 2) Readiness Endpoint

The service must expose:
- `GET /health`

Successful health response shape:

```json
{
  "status": "ready",
  "model_id": "provider-reported-model-id"
}
```

Permitted health statuses for the current version:
- `warming`
- `ready`

Rules:
- `warming` means the service process is reachable but the model is not yet loaded into memory;
- `warming` is not a terminal failure state;
- `ready` means the service is ready for rerank inference;
- any non-2xx response is a readiness failure.

## 3) Rerank Endpoint

The service must expose:
- `POST /rerank`

Required execution rules:
- it may probe `GET /health` before sending rerank requests, but that is not required when the service is already reachable;
- if the service reports `warming`, the transport must treat that response as a retryable warmup signal rather than as a terminal readiness failure;
- after a `warming` readiness signal, the transport must still be allowed to send `POST /rerank` because the first successful rerank call may perform the actual lazy model load;
- the transport must not claim the service is `ready` solely from a `warming` response;
- after a `warming` readiness signal, the transport may treat a subsequent successful `POST /rerank` as sufficient proof that the service is operational for the current request.

### 3.1) Request Shape

`rag_runtime` must send:

```json
{
  "query": "What is eventual consistency?",
  "texts": [
    "candidate chunk text 1",
    "candidate chunk text 2"
  ]
}
```

Observed optional service fields:
- `top_n`
- `instruction`

Rules for `rag_runtime`:
- it must send only:
  - `query`
  - `texts`
- it must not send:
  - `top_n`
  - `instruction`
- `texts` order must preserve the current reranker-batch candidate order.

### 3.2) Successful Response Shape

Successful response JSON:

```json
{
  "model_id": "provider-reported-model-id",
  "results": [
    {
      "index": 0,
      "score": 0.5387439727783203,
      "text": "candidate chunk text 1",
      "rank": 1
    }
  ]
}
```

Field semantics:
- `model_id`
  - service-reported identifier of the active reranker model used for the current call
- `results`
  - ordered list sorted by descending model score
- `results[*].index`
  - zero-based index into the input `texts` array
- `results[*].score`
  - rerank score returned by the model
- `results[*].text`
  - echoed candidate text
- `results[*].rank`
  - one-based rank position in the response order
  - rank is informational only for the current runtime contract

Example only:
- a current local deployment may report `mixedbread-ai/mxbai-rerank-base-v2`
- that value is not fixed by this API contract

## 4) Response Mapping Rules

The runtime wrapper must:
- map response items back to input candidates by `results[*].index`;
- treat `results[*].index` as the source of truth for response-to-candidate identity;
- not rely on echoed `text` for identity;
- not rely on provider `rank` for identity, ordering, or sorting logic;
- preserve the original retrieval score from the matched candidate;
- write `results[*].score` into the normalized transport score field;
- use provider response order as the final cross-encoder order for the current batch.

Validation rules:
- every returned `index` must be within input bounds;
- duplicate `index` values are invalid;
- every returned `score` must be finite;
- the response must cover every input candidate in the batch exactly once.

## 5) Failure Contract

The API-facing runtime wrapper must fail for:
- non-2xx response from `POST /rerank`;
- invalid JSON response;
- missing `model_id`;
- missing `results`;
- malformed `results[*].index`;
- malformed `results[*].score`;
- duplicate `results[*].index`;
- response coverage mismatch between input `texts` and response `results`.

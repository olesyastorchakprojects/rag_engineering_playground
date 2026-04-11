========================
1) Purpose / Scope
========================

This document defines the Phoenix/OpenInference semantic metric contract for `rag_runtime`.

It defines:
- compact AI-semantic metrics derived from retrieval and generation execution;
- metric names, units, and record points for Phoenix/OpenInference-oriented inspection;
- low-cardinality label rules for those metrics.

This document does not define:
- the required base OTEL metric set from `metrics.md`;
- span classification rules;
- raw prompt or raw response capture;
- evaluation metrics.

This document is part of the required observability contract for `rag_runtime`.

========================
2) Metric Label Rules
========================

Phoenix/OpenInference semantic metrics are low-cardinality.

Allowed labels are fixed:
- `module`
- `stage`
- `retriever_kind`
- `provider`
- `model`

The following values must not be metric labels:
- request identifiers
- chunk identifiers
- page locators
- raw query text
- raw prompt text
- raw retrieved text
- raw response text
- error message text

========================
3) Semantic Metric Set
========================

The Phoenix/OpenInference semantic metric set is fixed:

`rag_retriever_result_count`
- type: histogram
- unit: retrieved_items
- labels:
  - `module`
  - `stage`
  - `retriever_kind`
- record point:
  - record once when `retrieval.vector_search` returns mapped retrieved chunks

`rag_retrieval_top1_score`
- type: histogram
- unit: score
- labels:
  - `module`
  - `stage`
  - `retriever_kind`
- value definition:
  - score of the first returned retrieval result in response order
- record point:
  - record once when at least one retrieval result is returned

`rag_retrieval_topk_mean_score`
- type: histogram
- unit: score
- labels:
  - `module`
  - `stage`
  - `retriever_kind`
- value definition:
  - arithmetic mean of retrieval scores across all returned retrieval results in response order
- record point:
  - record once when at least one retrieval result is returned

Zero-result rule for retrieval score metrics:

- if zero retrieval results are returned, `rag_retrieval_top1_score` must not be recorded;
- if zero retrieval results are returned, `rag_retrieval_topk_mean_score` must not be recorded.

`rag_llm_prompt_tokens`
- type: histogram
- unit: tokens
- labels:
  - `module`
  - `stage`
  - `provider`
  - `model`
- record point:
  - record once when prompt token count is computed

`rag_llm_completion_tokens`
- type: histogram
- unit: tokens
- labels:
  - `module`
  - `stage`
  - `provider`
  - `model`
- record point:
  - record once when completion token count is computed

`rag_llm_total_tokens`
- type: histogram
- unit: tokens
- labels:
  - `module`
  - `stage`
  - `provider`
  - `model`
- record point:
  - record once when total token count is computed

`rag_llm_cost_total`
- type: histogram
- unit: cost
- labels:
  - `module`
  - `stage`
  - `provider`
  - `model`
- record point:
  - record once when cost accounting is available

========================
4) Fixed Label Values
========================

For `generation.chat` semantic metrics:
- `module = generation`
- `stage = generation`
- `provider` comes from the same provider-classification rule as `generation.chat.llm.provider`
- `model` comes from the active transport settings model name

For `retrieval.vector_search` semantic metrics:
- `module = retrieval`
- `stage = retrieval`
- `retriever_kind = Settings.retrieval.kind`

========================
5) Emission Rules
========================

Phoenix/OpenInference semantic metrics are emitted through the same OTLP metric pipeline as the required base metrics.

Emission rules are fixed:

- semantic metrics must not replace required base metrics from `metrics.md`;
- semantic metrics extend the metric set with compact AI-specific numeric signals;
- unavailable token or cost values must not be synthesized.

========================
6) Safety Constraints
========================

Phoenix/OpenInference semantic metrics must not encode raw text or unbounded identifiers in labels or values.

The generated implementation must not derive semantic metrics from:
- raw prompt text bodies stored as labels;
- raw model outputs stored as labels;
- raw retrieved document bodies stored as labels.

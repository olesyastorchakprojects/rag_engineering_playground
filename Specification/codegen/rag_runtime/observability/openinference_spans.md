========================
1) Purpose / Scope
========================

This document defines the Phoenix/OpenInference span contract for `rag_runtime`.

It defines:
- OpenInference span classification;
- Phoenix-facing semantic span mapping;
- required semantic span attributes;
- compact retrieval and generation metadata placed on OpenInference spans;
- span events attached to semantic spans, including their names and required attributes;
- safety limits for Phoenix-visible semantic payload.

This document does not define:
- the mandatory OTEL span tree;
- generic stage-span ownership;
- generic OTEL metric definitions;
- evaluation workflows.

This document is part of the required observability contract for `rag_runtime`.

========================
2) OpenInference Model
========================

OpenInference spans exist inside the single OTEL trace emitted by `rag_runtime`.

OpenInference instrumentation does not create a second trace.

Phoenix-facing semantic classification is applied only to the specific spans defined in this document.

The semantic span set is fixed:
- `rag.request`
- `retrieval.embedding`
- `retrieval.search`
- `reranking.rank`
- `generation.chat`

No other span receives Phoenix/OpenInference semantic classification in the current increment.

Span events are first-class diagnostic artifacts attached to semantic spans via `span.add_event()`.

Span events do not create new OTEL spans.

The set of span events per semantic span is fixed and defined in the per-span contracts below.

========================
3) Semantic Span Kind Mapping
========================

Phoenix/OpenInference semantic span-kind mapping is fixed:

- `rag.request` -> `CHAIN`
- `retrieval.embedding` -> `EMBEDDING`
- `retrieval.search` -> `RETRIEVER`
- `reranking.rank` -> `RERANKER`
- `generation.chat` -> `LLM`

The generated implementation must not classify:
- `input_validation`
- `input_validation.normalize`
- `input_validation.token_count`
- `retrieval`
- `retrieval.payload_mapping`
- `generation`
- `generation.prompt_assembly`
- `generation.response_validation`

========================
4) Shared Semantic Attribute Rules
========================

Phoenix/OpenInference semantic attributes must satisfy all of the following rules:

- semantic attributes are attached only to the span that owns the described operation;
- semantic attributes must be compact;
- semantic attributes must be deterministic;
- semantic attributes must not duplicate raw prompt text;
- semantic attributes must not duplicate raw retrieved document text;
- semantic attributes must not contain secrets, API keys, authorization headers, or environment variable values.

`input.value` and `output.value` placement rules:

- `input.value` on `rag.request` contains the normalized user query; this supports chain-level Phoenix evaluators;
- `output.value` on `rag.request` contains the final validated assistant answer returned by `rag_runtime`; this supports chain-level Phoenix evaluators;
- `output.value` on `generation.chat` contains the final validated assistant answer returned by `rag_runtime`; this supports LLM-level Phoenix evaluators;
- `output.value` on `rag.request` and `output.value` on `generation.chat` must contain the same value;
- `input.value` and `output.value` must not be attached to any other span.

========================
5) `rag.request` Semantic Contract
========================

`rag.request` is the Phoenix/OpenInference chain span.

Required semantic attributes:

- `openinference.span.kind = "CHAIN"`
- `input.value`
  - source: `ValidatedUserRequest.query`
  - type: string
  - value: normalized user query
- `input.mime_type = "text/plain"`
- `output.value`
  - source: final validated generation response text
  - type: string
  - value: final assistant answer text returned by `rag_runtime`
- `output.mime_type = "text/plain"`
- `request.id`
  - source: orchestration-derived request UUID
  - type: string
- `app.version`
  - source: generated/runtime build metadata derived from `Execution/rag_runtime/Cargo.toml`
  - type: string
- `rag.pipeline.name = "rag_runtime"`
- `rag.pipeline.version`
  - source: `Settings.pipeline.config_version`
  - type: string
- `prompt_template.id`
  - source: generated prompt-template constant derived from `Specification/codegen/rag_runtime/prompts.json`
  - type: string
- `prompt_template.version`
  - source: generated prompt-template constant derived from `Specification/codegen/rag_runtime/prompts.json`
  - type: string
- `corpus.version`
  - source: `RetrievalSettings.ingest.corpus_version`
  - type: string
- `token_length_curve.retrieval`
  - source: orchestration-derived cumulative prompt token counts for each prefix of the retrieval candidate list
  - type: string; compact ordered list of integers
  - value: token count of the assembled chat prompt when context includes the first 1, 2, ..., N retrieval candidates in retrieval-rank order
- `token_length_curve.reranking`
  - source: orchestration-derived cumulative prompt token counts for each prefix of the reranked candidate list
  - type: string; compact ordered list of integers
  - value: token count of the assembled chat prompt when context includes the first 1, 2, ..., N reranked candidates in reranking-rank order

Conditional semantic attributes:

- `summary_retrieval_context_loss_soft`
  - source: orchestration-derived from `RetrievalOutput.metrics.recall_soft - RerankedRetrievalOutput.metrics.recall_soft`
  - type: number
  - emitted only when both retrieval-stage and reranking-stage metric bundles are available for the current request
- `summary_retrieval_context_loss_strict`
  - source: orchestration-derived from `RetrievalOutput.metrics.recall_strict - RerankedRetrievalOutput.metrics.recall_strict`
  - type: number
  - emitted only when both retrieval-stage and reranking-stage metric bundles are available for the current request
- `summary_first_relevant_rank_retrieval_soft`
  - source: `RetrievalOutput.metrics.first_relevant_rank_soft`
  - type: integer
  - emitted only when `RetrievalOutput.metrics.first_relevant_rank_soft = Some(...)` for the current request
- `summary_first_relevant_rank_retrieval_strict`
  - source: `RetrievalOutput.metrics.first_relevant_rank_strict`
  - type: integer
  - emitted only when `RetrievalOutput.metrics.first_relevant_rank_strict = Some(...)` for the current request
- `summary_first_relevant_rank_context_soft`
  - source: `RerankedRetrievalOutput.metrics.first_relevant_rank_soft`
  - type: integer
  - emitted only when `RerankedRetrievalOutput.metrics.first_relevant_rank_soft = Some(...)` for the current request
- `summary_first_relevant_rank_context_strict`
  - source: `RerankedRetrievalOutput.metrics.first_relevant_rank_strict`
  - type: integer
  - emitted only when `RerankedRetrievalOutput.metrics.first_relevant_rank_strict = Some(...)` for the current request
- `summary_num_relevant_in_retrieval_topk_soft`
  - source: `RetrievalOutput.metrics.num_relevant_soft`
  - type: integer
  - emitted only when the retrieval-stage metric bundle is available for the current request
- `summary_num_relevant_in_retrieval_topk_strict`
  - source: `RetrievalOutput.metrics.num_relevant_strict`
  - type: integer
  - emitted only when the retrieval-stage metric bundle is available for the current request
- `summary_num_relevant_in_context_topk_soft`
  - source: `RerankedRetrievalOutput.metrics.num_relevant_soft`
  - type: integer
  - emitted only when the reranking-stage metric bundle is available for the current request
- `summary_num_relevant_in_context_topk_strict`
  - source: `RerankedRetrievalOutput.metrics.num_relevant_strict`
  - type: integer
  - emitted only when the reranking-stage metric bundle is available for the current request

`rag.request` must not include:

- raw prompt text
- raw retrieved chunk text
- `llm.*` semantic attributes
- `retriever.*` semantic attributes
- `embedding.*` semantic attributes

Root span events:

The following events may be attached to `rag.request`. They are emitted only when the described condition occurs.

Event: `retrieval_quality_metrics`
- emitted when at least one of retrieval-stage or reranking-stage metric bundles is available for the current request
- attributes:
  - `summary_retrieval_context_loss_soft` — `RetrievalOutput.metrics.recall_soft - RerankedRetrievalOutput.metrics.recall_soft`; emitted only when both metric bundles are available
  - `summary_retrieval_context_loss_strict` — `RetrievalOutput.metrics.recall_strict - RerankedRetrievalOutput.metrics.recall_strict`; emitted only when both metric bundles are available
  - `summary_first_relevant_rank_retrieval_soft` — `RetrievalOutput.metrics.first_relevant_rank_soft`; `None` when not present
  - `summary_first_relevant_rank_retrieval_strict` — `RetrievalOutput.metrics.first_relevant_rank_strict`; `None` when not present
  - `summary_first_relevant_rank_context_soft` — `RerankedRetrievalOutput.metrics.first_relevant_rank_soft`; `None` when not present
  - `summary_first_relevant_rank_context_strict` — `RerankedRetrievalOutput.metrics.first_relevant_rank_strict`; `None` when not present
  - `summary_num_relevant_in_retrieval_topk_soft` — `RetrievalOutput.metrics.num_relevant_soft`; emitted only when retrieval metric bundle is available
  - `summary_num_relevant_in_retrieval_topk_strict` — `RetrievalOutput.metrics.num_relevant_strict`; emitted only when retrieval metric bundle is available
  - `summary_num_relevant_in_context_topk_soft` — `RerankedRetrievalOutput.metrics.num_relevant_soft`; emitted only when reranking metric bundle is available
  - `summary_num_relevant_in_context_topk_strict` — `RerankedRetrievalOutput.metrics.num_relevant_strict`; emitted only when reranking metric bundle is available

Event: `request_capture_persistence_failed`
- emitted when the request capture persistence step fails
- no required attributes; include available diagnostic context

Event: `request_failed`
- emitted when the request terminates with an unrecoverable error
- no required attributes; include available diagnostic context

Event: `request_completed_with_warning`
- emitted when the request completes but a non-fatal warning condition was detected
- no required attributes; include available diagnostic context

========================
6) `retrieval.embedding` Semantic Contract
========================

`retrieval.embedding` is the Phoenix/OpenInference embedding span.

Required semantic attributes:

- `openinference.span.kind = "EMBEDDING"`
- `input.value`
  - source: `ValidatedUserRequest.query`
  - type: string
  - value: normalized query after `input_validation`
- `input.mime_type = "text/plain"`
- `embedding.model_name`
  - source: `RetrievalSettings.ingest.embedding_model_name`
  - type: string
- `embedding.model_provider = "ollama"`
- `embedding.input.count = 1`
- `embedding.input_role = "query"`
- `embedding.vector_dim`
  - source: `RetrievalSettings.ingest.embedding_dimension`
  - type: integer

Forbidden semantic payload:

- raw pre-normalization `UserRequest.query`
- raw embedding vectors

Token-count ownership rule:

- token count of the normalized user query is emitted in the `input_validation.token_count` event on `retrieval.search`;
- `retrieval.embedding` must not duplicate that value as a semantic attribute.

Span events:

Event: `embedding_metadata`
- emitted at span start, before the provider request is made
- duplicates config-derived span attributes for easy event-level indexing
- required attributes:
  - `embedding.model_name` — source: `RetrievalSettings.ingest.embedding_model_name`
  - `embedding.model_provider = "ollama"`
  - `embedding.vector_dim` — source: `RetrievalSettings.ingest.embedding_dimension`

Event: `embedding_returned`
- emitted when the embedding response is successfully received
- required attributes:
  - `embedding.model_name` — model that produced the embedding
  - `embedding_length` — dimension of the returned embedding vector
  - `retry_attempt_count` — number of retry attempts before success; 0 if first attempt succeeded

========================
7) `retrieval.search` Semantic Contract
========================

`retrieval.search` is the Phoenix/OpenInference retriever span.

Required semantic attributes:

- `openinference.span.kind = "RETRIEVER"`
- `input.value`
  - source: `ValidatedUserRequest.query`
  - type: string
  - value: normalized query after `input_validation`
- `input.mime_type = "text/plain"`
- `retriever_system = "qdrant"`
- `retriever_strategy`
  - source: `RetrievalSettings.kind`
  - type: string
  - value: `dense | hybrid`
- `retriever_collection_name`
  - source: `RetrievalSettings.ingest.qdrant_collection_name`
  - type: string
- `retriever_top_k_requested`
  - source: `RetrievalSettings.top_k`
  - type: integer
- `retriever_top_k_returned`
  - source: number of returned retrieved chunks
  - type: integer
- `retriever_score_threshold`
  - source: `RetrievalSettings.score_threshold`
  - type: number
- `retriever_empty`
  - source: `retriever_top_k_returned == 0`
  - type: boolean
- `corpus.version`
  - source: `RetrievalSettings.ingest.corpus_version`
  - type: string

Conditional semantic attributes:

- when `RetrievalSettings.ingest = RetrievalIngest::Dense(DenseRetrievalIngest)`:
  - `retriever_vector_name`
    - source: `RetrievalSettings.ingest.qdrant_vector_name`
    - type: string

- when `RetrievalSettings.ingest = RetrievalIngest::Hybrid(HybridRetrievalIngest)`:
  - `retriever_dense_vector_name`
    - source: `RetrievalSettings.ingest.dense_vector_name`
    - type: string
  - `retriever_sparse_vector_name`
    - source: `RetrievalSettings.ingest.sparse_vector_name`
    - type: string
  - `retriever_fusion`
    - type: string
    - value: `rrf`
  - `retriever_sparse_strategy_kind`
    - source: `HybridRetrievalIngest.strategy`
    - type: string
    - value: `bag_of_words | bm25_like`
  - `retriever_sparse_strategy_version`
    - source: `HybridRetrievalIngest.strategy`
    - type: string

- when orchestration passes `Some(&GoldenRetrievalTargets)` for the current request:
  - `retrieval_recall_soft`
    - source: `RetrievalOutput.metrics.recall_soft`
    - type: number
  - `retrieval_recall_strict`
    - source: `RetrievalOutput.metrics.recall_strict`
    - type: number
  - `retrieval_rr_soft`
    - source: `RetrievalOutput.metrics.rr_soft`
    - type: number
  - `retrieval_rr_strict`
    - source: `RetrievalOutput.metrics.rr_strict`
    - type: number
  - `retrieval_ndcg`
    - source: `RetrievalOutput.metrics.ndcg`
    - type: number
  - `retrieval_first_relevant_rank_soft`
    - source: `RetrievalOutput.metrics.first_relevant_rank_soft`
    - type: integer
    - emitted only when `RetrievalOutput.metrics.first_relevant_rank_soft = Some(...)` for the current request
  - `retrieval_first_relevant_rank_strict`
    - source: `RetrievalOutput.metrics.first_relevant_rank_strict`
    - type: integer
    - emitted only when `RetrievalOutput.metrics.first_relevant_rank_strict = Some(...)` for the current request
  - `retrieval_num_relevant_soft`
    - source: `RetrievalOutput.metrics.num_relevant_soft`
    - type: integer
  - `retrieval_num_relevant_strict`
    - source: `RetrievalOutput.metrics.num_relevant_strict`
    - type: integer

Compact page-label format is fixed:
- if `page_start == page_end`, label format is `page:<page_start>`
- if `page_start != page_end`, label format is `pages:<page_start>-<page_end>`

Forbidden semantic payload:

- raw chunk text
- full serialized chunk JSON
- unbounded provider response bodies
- raw retrieval result arrays (chunk_ids, document_ids, locators, scores); these are emitted in the `vector_search_returned` event

Span events:

The following events are attached to `retrieval.search`.

Event: `retrieval_quality_metrics`
- emitted after quality metrics are computed, when orchestration passes `Some(&GoldenRetrievalTargets)` for the current request
- attributes:
  - `retrieval_recall_soft` — `RetrievalOutput.metrics.recall_soft`
  - `retrieval_recall_strict` — `RetrievalOutput.metrics.recall_strict`
  - `retrieval_rr_soft` — `RetrievalOutput.metrics.rr_soft`
  - `retrieval_rr_strict` — `RetrievalOutput.metrics.rr_strict`
  - `retrieval_ndcg` — `RetrievalOutput.metrics.ndcg`
  - `retrieval_first_relevant_rank_soft` — `RetrievalOutput.metrics.first_relevant_rank_soft`; `None` when not present
  - `retrieval_first_relevant_rank_strict` — `RetrievalOutput.metrics.first_relevant_rank_strict`; `None` when not present
  - `retrieval_num_relevant_soft` — `RetrievalOutput.metrics.num_relevant_soft`
  - `retrieval_num_relevant_strict` — `RetrievalOutput.metrics.num_relevant_strict`

The following five events are attached to `retrieval.search` in emission order.

---

Event 1: `input_validation.normalize`
- emitted after query normalization is applied
- required attributes:
  - `trim_whitespace` — boolean; whether leading/trailing whitespace was trimmed
  - `collapse_internal_whitespace` — boolean; whether internal whitespace sequences were collapsed
  - `normalized_query_length` — integer; character length of the normalized query

---

Event 2: `input_validation.token_count`
- emitted after the normalized query is tokenized
- required attributes:
  - `input_token_count` — integer; token count of the normalized query
- optional attributes:
  - `tokenizer_source` — string; tokenizer identifier, if available

---

Event 3: `retriever_metadata`
- emitted after `input_validation.token_count`, before the vector search HTTP call
- duplicates the config-derived flat span attributes for forensic convenience
- required attributes (dense):
  - `retriever_system` — `"qdrant"`
  - `retriever_strategy` — `"dense"`
  - `retriever_collection_name` — `RetrievalSettings.ingest.qdrant_collection_name`
  - `retriever_vector_name` — `RetrievalSettings.ingest.qdrant_vector_name`
  - `retriever_top_k_requested` — integer
  - `retriever_score_threshold` — number
- required attributes (hybrid, in addition to `retriever_system`, `retriever_strategy`, `retriever_collection_name`, `retriever_top_k_requested`, `retriever_score_threshold`):
  - `retriever_dense_vector_name` — `RetrievalSettings.ingest.dense_vector_name`
  - `retriever_sparse_vector_name` — `RetrievalSettings.ingest.sparse_vector_name`
  - `retriever_fusion` — `"rrf"`
  - `retriever_sparse_strategy_kind` — `HybridRetrievalIngest.strategy` kind
  - `retriever_sparse_strategy_version` — `HybridRetrievalIngest.strategy` version

---

Event 4: `vector_search_returned`
- emitted when the vector search response is successfully received
- contains the raw retrieval forensic payload
- required attributes:
  - `retrieval_results.scores` — ordered list of retrieval scores in returned-rank order
  - `retrieval_results.chunk_ids` — ordered list of `Chunk.chunk_id` values in returned-rank order
  - `retrieval_results.document_ids` — ordered list of `Chunk.doc_id` values in returned-rank order
  - `retrieval_results.locators` — ordered list of page labels in returned-rank order, using compact page-label format
  - `retry_attempt_count` — integer; number of retry attempts before success; 0 if first attempt succeeded

---

Event 5: `retrieval.payload_mapping`
- emitted after raw retriever payload is mapped to internal chunk representation
- required attributes:
  - `mapped_chunks` — integer; number of chunks successfully mapped
- optional attributes:
  - `mapping_strategy` — string; mapping strategy identifier, if available

========================
8) `reranking.rank` Semantic Contract
========================

`reranking.rank` is the Phoenix/OpenInference reranker span.

Required semantic attributes:

- `openinference.span.kind = "RERANKER"`
- `reranker_kind`
  - source: `Settings.reranking.reranker`
  - type: string
  - value: canonical reranker identifier for the current request, for example `PassThrough`, `Heuristic`, or `CrossEncoder`
- `reranker.final_k`
  - source: `RerankingSettings.final_k`
  - type: integer
- `reranker.retrieval_scores`
  - source: `RerankedRetrievalOutput.chunks[*].retrieval_score`
  - type: compact ordered list of numbers
  - ordering: preserves the exact candidate order emitted by the reranker for the current request
- `reranker.rerank_scores`
  - source: `RerankedRetrievalOutput.chunks[*].rerank_score`
  - type: compact ordered list of numbers
  - ordering: preserves the exact candidate order emitted by the reranker for the current request
- `reranker.result_indices`
  - source: reranker-emitted final order represented as zero-based indices into the original retrieval candidate order
  - type: compact ordered list of integers
  - ordering: preserves the exact candidate order emitted by the reranker for the current request
  - for `cross_encoder`, these values come directly from provider response `results[*].index`
  - for `pass_through` and `heuristic`, these values are derived locally from original retrieval positions
- `reranking.total_tokens`
  - source: `RerankedRetrievalOutput.total_tokens`
  - type: integer
  - emitted only when `RerankedRetrievalOutput.total_tokens = Some(...)` for the current request
- `reranking.total_cost_usd`
  - source: reranking-stage cost derived in observability code from `RerankedRetrievalOutput.total_tokens` and the active transport `cost_per_million_tokens`
  - type: number
  - emitted only when `RerankedRetrievalOutput.total_tokens = Some(...)` for the current request

Conditional semantic attributes:

- when orchestration passes `Some(&GoldenRetrievalTargets)` for the current request:
  - `context_recall_soft`
    - source: `RerankedRetrievalOutput.metrics.recall_soft`
    - type: number
  - `context_recall_strict`
    - source: `RerankedRetrievalOutput.metrics.recall_strict`
    - type: number
  - `context_rr_soft`
    - source: `RerankedRetrievalOutput.metrics.rr_soft`
    - type: number
  - `context_rr_strict`
    - source: `RerankedRetrievalOutput.metrics.rr_strict`
    - type: number
  - `context_ndcg`
    - source: `RerankedRetrievalOutput.metrics.ndcg`
    - type: number
  - `context_first_relevant_rank_soft`
    - source: `RerankedRetrievalOutput.metrics.first_relevant_rank_soft`
    - type: integer
    - emitted only when `RerankedRetrievalOutput.metrics.first_relevant_rank_soft = Some(...)` for the current request
  - `context_first_relevant_rank_strict`
    - source: `RerankedRetrievalOutput.metrics.first_relevant_rank_strict`
    - type: integer
    - emitted only when `RerankedRetrievalOutput.metrics.first_relevant_rank_strict = Some(...)` for the current request
  - `context_num_relevant_soft`
    - source: `RerankedRetrievalOutput.metrics.num_relevant_soft`
    - type: integer
  - `context_num_relevant_strict`
    - source: `RerankedRetrievalOutput.metrics.num_relevant_strict`
    - type: integer

Forbidden semantic payload:

- raw query text
- raw retrieved chunk text
- reranker input document payloads
- reranker output document payloads

Span events:

Event: `reranker_quality_metrics`
- emitted after quality metrics are computed, when orchestration passes `Some(&GoldenRetrievalTargets)` for the current request
- attributes:
  - `context_recall_soft` — `RerankedRetrievalOutput.metrics.recall_soft`
  - `context_recall_strict` — `RerankedRetrievalOutput.metrics.recall_strict`
  - `context_rr_soft` — `RerankedRetrievalOutput.metrics.rr_soft`
  - `context_rr_strict` — `RerankedRetrievalOutput.metrics.rr_strict`
  - `context_ndcg` — `RerankedRetrievalOutput.metrics.ndcg`
  - `context_first_relevant_rank_soft` — `RerankedRetrievalOutput.metrics.first_relevant_rank_soft`; `None` when not present
  - `context_first_relevant_rank_strict` — `RerankedRetrievalOutput.metrics.first_relevant_rank_strict`; `None` when not present
  - `context_num_relevant_soft` — `RerankedRetrievalOutput.metrics.num_relevant_soft`
  - `context_num_relevant_strict` — `RerankedRetrievalOutput.metrics.num_relevant_strict`

Event: `reranking.completed`
- optional; emitted when the reranking step completes successfully
- no required attributes; include available diagnostic context when emitted

========================
9) `generation.chat` Semantic Contract
========================

`generation.chat` is the Phoenix/OpenInference LLM span.

Required semantic attributes:

- `openinference.span.kind = "LLM"`
- `llm.system`
  - source: active generation transport classification
  - type: string
- `llm.provider`
  - source: active generation transport provider classification
  - type: string
- `llm.model.name`
  - source: active transport settings model name
  - type: string
- `llm.invocation.temperature`
  - source: `GenerationSettings.temperature`
  - type: number
- `llm.input_messages.count = 2`
- `llm.input_messages.roles`
  - value: compact ordered list `["system", "user"]`
- `llm.output_messages.count = 1`
- `llm.prompt.template.id`
  - source: generated prompt-template constant derived from `Specification/codegen/rag_runtime/prompts.json`
  - type: string
- `llm.prompt.template.version`
  - source: generated prompt-template constant derived from `Specification/codegen/rag_runtime/prompts.json`
  - type: string
- `output.value`
  - source: final validated generation response text
  - type: string
  - value: final assistant answer text returned by `rag_runtime`
- `output.mime_type = "text/plain"`
- `llm.token_count.prompt`
  - source: token count of the fully assembled chat prompt
  - type: integer
- `llm.token_count.completion`
  - source: token count of the final `message.content`
  - type: integer
- `llm.token_count.total`
  - source: `llm.token_count.prompt + llm.token_count.completion`
  - type: integer
- `llm.cost.prompt`
  - source: `llm.token_count.prompt * input_cost_per_million_tokens / 1_000_000`
  - type: number
  - unit: USD
- `llm.cost.completion`
  - source: `llm.token_count.completion * output_cost_per_million_tokens / 1_000_000`
  - type: number
  - unit: USD
- `llm.cost.total`
  - source: `llm.cost.prompt + llm.cost.completion`
  - type: number
  - unit: USD

Provider classification rules:

- when `Settings.generation.transport = TransportSettings::Ollama(_)`:
  - `llm.system = "ollama"`
  - `llm.provider = "ollama"`
- when `Settings.generation.transport = TransportSettings::OpenAi(s)` and `s.url` points to Together AI:
  - `llm.system = "openai"`
  - `llm.provider = "together"`
- when `Settings.generation.transport = TransportSettings::OpenAi(s)` and no better provider-specific mapping is available:
  - `llm.system = "openai"`
  - `llm.provider = "openai"`

Forbidden semantic payload:

- raw prompt text
- raw provider response bodies
- intermediate or unvalidated model response text
- raw model response text on any span other than `generation.chat.output.value`
- unbounded provider response bodies

Span events:

The following three events are attached to `generation.chat` in emission order.

---

Event 1: `generation.prompt_assembly`
- emitted after the chat prompt is fully assembled and token-counted
- required attributes:
  - `tokenizer_source` — string; tokenizer identifier used for token counting
  - `max_context_chunks` — integer; maximum number of context chunks allowed by settings
  - `max_prompt_tokens` — integer; token budget from `GenerationSettings.max_prompt_tokens`
  - `input_chunk_count` — integer; number of context chunks included in the assembled prompt
  - `prompt_length` — integer; character length of the assembled prompt
  - `prompt_token_count` — integer; token count of the assembled prompt

---

Event 2: `generation.response_returned`
- emitted when the provider response is successfully received
- required attributes:
  - `model_name` — string; model identifier from the provider response
  - `temperature` — number; temperature value used for the request
  - `http_status_code` — integer; HTTP status code of the provider response
  - `prompt_token_count` — integer; prompt token count as reported by the provider
  - `prompt_length` — integer; character length of the prompt sent to the provider
  - `request_body_length` — integer; byte length of the serialized request body
  - `retry_attempt_count` — integer; number of retry attempts before success; 0 if first attempt succeeded

---

Event 3: `generation.response_validation`
- emitted after internal validation of the provider response is complete
- required attributes:
  - `answer_present` — boolean; whether a non-empty answer was extracted from the response
  - `answer_length` — integer; character length of the extracted answer
  - `completion_token_count` — integer; token count of the completion as reported by the provider
  - `total_token_count` — integer; total token count as reported by the provider

========================
10) Safety And Size Constraints
========================

Phoenix/OpenInference semantic payload must remain compact.

The generated implementation must enforce all of the following limits:

- retrieval result identifiers are emitted only in the `vector_search_returned` event, not as span attributes;
- retrieval locators are emitted only in the `vector_search_returned` event, not as span attributes;
- no semantic attribute value contains full chunk text;
- no semantic attribute value contains full prompt text;
- no semantic attribute value contains full answer text, except for the required `output.value` attribute on `rag.request` and `generation.chat`.

========================
11) Error And Early-Termination Rules
========================

Phoenix/OpenInference spans must preserve both:
- semantic attributes that are already known at the failure point;
- correct error status on the span that owns the failure.

Rules:

- if a span ends with a failure in its own failure domain, that span must be marked with `status = "error"`;
- if a span completes successfully and a later span fails, the earlier successful span must remain `status = "ok"`;
- semantic attributes whose values are already known before the failure point must still be emitted on the owning span;
- semantic attributes whose values are not computed because execution terminated early must be omitted;
- retrieval-quality semantic attributes derived from `GoldenRetrievalTargets` must be emitted only when the owning module received `Some(&GoldenRetrievalTargets)` for the current request;
- placeholder or invented fallback values are forbidden;
- terminal request failure on `rag.request` must not rewrite already completed successful child spans into error spans.

Empty retrieval-output rule:

- if vector search returns zero mapped chunks, `retrieval.search` remains `status = "ok"`;
- `retriever_top_k_returned = 0` must be emitted on the span;
- `retriever_empty = true` must be emitted on the span;
- the `vector_search_returned` event must be emitted with all four result arrays empty (`scores`, `chunk_ids`, `document_ids`, `locators`);
- `rag.request` must be marked `status = "error"` when orchestration terminates the request because retrieval output is empty.

Dependency-failure rule:

- if embedding request execution fails, `retrieval.embedding` must be marked `status = "error"`;
- if vector-search request execution fails, `retrieval.search` must be marked `status = "error"`;
- if reranking execution fails, `reranking.rank` must be marked `status = "error"`;
- if generation provider request execution fails, `generation.chat` must be marked `status = "error"`;
- config-derived semantic attributes already known on those spans must still be emitted.

Prompt-token-limit rule:

- if prompt token count exceeds `GenerationSettings.max_prompt_tokens`:
  - the `generation.prompt_assembly` event must be emitted on `generation.chat` with all known attributes including `prompt_token_count`;
  - `generation.chat` must not be created when execution terminates before provider request execution starts;
  - `rag.request` must be marked `status = "error"`.

Response-validation rule:

- if provider request succeeds but response validation fails:
  - `generation.chat` remains `status = "ok"` when the transport/request execution completed successfully;
  - the `generation.response_validation` event must be emitted with `answer_present = false` and all other known attributes;
  - `rag.request` must be marked `status = "error"`.

========================
12) Ownership Rules
========================

Ownership of Phoenix/OpenInference semantics is fixed:

- `orchestration` owns `rag.request` semantic classification;
- `retrieval` owns `retrieval.embedding` semantic classification;
- `retrieval` owns `retrieval.search` semantic classification;
- `reranking` owns `reranking.rank` semantic classification;
- `generation` owns `generation.chat` semantic classification.

A module must not attach Phoenix/OpenInference semantic attributes to a span owned by another module.

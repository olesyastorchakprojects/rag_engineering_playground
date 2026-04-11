========================
1) Purpose / Scope
========================

This document defines the span contract for `rag_runtime`.

It defines:
- root span contract;
- stage hierarchy;
- span ownership;
- span scope boundaries;
- required span attributes;
- OpenInference usage.

========================
2) Root Span Contract
========================

Each request trace contains exactly one root span.

The root span name is:
- `rag.request`

`rag.request` rules:
- it is created at the beginning of orchestration request handling;
- it is the ancestor of every other span in the request trace;
- it closes only after final success or terminal failure;
- it records the final request status;
- it remains present in partial and failed traces.

========================
3) Attribute Naming Rules
========================

Attribute names in this document are local to the span that owns them.

Rules:
- attribute names in this document do not repeat the span name prefix;
- shared attributes keep their full names:
  - `span.module`
  - `span.stage`
  - `status`
  - `error.type`
  - `error.message`
- all other attributes are interpreted in the scope of the span section that defines them.

========================
4) Mandatory Stage Hierarchy
========================

Each successful full request trace contains the following stage hierarchy:

- `rag.request`
- `input_validation`
- `retrieval`
- `reranking`
- `generation`

Required child spans:

Inside `input_validation`:
- `input_validation.normalize`
- `input_validation.token_count`

Inside `retrieval`:
- `retrieval.embedding`
- `retrieval.vector_search`
- `retrieval.payload_mapping`

Inside `reranking`:
- `reranking.rank`

Inside `generation`:
- `generation.prompt_assembly`
- `generation.chat`
- `generation.response_validation`

Hierarchy rules:
- every listed span is a descendant of `rag.request`;
- dependency spans are nested inside the stage that owns the dependency call;
- sibling spans are not used to represent parent-child execution;
- duplicate spans for the same action are forbidden.

========================
5) Span Ownership
========================

Span ownership is fixed by module:

- `rag.request` belongs to `orchestration`;
- `input_validation` and `input_validation.*` belong to `input_validation`;
- `retrieval` and `retrieval.*` belong to `retrieval`;
- `reranking` and `reranking.*` belong to `reranking`;
- `generation` and `generation.*` belong to `generation`.

Ownership rules:
- a module creates only its own spans;
- a module does not create spans for another module;
- cross-module telemetry side effects are forbidden.

========================
6) Required Attributes For Mandatory Spans
========================

Every mandatory span listed in sections `2) Root Span Contract` and `4) Mandatory Stage Hierarchy` contains:
- `span.module`;
- `span.stage`;
- `status`.

If a mandatory span ends with an error, it also contains:
- `error.type`;
- `error.message`.

Allowed `status` values are fixed:
- `ok`;
- `error`.

========================
7) Emitted Event Rules
========================

If a span section defines a success event and an error event, those events are mutually exclusive.

Rules:
- one span execution emits either the success event or the error event;
- one span execution must not emit both events from the same success/error pair;
- if the span ends with `status = "ok"`, it emits the success event;
- if the span ends with `status = "error"`, it emits the error event.

========================
8) Detailed Span Contracts
========================

`rag.request`

- begins:
  - before orchestration starts handling one `UserRequest`
- ends:
  - after final `UserResponse` is returned or terminal failure is returned
- includes:
  - complete request handling for `input_validation`, `retrieval`, `reranking`, and `generation`
- required attributes:
  - `request_id`
    - type: string
    - source: orchestration-derived
    - value: request UUID v4
  - `span.module`
    - type: string
    - source: constant
    - value: `orchestration`
  - `span.stage`
    - type: string
    - source: constant
    - value: `request`
  - `status`
    - type: string
    - source: result-derived
    - value: `ok | error`
- conditional attributes:
  - `retrieval_context_loss_soft`
    - type: number
    - source: orchestration-derived from `RetrievalOutput.metrics.recall_soft - RerankedRetrievalOutput.metrics.recall_soft`
    - emitted only when both retrieval-stage and reranking-stage metric bundles are available for the current request
  - `retrieval_context_loss_strict`
    - type: number
    - source: orchestration-derived from `RetrievalOutput.metrics.recall_strict - RerankedRetrievalOutput.metrics.recall_strict`
    - emitted only when both retrieval-stage and reranking-stage metric bundles are available for the current request
  - `first_relevant_rank_retrieval_soft`
    - type: integer
    - source: `RetrievalOutput.metrics.first_relevant_rank_soft`
    - emitted only when `RetrievalOutput.metrics.first_relevant_rank_soft = Some(...)` for the current request
  - `first_relevant_rank_retrieval_strict`
    - type: integer
    - source: `RetrievalOutput.metrics.first_relevant_rank_strict`
    - emitted only when `RetrievalOutput.metrics.first_relevant_rank_strict = Some(...)` for the current request
  - `first_relevant_rank_context_soft`
    - type: integer
    - source: `RerankedRetrievalOutput.metrics.first_relevant_rank_soft`
    - emitted only when `RerankedRetrievalOutput.metrics.first_relevant_rank_soft = Some(...)` for the current request
  - `first_relevant_rank_context_strict`
    - type: integer
    - source: `RerankedRetrievalOutput.metrics.first_relevant_rank_strict`
    - emitted only when `RerankedRetrievalOutput.metrics.first_relevant_rank_strict = Some(...)` for the current request
  - `num_relevant_in_retrieval_topk_soft`
    - type: integer
    - source: `RetrievalOutput.metrics.num_relevant_soft`
    - emitted only when the retrieval-stage metric bundle is available for the current request
  - `num_relevant_in_retrieval_topk_strict`
    - type: integer
    - source: `RetrievalOutput.metrics.num_relevant_strict`
    - emitted only when the retrieval-stage metric bundle is available for the current request
  - `num_relevant_in_context_topk_soft`
    - type: integer
    - source: `RerankedRetrievalOutput.metrics.num_relevant_soft`
    - emitted only when the reranking-stage metric bundle is available for the current request
  - `num_relevant_in_context_topk_strict`
    - type: integer
    - source: `RerankedRetrievalOutput.metrics.num_relevant_strict`
    - emitted only when the reranking-stage metric bundle is available for the current request

`request_id` rules:
- `request_id` is required only on `rag.request`;
- child spans do not duplicate `request_id`;
- `request_id` is the only high-cardinality root-span attribute indexed through Tempo dedicated columns in the current contract.

`input_validation`

- begins:
  - before `input_validation` module execution starts
- ends:
  - after `input_validation` returns success or failure
- includes:
  - `input_validation.normalize`
  - `input_validation.token_count`

`input_validation.normalize`

- begins:
  - before query normalization starts
- ends:
  - after query normalization completes
- includes:
  - trim logic
  - internal whitespace collapse logic
- emitted events:
  - `query_normalized`
    - payload:
      - `trim_whitespace`
        - type: boolean
        - source: config-derived
        - value: `Settings.input_validation.trim_whitespace`
      - `collapse_internal_whitespace`
        - type: boolean
        - source: config-derived
        - value: `Settings.input_validation.collapse_internal_whitespace`
      - `normalized_query_length`
        - type: integer
        - source: runtime-derived
        - value: character length of normalized query
  - `query_normalization_failed`
    - payload:
      - `error.type`
        - type: string
        - source: error-derived
        - value: normalization failure category
      - `error.message`
        - type: string
        - source: error-derived
        - value: normalization failure detail

`input_validation.token_count`

- begins:
  - before token counting of the normalized query starts
- ends:
  - after token counting completes or token counting fails
- includes:
  - tokenizer invocation
  - token count extraction
- required attributes:
  - `input_token_count`
    - type: integer
    - source: runtime-derived
    - value: computed token count for normalized query
- emitted events:
  - `query_token_count_failed`
    - payload:
      - `tokenizer_source`
        - type: string
        - source: config-derived
        - value: `Settings.input_validation.tokenizer_source`
      - `max_query_tokens`
        - type: integer
        - source: config-derived
        - value: `Settings.input_validation.max_query_tokens`
      - `error.type`
        - type: string
        - source: error-derived
        - value: token counting failure category
      - `error.message`
        - type: string
        - source: error-derived
        - value: token counting failure detail

`retrieval`

- begins:
  - before `retrieval` module execution starts
- ends:
  - after `retrieval` returns success or failure
- includes:
  - `retrieval.embedding`
  - `retrieval.vector_search`
  - `retrieval.payload_mapping`

`retrieval.embedding`

- begins:
  - before embedding generation starts
- ends:
  - after embedding generation completes or fails
- includes:
  - embedding provider request
  - embedding response handling
- emitted events:
  - `embedding_returned`
    - payload:
      - `embedding_model_name`
        - type: string
        - source: config-derived
        - value: `Settings.retrieval.ingest.embedding_model_name`
      - `embedding_length`
        - type: integer
        - source: result-derived
        - value: returned embedding length
      - `retry_attempt_count`
        - type: integer
        - source: runtime-derived
        - value: number of retry attempts performed before success
  - `embedding_failed`
    - payload:
      - `embedding_model_name`
        - type: string
        - source: config-derived
        - value: `Settings.retrieval.ingest.embedding_model_name`
      - `retry_attempt_count`
        - type: integer
        - source: runtime-derived
        - value: number of retry attempts performed before failure
      - `expected_dimension`
        - type: integer
        - source: config-derived
        - value: `Settings.retrieval.ingest.embedding_dimension`
      - `actual_dimension`
        - type: integer
        - source: result-derived
        - value: returned embedding length when available
      - `error.type`
        - type: string
        - source: error-derived
        - value: embedding failure category
      - `error.message`
        - type: string
        - source: error-derived
        - value: embedding failure detail

`retrieval.vector_search`

- begins:
  - before vector search starts
- ends:
  - after vector search completes or fails
- includes:
  - Qdrant request
  - Qdrant response handling
- required attributes:
  - `top_k`
    - type: integer
    - source: config-derived
    - value: `Settings.retrieval.top_k`
- conditional attributes:
  - `recall_soft`
    - type: number
    - source: `RetrievalOutput.metrics.recall_soft`
    - emitted only when orchestration passes `Some(&GoldenRetrievalTargets)` for the current request
  - `recall_strict`
    - type: number
    - source: `RetrievalOutput.metrics.recall_strict`
    - emitted only when orchestration passes `Some(&GoldenRetrievalTargets)` for the current request
  - `rr_soft`
    - type: number
    - source: `RetrievalOutput.metrics.rr_soft`
    - emitted only when orchestration passes `Some(&GoldenRetrievalTargets)` for the current request
  - `rr_strict`
    - type: number
    - source: `RetrievalOutput.metrics.rr_strict`
    - emitted only when orchestration passes `Some(&GoldenRetrievalTargets)` for the current request
  - `ndcg`
    - type: number
    - source: `RetrievalOutput.metrics.ndcg`
    - emitted only when orchestration passes `Some(&GoldenRetrievalTargets)` for the current request
  - `first_relevant_rank_soft`
    - type: integer
    - source: `RetrievalOutput.metrics.first_relevant_rank_soft`
    - emitted only when `RetrievalOutput.metrics.first_relevant_rank_soft = Some(...)` for the current request
  - `first_relevant_rank_strict`
    - type: integer
    - source: `RetrievalOutput.metrics.first_relevant_rank_strict`
    - emitted only when `RetrievalOutput.metrics.first_relevant_rank_strict = Some(...)` for the current request
  - `num_relevant_soft`
    - type: integer
    - source: `RetrievalOutput.metrics.num_relevant_soft`
    - emitted only when orchestration passes `Some(&GoldenRetrievalTargets)` for the current request
  - `num_relevant_strict`
    - type: integer
    - source: `RetrievalOutput.metrics.num_relevant_strict`
    - emitted only when orchestration passes `Some(&GoldenRetrievalTargets)` for the current request
- emitted events:
  - `vector_search_returned`
    - payload:
      - `retrieval_kind`
        - type: string
        - source: config-derived
        - value: `Settings.retrieval.kind`
      - `collection_name`
        - type: string
        - source: config-derived
        - value: `Settings.retrieval.ingest.qdrant_collection_name`
      - `top_k`
        - type: integer
        - source: config-derived
        - value: `Settings.retrieval.top_k`
      - `score_threshold`
        - type: number
        - source: config-derived
        - value: `Settings.retrieval.score_threshold`
      - `http_status_code`
        - type: integer
        - source: result-derived
        - value: HTTP status code returned by Qdrant
      - `returned_chunks`
        - type: integer
        - source: result-derived
        - value: number of chunks returned by vector search
      - `scores`
        - type: array<number>
        - source: result-derived
        - value: ordered list of scores returned by vector search for the returned chunks
      - `vector_name`
        - type: string
        - source: config-derived
        - value: `Settings.retrieval.ingest.qdrant_vector_name`
        - emitted only when `Settings.retrieval.ingest = RetrievalIngest::Dense(DenseRetrievalIngest)`
      - `dense_vector_name`
        - type: string
        - source: config-derived
        - value: `Settings.retrieval.ingest.dense_vector_name`
        - emitted only when `Settings.retrieval.ingest = RetrievalIngest::Hybrid(HybridRetrievalIngest)`
      - `sparse_vector_name`
        - type: string
        - source: config-derived
        - value: `Settings.retrieval.ingest.sparse_vector_name`
        - emitted only when `Settings.retrieval.ingest = RetrievalIngest::Hybrid(HybridRetrievalIngest)`
      - `fusion_method`
        - type: string
        - source: constant
        - value: `rrf`
        - emitted only when `Settings.retrieval.ingest = RetrievalIngest::Hybrid(HybridRetrievalIngest)`
      - `sparse_strategy_kind`
        - type: string
        - source: config-derived
        - value: `Settings.retrieval.ingest.strategy.kind`
        - emitted only when `Settings.retrieval.ingest = RetrievalIngest::Hybrid(HybridRetrievalIngest)`
  - `vector_search_failed`
    - payload:
      - `retrieval_kind`
        - type: string
        - source: config-derived
        - value: `Settings.retrieval.kind`
      - `collection_name`
        - type: string
        - source: config-derived
        - value: `Settings.retrieval.ingest.qdrant_collection_name`
      - `top_k`
        - type: integer
        - source: config-derived
        - value: `Settings.retrieval.top_k`
      - `score_threshold`
        - type: number
        - source: config-derived
        - value: `Settings.retrieval.score_threshold`
      - `http_status_code`
        - type: integer
        - source: result-derived
        - value: HTTP status code returned by Qdrant when available
      - `retry_attempt_count`
        - type: integer
        - source: runtime-derived
        - value: number of retry attempts performed before failure
      - `error.type`
        - type: string
        - source: error-derived
        - value: vector search failure category
      - `error.message`
        - type: string
        - source: error-derived
        - value: vector search failure detail
      - `vector_name`
        - type: string
        - source: config-derived
        - value: `Settings.retrieval.ingest.qdrant_vector_name`
        - emitted only when `Settings.retrieval.ingest = RetrievalIngest::Dense(DenseRetrievalIngest)`
      - `dense_vector_name`
        - type: string
        - source: config-derived
        - value: `Settings.retrieval.ingest.dense_vector_name`
        - emitted only when `Settings.retrieval.ingest = RetrievalIngest::Hybrid(HybridRetrievalIngest)`
      - `sparse_vector_name`
        - type: string
        - source: config-derived
        - value: `Settings.retrieval.ingest.sparse_vector_name`
        - emitted only when `Settings.retrieval.ingest = RetrievalIngest::Hybrid(HybridRetrievalIngest)`
      - `fusion_method`
        - type: string
        - source: constant
        - value: `rrf`
        - emitted only when `Settings.retrieval.ingest = RetrievalIngest::Hybrid(HybridRetrievalIngest)`
      - `sparse_strategy_kind`
        - type: string
        - source: config-derived
        - value: `Settings.retrieval.ingest.strategy.kind`
        - emitted only when `Settings.retrieval.ingest = RetrievalIngest::Hybrid(HybridRetrievalIngest)`

`retrieval.payload_mapping`

- begins:
  - before mapping raw retrieval payloads into retrieval output chunks
- ends:
  - after all returned payloads are mapped or mapping fails
- includes:
  - payload validation
  - payload-to-domain mapping
- emitted events:
  - `payloads_mapped`
    - payload:
      - `mapped_chunks`
        - type: integer
        - source: result-derived
        - value: number of mapped chunks
  - `payload_mapping_failed`
    - payload:
      - `mapped_chunks_before_failure`
        - type: integer
        - source: result-derived
        - value: number of chunks mapped before failure
      - `error.type`
        - type: string
        - source: error-derived
        - value: payload mapping failure category
      - `error.message`
        - type: string
        - source: error-derived
        - value: payload mapping failure detail

`reranking`

- begins:
  - before `reranking` module execution starts
- ends:
  - after `reranking` returns success or failure
- includes:
  - `reranking.rank`

`reranking.rank`

- begins:
  - before reranking starts
- ends:
  - after final reranked candidate ordering is produced or reranking fails
- includes:
  - candidate scoring
  - score normalization
  - deterministic tie-break application
  - final selected-order materialization
- required attributes:
  - `reranker_kind`
    - type: string
    - source: config-derived
    - value: derived from the active `Settings.reranking.reranker` variant
  - `final_k`
    - type: integer
    - source: config-derived
    - value: `Settings.reranking.final_k`
- conditional attributes:
  - `recall_soft`
    - type: number
    - source: `RerankedRetrievalOutput.metrics.recall_soft`
    - emitted only when orchestration passes `Some(&GoldenRetrievalTargets)` for the current request
  - `recall_strict`
    - type: number
    - source: `RerankedRetrievalOutput.metrics.recall_strict`
    - emitted only when orchestration passes `Some(&GoldenRetrievalTargets)` for the current request
  - `rr_soft`
    - type: number
    - source: `RerankedRetrievalOutput.metrics.rr_soft`
    - emitted only when orchestration passes `Some(&GoldenRetrievalTargets)` for the current request
  - `rr_strict`
    - type: number
    - source: `RerankedRetrievalOutput.metrics.rr_strict`
    - emitted only when orchestration passes `Some(&GoldenRetrievalTargets)` for the current request
  - `ndcg`
    - type: number
    - source: `RerankedRetrievalOutput.metrics.ndcg`
    - emitted only when orchestration passes `Some(&GoldenRetrievalTargets)` for the current request
  - `first_relevant_rank_soft`
    - type: integer
    - source: `RerankedRetrievalOutput.metrics.first_relevant_rank_soft`
    - emitted only when `RerankedRetrievalOutput.metrics.first_relevant_rank_soft = Some(...)` for the current request
  - `first_relevant_rank_strict`
    - type: integer
    - source: `RerankedRetrievalOutput.metrics.first_relevant_rank_strict`
    - emitted only when `RerankedRetrievalOutput.metrics.first_relevant_rank_strict = Some(...)` for the current request
  - `num_relevant_soft`
    - type: integer
    - source: `RerankedRetrievalOutput.metrics.num_relevant_soft`
    - emitted only when orchestration passes `Some(&GoldenRetrievalTargets)` for the current request
  - `num_relevant_strict`
    - type: integer
    - source: `RerankedRetrievalOutput.metrics.num_relevant_strict`
    - emitted only when orchestration passes `Some(&GoldenRetrievalTargets)` for the current request
- emitted events:
  - `rerank_scores_computed`
    - payload:
      - `reranker_kind`
        - type: string
        - source: config-derived
        - value: derived from the active `Settings.reranking.reranker` variant
      - `candidate_count`
        - type: integer
        - source: runtime-derived
        - value: number of retrieval candidates received by reranking
  - `rerank_score_computation_failed`
    - payload:
      - `reranker_kind`
        - type: string
        - source: config-derived
        - value: derived from the active `Settings.reranking.reranker` variant
      - `candidate_count`
        - type: integer
        - source: runtime-derived
        - value: number of retrieval candidates received before failure
      - `error.type`
        - type: string
        - source: error-derived
        - value: reranking failure category
      - `error.message`
        - type: string
        - source: error-derived
        - value: reranking failure detail
  - `candidates_reordered`
    - payload:
      - `reranker_kind`
        - type: string
        - source: config-derived
        - value: derived from the active `Settings.reranking.reranker` variant
      - `candidate_count`
        - type: integer
        - source: runtime-derived
        - value: number of reranked candidates
  - `candidate_reorder_failed`
    - payload:
      - `reranker_kind`
        - type: string
        - source: config-derived
        - value: derived from the active `Settings.reranking.reranker` variant
      - `error.type`
        - type: string
        - source: error-derived
        - value: reorder failure category
      - `error.message`
        - type: string
        - source: error-derived
        - value: reorder failure detail

`generation`

- begins:
  - before `generation` module execution starts
- ends:
  - after `generation` returns success or failure
- includes:
  - `generation.prompt_assembly`
  - `generation.chat`
  - `generation.response_validation`

`generation.prompt_assembly`

- begins:
  - before prompt assembly starts
- ends:
  - after prompt assembly completes
- includes:
  - prompt template rendering
  - chunk insertion into prompt context
- emitted events:
  - `prompt_assembled`
    - payload:
      - `model_name`
        - type: string
        - source: config-derived
        - value: `Settings.generation.model_name`
      - `tokenizer_source`
        - type: string
        - source: config-derived
        - value: `Settings.generation.tokenizer_source`
      - `max_context_chunks`
        - type: integer
        - source: config-derived
        - value: `Settings.generation.max_context_chunks`
      - `max_prompt_tokens`
        - type: integer
        - source: config-derived
        - value: `Settings.generation.max_prompt_tokens`
      - `input_chunks`
        - type: integer
        - source: runtime-derived
        - value: number of chunks passed into prompt assembly
      - `prompt_length`
        - type: integer
        - source: runtime-derived
        - value: character length of assembled prompt
      - `prompt_token_count`
        - type: integer
        - source: runtime-derived
        - value: token count of the fully assembled chat prompt
  - `prompt_assembly_failed`
    - payload:
      - `model_name`
        - type: string
        - source: config-derived
        - value: `Settings.generation.model_name`
      - `tokenizer_source`
        - type: string
        - source: config-derived
        - value: `Settings.generation.tokenizer_source`
      - `max_context_chunks`
        - type: integer
        - source: config-derived
        - value: `Settings.generation.max_context_chunks`
      - `max_prompt_tokens`
        - type: integer
        - source: config-derived
        - value: `Settings.generation.max_prompt_tokens`
      - `input_chunks`
        - type: integer
        - source: runtime-derived
        - value: number of chunks passed into prompt assembly when available
      - `prompt_token_count`
        - type: integer
        - source: runtime-derived
        - value: token count of the fully assembled chat prompt when available
      - `error.type`
        - type: string
        - source: error-derived
        - value: prompt assembly failure category
      - `error.message`
        - type: string
        - source: error-derived
        - value: prompt assembly failure detail

`generation.chat`

- begins:
  - before generation request execution starts
- ends:
  - after generation request execution completes or fails
- includes:
  - generation provider request
  - generation provider response handling
- emitted events:
  - `generation_response_returned`
    - payload:
      - `model_name`
        - type: string
        - source: config-derived
        - value: `Settings.generation.model_name`
      - `temperature`
        - type: number
        - source: config-derived
        - value: `Settings.generation.temperature`
      - `http_status_code`
        - type: integer
        - source: result-derived
        - value: HTTP status code returned by generation provider
      - `response_content_length`
        - type: integer
        - source: result-derived
        - value: character length of returned response content
  - `generation_request_failed`
    - payload:
      - `model_name`
        - type: string
        - source: config-derived
        - value: `Settings.generation.model_name`
      - `temperature`
        - type: number
        - source: config-derived
        - value: `Settings.generation.temperature`
      - `http_status_code`
        - type: integer
        - source: result-derived
        - value: HTTP status code returned by generation provider when available
      - `error.type`
        - type: string
        - source: error-derived
        - value: generation request failure category
      - `error.message`
        - type: string
        - source: error-derived
        - value: generation request failure detail

`generation.response_validation`

- begins:
  - before generation response validation starts
- ends:
  - after generation response validation completes or fails
- includes:
  - response shape validation
  - answer extraction validation
  - completion token counting
- emitted events:
  - `generation_response_validated`
    - payload:
      - `model_name`
        - type: string
        - source: config-derived
        - value: `Settings.generation.model_name`
      - `answer_present`
        - type: boolean
        - source: result-derived
        - value: whether validated response contains a non-empty answer
      - `answer_length`
        - type: integer
        - source: result-derived
        - value: character length of validated answer
      - `completion_token_count`
        - type: integer
        - source: runtime-derived
        - value: token count of the validated final answer
      - `total_token_count`
        - type: integer
        - source: runtime-derived
        - value: prompt token count + completion token count
  - `generation_response_validation_failed`
    - payload:
      - `model_name`
        - type: string
        - source: config-derived
        - value: `Settings.generation.model_name`
      - `error.type`
        - type: string
        - source: error-derived
        - value: response validation failure category
      - `error.message`
        - type: string
        - source: error-derived
        - value: response validation failure detail

========================
9) OpenInference Usage
========================

Phoenix/OpenInference semantic span classification is defined only in:

- `Specification/codegen/rag_runtime/observability/openinference_spans.md`

`spans.md` must not redefine Phoenix/OpenInference semantic span-kind mapping or Phoenix-specific semantic attributes.

## 1) Purpose / Scope

This document defines the retrieval-quality metric helper contract for `rag_runtime`.

It defines:

- the metric inputs;
- the metric formulas;
- the rank and ordering rules;
- the required output metric bundle shape at the semantic level.

This document does not define:

- CLI behavior;
- orchestration ownership;
- observability attribute names;
- concrete Rust module paths;
- dataset-level reporting aggregates such as MRR across many requests.

Module-placement rule:

- the retrieval metrics helper must live in a dedicated internal Rust module of the generated `rag_runtime` crate;
- the helper must not be inlined into `retrieval`, `reranking`, or `orchestration` module bodies;
- unit tests for the helper must live in that helper module under its own `#[cfg(test)]` test module.

## 2) Role Of The Retrieval Metrics Helper

The retrieval metrics helper is a runtime utility owned by `rag_runtime`.

Its purpose is:

- to compute request-local retrieval-quality metrics from one golden retrieval target set and one actual full ranked output together with one effective top-k cutoff;
- to provide one source of truth for metric formulas used by retrieval and reranking;
- to keep retrieval-quality metric computation consistent across pipeline stages.

The helper computes per-request metrics only.
It does not compute cross-request aggregates.
The helper may reject invalid metric inputs.

## 3) Inputs

The helper consumes:

- one `GoldenRetrievalTargets`;
- one ordered list of actual chunk ids representing the full ranked output of the current stage;
- one positive integer `k`.

Input rules:

- actual chunk ids must follow the exact emitted rank order of the current stage;
- `k` is the effective top-k cutoff of the current stage;
- soft relevance comes from `GoldenRetrievalTargets.soft_positive_chunk_ids`;
- strict relevance comes from `GoldenRetrievalTargets.strict_positive_chunk_ids`;
- graded relevance comes from `GoldenRetrievalTargets.graded_relevance`.
- for the current contract, `strict_positive_chunk_ids` is a subset of `soft_positive_chunk_ids`;
- for the current contract, every chunk id in `soft_positive_chunk_ids` and `strict_positive_chunk_ids` must also appear in `graded_relevance`;
- for the current contract, graded relevance scores are restricted to:
  - `0.0`
  - `0.5`
  - `1.0`

## 4) Effective Top-k Set And Order

Let:

- `ActualTopK` be the first `k` chunk ids in the current stage output rank order.

Rank rules:

- ranks are `1`-based;
- the first item in `ActualTopK` has rank `1`;
- the second item in `ActualTopK` has rank `2`, and so on.

Duplicate-handling rules:

- let `ActualTopK_dedup` be the ordered prefix of unique chunk ids obtained by scanning `ActualTopK` from left to right and keeping only the first occurrence of each `chunk_id`;
- recall, reciprocal rank, relevant counts, DCG, IDCG, and nDCG must be computed against `ActualTopK_dedup`, not against the raw duplicated list;
- later duplicate occurrences must not increase recall, reciprocal rank, relevant counts, or DCG.

## 5) Recall@k

### 5.1) Soft Recall@k

Let:

- `Rel_soft` be the set of all chunk ids from `GoldenRetrievalTargets.soft_positive_chunk_ids`;
- `TopK_set` be the set of chunk ids in `ActualTopK_dedup`.

Then:

`recall_at_k_soft = |Rel_soft ∩ TopK_set| / |Rel_soft|`

### 5.2) Strict Recall@k

Let:

- `Rel_strict` be the set of all chunk ids from `GoldenRetrievalTargets.strict_positive_chunk_ids`;
- `TopK_set` be the set of chunk ids in `ActualTopK_dedup`.

Then:

`recall_at_k_strict = |Rel_strict ∩ TopK_set| / |Rel_strict|`

Recall rules:

- recall is request-local;
- recall depends only on which relevant chunk ids appear in the top-k prefix, not on their internal order;
- for the current contract, `Rel_soft` and `Rel_strict` are required non-empty sets.
- if `Rel_soft` or `Rel_strict` is empty, the helper must reject the input as invalid rather than synthesizing metric values.

## 6) Reciprocal Rank@k

This document defines per-request reciprocal rank.
It does not define mean reciprocal rank across many requests.

### 6.1) Soft Reciprocal Rank@k

Let:

- `rank_soft_first` be the `1`-based rank of the first chunk in `ActualTopK_dedup` whose id belongs to `Rel_soft`;
- operationally, this means scanning `ActualTopK_dedup` in rank order and stopping at the first chunk id that is also a member of `Rel_soft`.

Then:

- if such a chunk exists:
  - `rr_at_k_soft = 1 / rank_soft_first`
- otherwise:
  - `rr_at_k_soft = 0`

### 6.2) Strict Reciprocal Rank@k

Let:

- `rank_strict_first` be the `1`-based rank of the first chunk in `ActualTopK_dedup` whose id belongs to `Rel_strict`;
- operationally, this means scanning `ActualTopK_dedup` in rank order and stopping at the first chunk id that is also a member of `Rel_strict`.

Then:

- if such a chunk exists:
  - `rr_at_k_strict = 1 / rank_strict_first`
- otherwise:
  - `rr_at_k_strict = 0`

Derived rank outputs:

- `first_relevant_rank_soft` is `Some(rank_soft_first)` when a soft-relevant chunk exists in `ActualTopK_dedup`, otherwise `None`;
- `first_relevant_rank_strict` is `Some(rank_strict_first)` when a strict-relevant chunk exists in `ActualTopK_dedup`, otherwise `None`.

## 7) Relevant Count@k

### 7.1) Soft Relevant Count@k

`num_relevant_soft = |Rel_soft ∩ TopK_set|`

### 7.2) Strict Relevant Count@k

`num_relevant_strict = |Rel_strict ∩ TopK_set|`

Count rules:

- counts are computed over chunk ids in `ActualTopK_dedup`;
- duplicate chunk ids must not increase the count.

## 8) nDCG@k

The graded ranking metric for the current version is nDCG@k.

### 8.1) Graded Relevance Lookup

Let:

- `grade(chunk_id)` be the graded relevance score looked up from `GoldenRetrievalTargets.graded_relevance`;
- if a chunk id is not present in `graded_relevance`, its graded relevance is `0.0`.

### 8.2) DCG@k

Let:

- `rel_i` be the graded relevance of the chunk at rank `i` in `ActualTopK_dedup`.

Then:

`dcg_at_k = sum_{i=1..|ActualTopK_dedup|} rel_i / log2(i + 1)`

### 8.3) IDCG@k

Let:

- `IdealTopK` contain up to `k` unique chunk ids with the highest graded relevance scores from `GoldenRetrievalTargets.graded_relevance`, sorted by descending score;
- when multiple chunk ids have the same graded relevance score, the tie-breaking order inside `IdealTopK` must be deterministic.

Let:

- `ideal_rel_i` be the graded relevance at rank `i` in `IdealTopK`.

Then:

`idcg_at_k = sum_{i=1..|IdealTopK|} ideal_rel_i / log2(i + 1)`

### 8.4) nDCG@k

Then:

- if `idcg_at_k > 0`:
  - `ndcg_at_k = dcg_at_k / idcg_at_k`
- otherwise:
  - `ndcg_at_k = 0`

## 9) Output Semantics

The helper returns one per-request metric bundle whose semantic fields are:

- `evaluated_k`
- `recall_soft`
- `recall_strict`
- `rr_soft`
- `rr_strict`
- `ndcg`
- `first_relevant_rank_soft`
- `first_relevant_rank_strict`
- `num_relevant_soft`
- `num_relevant_strict`

Output rules:

- `evaluated_k` is the effective stage-owned top-k value supplied to the helper;
- metric values must be deterministic for the same inputs;
- this helper must not produce cross-request mean values;
- this helper must not rename per-request reciprocal rank into MRR.

## 10) Error Model

The helper must define one internal error type for retrieval-metric computation failures.

Required failure categories:

- invalid golden retrieval target shape for metric computation;
- invalid effective top-k metric input;
- inconsistent graded relevance state;
- unexpected internal metric computation state.

Error-model rules:

- helper failures are internal utility failures;
- helper failures must not become an independent public pipeline error domain;
- retrieval wraps helper failures into `RetrievalError`;
- reranking wraps helper failures into `RerankingError`.

## 11) Implementation Guidance

The metrics helper should be implemented through small private helper methods for individual metric computations.

Recommended decomposition:

- one private helper for recall-style metrics;
- one private helper for reciprocal-rank-style metrics;
- one private helper for relevant-count metrics;
- one private helper for DCG/IDCG/nDCG computation.

Implementation guidance rules:

- the helper may return an error when metric inputs violate the contract defined in this document;
- helper failure is an internal utility failure, not an independent public pipeline error domain;
- the public helper entrypoint may assemble the final metric bundle from these private helper methods;
- private helper methods should be deterministic and side-effect free;
- private helper methods should be testable in isolation through module-local unit tests.

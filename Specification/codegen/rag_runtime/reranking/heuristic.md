## 1) Purpose / Scope

This document defines the baseline heuristic reranker for `rag_runtime`.

It defines:
- heuristic reranker inputs;
- text normalization assumptions;
- required scoring signals;
- weighted score combination rules;
- ranking behavior;
- deterministic expectations.

This document does not define:
- pass-through behavior;
- cross-encoder reranking;
- API-based reranking;
- retrieval embedding or Qdrant ranking logic.

## 2) Role Of The Heuristic Reranker

The heuristic reranker is the baseline reranking implementation.

Its purpose is:
- to provide a cheap, deterministic reranking baseline;
- to improve candidate ordering using lexical and structural signals;
- to provide an evaluation baseline for later comparison with stronger rerankers.

This reranker is not a retrieval engine.
It only reorders already retrieved candidates.

## 3) Inputs

The heuristic reranker consumes:
- `ValidatedUserRequest.query`
- `Option<&GoldenRetrievalTargets>`
- `RetrievalOutput`
- `RerankingSettings.weights`

Candidate count is controlled by:
- `RerankingSettings.candidate_k`

`RerankingSettings.final_k` is not used by the heuristic reranker algorithm.
It remains orchestration-owned truncation input after reranking has produced the full candidate order.

When orchestration passes `Some(&GoldenRetrievalTargets)` for the current request:

- the heuristic reranker must compute reranking-stage retrieval-quality metrics at `RerankingSettings.final_k`;
- the heuristic reranker must call the helper defined by:
  - `Specification/codegen/rag_runtime/retrieval_metrics.md`
  with:
  - the current request's `GoldenRetrievalTargets`
  - the ordered reranked chunk-id list produced by the heuristic reranker
  - `RerankingSettings.final_k`
- the returned `RetrievalQualityMetrics` bundle must be written into `RerankedRetrievalOutput.metrics`.

## 4) Text Normalization Rules

The heuristic reranker must apply deterministic normalization to query and candidate text before lexical signal computation.

Required normalization rules:
- lowercase query and candidate text;
- trim outer whitespace;
- collapse repeated internal whitespace;
- tokenize by splitting on whitespace;
- preserve punctuation exactly as it appears in the normalized text;
- do not strip punctuation characters before token comparison;
- ignore empty tokens;
- ignore one-character tokens.

The first version does not require stemming or lemmatization.

## 5) Required Scoring Signals

The heuristic reranker must compute the following signals for every candidate:
- `retrieval_score`
- `query_term_coverage`
- `phrase_match_bonus`
- `title_section_match_bonus`

### 5.1) `retrieval_score`

- source: retrieval output
- meaning: dense retrieval confidence signal
- computation:
  - let `raw_retrieval_score` be `RetrievedChunk.score`
  - let `min_score` be the minimum `RetrievedChunk.score` across the current `RetrievalOutput.chunks`
  - let `max_score` be the maximum `RetrievedChunk.score` across the current `RetrievalOutput.chunks`
  - if `max_score > min_score`, compute:
    - `retrieval_score = (raw_retrieval_score - min_score) / (max_score - min_score)`
  - if `max_score == min_score`, set:
    - `retrieval_score = 1.0`
- output range:
  - `0.0 ..= 1.0`

### 5.2) `query_term_coverage`

- source: normalized query and normalized chunk text
- meaning: proportion of meaningful query terms present in the candidate chunk text
- computation:
  - let `query_terms` be the normalized query tokens after applying the normalization rules from section `4)`
  - let `unique_query_terms` be the deduplicated ordered set of `query_terms`
  - let `chunk_terms` be the normalized chunk text tokens after applying the same normalization rules
  - let `matched_query_terms` be the count of terms in `unique_query_terms` that appear at least once in `chunk_terms`
  - compute:
    - `query_term_coverage = matched_query_terms / unique_query_terms.len()`
  - if `unique_query_terms.len() == 0`, set:
    - `query_term_coverage = 0.0`
- output range:
  - `0.0 ..= 1.0`

### 5.3) `phrase_match_bonus`

- source: normalized query and normalized chunk text
- meaning: extra score when the chunk contains the full query phrase or query n-gram matches
- computation:
  - let `normalized_query_text` be the normalized query after lowercase, trim, and internal whitespace collapse
  - let `normalized_chunk_text` be the normalized chunk text after lowercase, trim, and internal whitespace collapse
  - if `normalized_query_text` is a non-empty substring of `normalized_chunk_text`, set:
    - `phrase_match_bonus = 1.0`
  - otherwise, construct all adjacent two-token phrases from `query_terms` by joining each neighboring token pair with one space
  - if at least one such two-token phrase appears as a substring in `normalized_chunk_text`, set:
    - `phrase_match_bonus = 0.5`
  - otherwise, set:
    - `phrase_match_bonus = 0.0`
- output range:
  - `0.0`
  - `0.5`
  - `1.0`

### 5.4) `title_section_match_bonus`

- source:
  - `Chunk.document_title`
  - `Chunk.section_title`
  - `Chunk.section_path`
- meaning: extra score when query terms match title-like metadata
- computation:
  - build one normalized metadata text by concatenating, in this order:
    - `Chunk.document_title`
    - `Chunk.section_title` when present
    - all items of `Chunk.section_path` joined with a single space
  - apply the normalization rules from section `4)` to that metadata text
  - let `metadata_terms` be the resulting tokens
  - let `unique_query_terms` be the deduplicated ordered set of normalized query tokens
  - let `matched_metadata_terms` be the count of terms in `unique_query_terms` that appear at least once in `metadata_terms`
  - compute:
    - `title_section_match_bonus = matched_metadata_terms / unique_query_terms.len()`
  - if `unique_query_terms.len() == 0`, set:
    - `title_section_match_bonus = 0.0`
- output range:
  - `0.0 ..= 1.0`

## 6) Weighted Combination Rules

The heuristic reranker must compute the final rerank score as a weighted combination of the configured signals.

Rules:
- weights are read from `RerankingSettings.weights`;
- for the current version, `RerankingSettings.weights` must expose exactly:
  - `retrieval_score`
  - `query_term_coverage`
  - `phrase_match_bonus`
  - `title_section_match_bonus`
- every configured weight must be finite and `>= 0.0`;
- weights are configuration, not hard-coded constants in the contract;
- the weighted combination must be deterministic for the same input and same settings;
- the weighted combination must produce exactly one `rerank_score` per candidate.

Required formula:

`rerank_score =
    weights.retrieval_score * retrieval_score +
    weights.query_term_coverage * query_term_coverage +
    weights.phrase_match_bonus * phrase_match_bonus +
    weights.title_section_match_bonus * title_section_match_bonus`

The contract does not require fixed hard-coded numeric defaults.
Recommended defaults may exist in config, but the implementation must treat weights as runtime-configurable.

## 7) Ranking Rules

The heuristic reranker must:
- compute one final `rerank_score` per candidate;
- sort candidates by descending final rerank score;
- preserve all candidates returned by retrieval;
- return the full reranked candidate set without truncation;
- preserve chunk payloads unchanged;
- preserve retrieval score alongside the new rerank score.

Tie-breaking rules must be deterministic.

Required tie-breaking order:
1. higher `rerank_score`
2. higher `retrieval_score`
3. original retrieval order

## 8) Output Contract

The heuristic reranker returns:
- `RerankedRetrievalOutput`

Output rules:
- every candidate in the input retrieval output must appear exactly once in the output;
- output order must reflect heuristic reranking order;
- output items must contain both `retrieval_score` and `rerank_score`.
- `RerankedRetrievalOutput.metrics`, when present, contains heuristic-reranking-stage metric values computed at `RerankingSettings.final_k`.

## 9) Failure Rules

The heuristic reranker must not fail merely because:
- the candidate list contains one item;
- the candidate list is already well ordered;
- a candidate does not match any lexical heuristic signal.

The heuristic reranker may fail only for real reranking-owned failures such as:
- invalid configured weights;
- retrieval metrics helper failure;
- invalid internal score computation state.

## 10) Determinism Rules

The heuristic reranker must be deterministic.

Rules:
- identical query, identical retrieval output, and identical settings must produce identical output order;
- heuristic reranking must not use randomization;
- heuristic reranking must not call external services.

## 11) Observability Hook

The heuristic reranker uses the `reranking` stage observability contract defined by:
- `Specification/codegen/rag_runtime/reranking/integration.md`
- `Specification/codegen/rag_runtime/observability/spans.md`
- `Specification/codegen/rag_runtime/observability/metrics.md`

Metric rules:

- the heuristic reranker must use the retrieval metrics helper defined by:
  - `Specification/codegen/rag_runtime/retrieval_metrics.md`
- the heuristic reranker must not duplicate retrieval-quality formulas inline across multiple call sites;
- if the retrieval metrics helper rejects invalid metric inputs, the heuristic reranker must surface that failure as a reranking-owned failure;
- when orchestration passes `None` for the current request, `RerankedRetrievalOutput.metrics` must be `None`;
- when orchestration passes `Some(&GoldenRetrievalTargets)` for the current request, `RerankedRetrievalOutput.metrics` must contain heuristic-reranking-stage metrics computed at `RerankingSettings.final_k`.

It must at minimum support latency observation through the reranking stage span and existing stage-duration metrics.

## 12) Unit-Test Hook

Required generated tests for the heuristic reranker are defined in:
- `Specification/codegen/rag_runtime/unit_tests.md`

The heuristic reranker generation is incomplete if the required reranking tests are missing.

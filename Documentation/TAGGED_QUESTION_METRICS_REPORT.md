# Tagged Question Metrics Report

## Purpose

This document summarizes the follow-up analysis that recomputes selected eval metrics by question tag instead of averaging only across the full 20-question benchmark.

The motivating question was:

`Which question types are sensitive to retrieval quality, and which are currently limited by generation quality?`

The analysis uses the current 20-question golden set and the following tag families:

- `causal`
- `contrast`
- `tradeoff`
- `failure`

For implementation details and reproducible outputs, see:

- [Execution/evals/tagged_metrics.py](../Execution/evals/tagged_metrics.py)
- [Execution/evals/golden_question_tags.json](../Execution/evals/golden_question_tags.json)
- [Evidence/analysis/tagged_question_metrics/tagged_metrics.md](../Evidence/analysis/tagged_question_metrics/tagged_metrics.md)
- [Evidence/analysis/tagged_question_metrics/per_question_metrics.csv](../Evidence/analysis/tagged_question_metrics/per_question_metrics.csv)

---

## Scope

The tagged recomputation currently focuses on these metrics:

- `answer_completeness_mean`
- `groundedness_mean`
- `answer_relevance_mean`
- `generation_context@4 strict recall`
- `generation_context@4 nDCG`

The analysis is computed from `request_run_summaries`, joined back to the canonical 20-question golden set and then expanded by tags.

This means the tagged report does not re-run judge models. It only reshapes and aggregates already materialized request-level results.

In this document:

- `weak gen` means the local generation model `qwen2.5:1.5b-instruct-ctx32k`
- `stronger gen` means the remote generation model `openai/gpt-oss-20b`
- `PassThrough reranker` means no learned reranking beyond preserving the retriever order
- `Heuristic reranker` means the repository's rule-based reranker that reweights retrieval candidates with lexical and section-aware signals
- `local mixedbread reranker` means the local cross-encoder reranker `mixedbread-ai/mxbai-rerank-base-v2` served at `http://localhost:8081`
- `Voyage reranker` means the remote cross-encoder reranker `rerank-2.5` served by Voyage AI

---

## Runs Used

The main comparison set in this report includes:

- `f8972737-1bb2-4cad-adb9-2a730f0101b3`
  `Hybrid bm25 + PassThrough reranker + weak local generation`
- `1bc4a880-48a1-4a41-957f-d531cbdde2f9`
  `Hybrid bm25 + Heuristic reranker + weak local generation`
- `e1b43ff2-91b9-49ad-aa7a-e9c4383c589d`
  `Hybrid bm25 + local mixedbread reranker + weak local generation`
- `9231451d-7e23-48e8-95c9-97a7a28f9189`
  `Dense + Voyage reranker + stronger remote generation`
- `05047884-3dc0-463b-a01e-2e3bed54589d`
  `Hybrid bm25 + Voyage reranker + weak local generation`
- `4890ab41-d02c-4bd2-86f9-4fdf5b6729dc`
  `Hybrid bm25 + PassThrough reranker + stronger remote generation`
- `2912cd07-b245-4479-a619-b0c745ff64b5`
  `Hybrid bm25 + local mixedbread reranker + stronger remote generation`

The most important control comparison is:

- `Hybrid bm25 + PassThrough reranker + weak gen`
  versus
- `Hybrid bm25 + PassThrough reranker + stronger gen`

because retrieval stays nearly constant while generation strength changes.

---

## Coverage Caveats

Several weak-generation runs were incomplete and must be interpreted directionally:

- `2f725ce8-aed5-4ded-9143-dbf25a738b94`
  `18/20`
- `e1b43ff2-91b9-49ad-aa7a-e9c4383c589d`
  `19/20`
- `05047884-3dc0-463b-a01e-2e3bed54589d`
  `19/20`

The tagged output explicitly reports expected versus observed question counts and lists missing question ids for each run-tag bucket.

Another important caveat is methodological:

- the stronger-generation comparison run uses `openai/gpt-oss-20b` both as generation model and as judge model

This does not invalidate the analysis for internal diagnosis, but it does mean the stronger-generation conclusions should be treated as high-signal internal evidence rather than as final external-proof benchmarking.

---

## Tagged Summary Table

The table below gives a compact view of the recomputed metrics across the four question tags for the most important control runs.

It intentionally focuses on the runs that answer the main diagnostic questions:

- `Dense` versus `Hybrid bm25`
- weak versus stronger generation
- `PassThrough reranker` versus `local mixedbread reranker`

| run / config | tag | answer completeness | groundedness | answer relevance | gen ctx strict recall@4 | gen ctx nDCG@4 |
|---|---|---:|---:|---:|---:|---:|
| `2f725...` Dense + PassThrough reranker + weak gen | `causal` | 0.5833 | 0.8333 | 1.0000 | 0.9167 | 0.8224 |
| `2f725...` Dense + PassThrough reranker + weak gen | `contrast` | 0.6250 | 0.7500 | 0.9375 | 0.9375 | 0.7406 |
| `2f725...` Dense + PassThrough reranker + weak gen | `failure` | 0.4500 | 0.8500 | 0.9000 | 1.0000 | 0.7959 |
| `2f725...` Dense + PassThrough reranker + weak gen | `tradeoff` | 0.6429 | 0.8571 | 1.0000 | 0.9286 | 0.8106 |
| `f897...` Hybrid bm25 + PassThrough reranker + weak gen | `causal` | 0.4286 | 0.7857 | 1.0000 | 1.0000 | 0.8403 |
| `f897...` Hybrid bm25 + PassThrough reranker + weak gen | `contrast` | 0.7778 | 0.7778 | 0.9444 | 1.0000 | 0.7866 |
| `f897...` Hybrid bm25 + PassThrough reranker + weak gen | `failure` | 0.5455 | 1.0000 | 0.9545 | 1.0000 | 0.8005 |
| `f897...` Hybrid bm25 + PassThrough reranker + weak gen | `tradeoff` | 0.6250 | 0.9375 | 0.8750 | 1.0000 | 0.8234 |
| `a2ecf5fd...` Dense + PassThrough reranker + stronger gen | `causal` | 0.8571 | 0.8571 | 0.8571 | 0.9286 | 0.8477 |
| `a2ecf5fd...` Dense + PassThrough reranker + stronger gen | `contrast` | 1.0000 | 1.0000 | 1.0000 | 0.9444 | 0.7694 |
| `a2ecf5fd...` Dense + PassThrough reranker + stronger gen | `failure` | 0.7273 | 0.9091 | 0.8182 | 1.0000 | 0.8035 |
| `a2ecf5fd...` Dense + PassThrough reranker + stronger gen | `tradeoff` | 0.6250 | 0.8750 | 0.6250 | 0.9375 | 0.8192 |
| `4890ab41...` Hybrid bm25 + PassThrough reranker + stronger gen | `causal` | 0.7143 | 0.7143 | 0.7143 | 1.0000 | 0.8492 |
| `4890ab41...` Hybrid bm25 + PassThrough reranker + stronger gen | `contrast` | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.7866 |
| `4890ab41...` Hybrid bm25 + PassThrough reranker + stronger gen | `failure` | 0.9091 | 0.9091 | 0.9091 | 1.0000 | 0.8082 |
| `4890ab41...` Hybrid bm25 + PassThrough reranker + stronger gen | `tradeoff` | 0.8750 | 0.8750 | 0.8750 | 1.0000 | 0.8418 |
| `2912cd07...` Hybrid bm25 + local mixedbread reranker + stronger gen | `causal` | 0.7143 | 0.7143 | 0.7143 | 1.0000 | 0.8827 |
| `2912cd07...` Hybrid bm25 + local mixedbread reranker + stronger gen | `contrast` | 0.8889 | 1.0000 | 1.0000 | 0.9444 | 0.8174 |
| `2912cd07...` Hybrid bm25 + local mixedbread reranker + stronger gen | `failure` | 0.6364 | 0.6364 | 0.6364 | 1.0000 | 0.8315 |
| `2912cd07...` Hybrid bm25 + local mixedbread reranker + stronger gen | `tradeoff` | 0.8750 | 0.8750 | 0.8750 | 1.0000 | 0.8545 |

Reading hints:

- compare `Dense` versus `Hybrid bm25` within the same generation strength to see retrieval-family effects;
- compare weak versus stronger generation within the same reranker to isolate generation bottlenecks;
- compare `PassThrough reranker` versus `local mixedbread reranker` under stronger generation to see whether reranking adds anything beyond a strong generator.

---

## Main Findings

### 1. `Contrast` is the most retrieval-sensitive tag

`Contrast` questions respond the most clearly to retrieval configuration.

Characteristic examples:

- `What is the difference between flow control and congestion control in TCP, and what type of overload is each mechanism designed to prevent?`
- `What is the difference between transport-layer and application-layer load balancing, and what extra capabilities does an L7 load balancer gain by understanding HTTP traffic?`

Examples:

- `Dense + PassThrough reranker + weak gen`
  completeness `0.6250`
- `Dense + PassThrough reranker + stronger gen`
  completeness `0.8889`
- `Hybrid bm25 + PassThrough reranker + weak gen`
  completeness `0.7778`
- `Hybrid bm25 + Heuristic reranker + weak gen`
  completeness `0.8333`
- `Hybrid bm25 + PassThrough reranker + stronger gen`
  completeness `1.0000`

This is important because the contrast pattern is visible not only when generation changes, but also when retrieval changes. Even with the same weak generator, `Hybrid bm25` outperforms `Dense` on the contrast slice.

This is consistent with the hypothesis that contrast questions depend strongly on lexical anchors, explicit oppositions, and well-separated concept pairs.

### 2. `Causal` questions are much more generation-limited

Characteristic examples:

- `Why are Lamport logical clocks not sufficient to capture causality precisely, and how do vector clocks improve on them?`
- `Why is the partially synchronous model usually a better fit for real distributed systems than either the strictly synchronous model or the fully asynchronous one?`

For `causal` questions, retrieval quality is already high in the important comparison runs:

- `Hybrid bm25 + PassThrough reranker + weak gen`
  strict recall@4 `1.0000`, nDCG `0.8403`
- `Hybrid bm25 + PassThrough reranker + stronger gen`
  strict recall@4 `1.0000`, nDCG `0.8492`

But answer completeness changes substantially:

- weak gen completeness `0.4286`
- stronger gen completeness `0.7143`

This indicates that causal questions are not primarily failing because the relevant context is missing. They are failing because the weaker generator often cannot synthesize the causal chain completely.

### 3. `Failure` questions are the clearest generation bottleneck

`Failure` questions show the strongest separation between retrieval quality and final answer quality.

Characteristic examples:

- `Why can retrying a POST request after a timeout create an inconsistent system state, and how do idempotency keys together with transactional atomicity solve this problem?`
- `Why can dual writes to a primary database and a secondary system such as a search index leave the system in an inconsistent state, and how does the outbox pattern address this problem?`

The key comparison is:

- `Hybrid bm25 + PassThrough reranker + weak gen`
  completeness `0.5455`, strict recall@4 `1.0000`, nDCG `0.8005`
- `Hybrid bm25 + PassThrough reranker + stronger gen`
  completeness `0.9091`, strict recall@4 `1.0000`, nDCG `0.8082`

Retrieval stays effectively unchanged, while answer completeness rises sharply.

This is the strongest evidence in the current dataset that some benchmark slices are limited primarily by generation quality rather than retrieval quality.

### 4. Better ranking metrics do not reliably improve answer quality

This pattern remains visible after tagging, not only in the overall averages.

For example, with stronger generation:

- `Hybrid bm25 + PassThrough reranker + stronger gen`
  `failure` completeness `0.9091`
- `Hybrid bm25 + local mixedbread reranker + stronger gen`
  `failure` completeness `0.6364`

Yet the mixedbread run has slightly better `failure` nDCG:

- PassThrough `0.8082`
- mixedbread `0.8315`

So even when generation is stronger, better context ranking diagnostics do not automatically translate into better answers.

### 5. `Tradeoff` sits between retrieval-sensitive and generation-limited

`Tradeoff` questions are more balanced.

Characteristic examples:

- `How does DNS resolution work, why does the TTL create a trade-off between fast propagation and lower lookup load, and why can serving stale records be more robust than serving no records at all?`
- `What trade-offs separate range partitioning from hash partitioning, and why can each approach still suffer from hotspots under certain access patterns?`

They do benefit from stronger generation, but they are not as obviously generation-limited as `failure`, and not as clearly retrieval-sensitive as `contrast`.

Representative values:

- `Hybrid bm25 + PassThrough reranker + weak gen`
  completeness `0.6250`
- `Hybrid bm25 + PassThrough reranker + stronger gen`
  completeness `0.8750`
- `Hybrid bm25 + local mixedbread reranker + stronger gen`
  completeness `0.8750`

This suggests tradeoff questions may be hybrid in a real systems sense: retrieval matters, but generator quality still decides whether the answer preserves both sides of the compromise.

---

## Stronger Generation Comparison

The strongest diagnostic question in this analysis was:

`How much does a stronger generator remove the failure on causal and failure questions under the same Hybrid bm25 + PassThrough reranker setup?`

Answer:

- On `causal`, completeness rises from `0.4286` to `0.7143`
- On `failure`, completeness rises from `0.5455` to `0.9091`
- In both cases, retrieval stays effectively fixed at strict recall@4 `1.0000`

This supports a strong systems conclusion:

`For causal and failure questions, the current weak local generator is a larger bottleneck than retrieval.`

---

## Mixedbread Comparison

The newer stronger-generation mixedbread run adds an important counterpoint.

Comparison:

- `Hybrid bm25 + PassThrough reranker + stronger gen`
- `Hybrid bm25 + local mixedbread reranker + stronger gen`

The tagged outcome is not favorable to mixedbread:

- `causal`
  answer quality unchanged, only nDCG slightly higher
- `contrast`
  answer completeness worsens from `1.0000` to `0.8889`
- `failure`
  answer completeness worsens from `0.9091` to `0.6364`
- `tradeoff`
  answer quality remains flat

The current interpretation is:

`the local mixedbread reranker does not currently outperform the PassThrough reranker once generation is already strong, and on failure questions it appears materially worse.`

---

## Working Conclusions

The current tagged analysis supports these working conclusions:

1. `Hybrid bm25` remains the stronger retrieval family for this benchmark.
2. `Contrast` questions are the most retrieval-sensitive slice in the current 20-question set.
3. `Causal` and especially `failure` questions are much more generation-limited.
4. Improvements in ranking-side diagnostics do not reliably transfer to answer quality.
5. The `PassThrough` reranker remains a very strong baseline.
6. The `local mixedbread` reranker does not currently justify itself over the `PassThrough` reranker once the generation model is already strong.

---

## What This Suggests Next

The current data makes two directions especially plausible.

### 1. Decomposition-aware retrieval for multi-part questions

Some causal and failure questions appear to combine several required subparts:

- mechanism
- failure mode
- tradeoff
- mitigation

That makes them good candidates for:

- question decomposition
- multi-query retrieval
- question rewrite that highlights the answer structure for the generator

### 2. Question-type-aware routing

The tags now look useful as a routing signal.

A practical next-stage idea would be:

- use cheaper retrieval plus weaker generation for easier contrast-style questions
- route causal and failure questions toward stronger generation or more structured retrieval flows

This is not yet a production routing policy, but the current evidence is strong enough to justify designing one experimentally.

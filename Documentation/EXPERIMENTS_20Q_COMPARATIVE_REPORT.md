# RAG Evaluation Report (20-Question Runs)

## Scope

This report summarizes a set of evaluation runs for a RAG pipeline tested on 20 questions across multiple configuration combinations. The runs vary by retrieval strategy, chunking strategy, and reranking strategy.

The 20-question set is not a random grab bag. It mixes four dominant reasoning patterns: causal explanation, contrast, trade-off analysis, and failure-oriented reasoning. Many questions intentionally combine two of these patterns, for example contrast plus trade-off, or failure analysis plus mitigation. This matters because the benchmark is designed to test explanation quality and evidence use, not only fact lookup.

The goal of this document is to answer three practical questions:

1. What do the reports already show with reasonable consistency?
2. What is still unclear from the current data?
3. What should be explored next?

---

## Evaluation Lens

The reports expose signals from at least two distinct layers:

- **Retrieval / ranking layer**: metrics such as recall, MRR, and nDCG over retrieved or selected chunks.
- **Generation layer**: metrics such as answer completeness, groundedness, and answer relevance.

This separation is useful because improvements in retrieval do not automatically translate into better downstream answers.

---

## Run Overview

The table below restores the compact overview across all recorded runs. It is included as a navigation layer rather than a leaderboard.

| Retriever | Chunking | Reranker | n | Run IDs | Answer completeness | Groundedness | Answer relevance | Gen ctx strict recall@4 | Gen ctx nDCG@4 | Stability note |
|---|---|---|---:|---|---:|---:|---:|---:|---:|---|
| Dense | structural | PassThrough | 1 | `a2ecf5fd` | 0.800 | 0.900 | 0.850 | 0.9500 | 0.7899 | single run |
| Dense | structural | CrossEncoder | 1 | `837f0e8b` | 0.900 | 0.825 | 0.900 | 0.9750 | 0.8371 | single run |
| Dense | fixed | PassThrough | 1 | `2d1d8fef` | 0.800 | 0.850 | 0.800 | 0.7708 | 0.8076 | single run |
| Dense | fixed | Heuristic | 1 | `e815b405` | 0.750 | 0.750 | 0.750 | 0.7958 | 0.8243 | single run |
| Dense | fixed | CrossEncoder | 1 | `a3e9f003` | 0.700 | 0.725 | 0.750 | 0.7833 | 0.8272 | single run |
| Hybrid bm25 | structural | PassThrough | 1 | `4890ab41` | 0.900 | 0.900 | 0.900 | 1.0000 | 0.8093 | single run |
| Hybrid bm25 | structural | Heuristic | 1 | `cd2431e5` | 0.800 | 0.850 | 0.800 | 1.0000 | 0.7756 | single run |
| Hybrid bm25 | structural | CrossEncoder | 2 | `7e13c930`, `5a5a0886` | 0.725 | 0.750 | 0.738 | 0.9750 | 0.8320 | repeated, answer metrics close |
| Hybrid bm25 | fixed | PassThrough | 1 | `77ac1095` | 0.900 | 0.900 | 0.900 | 0.8167 | 0.8166 | single run |
| Hybrid bm25 | fixed | CrossEncoder | 2 | `9961f583`, `0d85b984` | 0.688 | 0.700 | 0.725 | 0.8167 | 0.8222 | repeated, answer metrics noisy |
| Hybrid bow | structural | PassThrough | 1 | `efebfc1b` | 0.600 | 0.700 | 0.600 | 0.9250 | 0.5776 | single run |
| Hybrid bow | structural | CrossEncoder | 2 | `c4c0b74b`, `c6fca38c` | 0.788 | 0.812 | 0.825 | 0.9500 | 0.7865 | repeated, answer metrics noisy |
| Hybrid bow | fixed | PassThrough | 1 | `2d6399f1` | 0.800 | 0.800 | 0.800 | 0.7042 | 0.6694 | single run |
| Hybrid bow | fixed | CrossEncoder | 2 | `bb6f4bdd`, `087199f2` | 0.775 | 0.775 | 0.775 | 0.7833 | 0.8213 | repeated, answer metrics close |

Notes:
- Repeated hybrid `CrossEncoder` configurations are collapsed into one row per config.
- `n` shows how many runs were available for that configuration.
- For repeated rows, answer metrics are shown as simple averages across runs, while the stability note indicates whether the repeated runs were close or noisy.
- This table is intentionally descriptive. Interpretation is handled in the sections below.

## What the Reports Show

### 1. Structural chunking is promising, but not a universal winner

Structural chunking performs well in several important configurations, especially in the dense path and in the stronger hybrid BM25 path, but the current matrix does not support the broader claim that it always beats fixed chunking.

Observed pattern:

- Dense + structural is stronger than Dense + fixed in both the pass-through and cross-encoder branches.
- Hybrid BM25 + structural + PassThrough is one of the strongest runs in the matrix.
- At the same time, some fixed configurations still remain very competitive, so the chunking story is configuration-dependent rather than global.

What this likely means:

- Preserving semantic boundaries appears useful in several high-value configurations, but the benefit is configuration-dependent rather than universal.

What is **not** proven yet:

- That structural chunking is universally better.
- That the result would hold on a larger benchmark or a different document type.

---

### 2. Hybrid BM25 is the stronger sparse default

The gap between the two sparse strategies is one of the clearest signals in the reports.

Observed pattern:

- Under PassThrough, Hybrid BM25 clearly outperforms Hybrid BOW on both retrieval-side and answer-side metrics.
- Under CrossEncoder, the retrieval-side advantage of BM25 remains clear, while the answer-side advantage is smaller and, in some pairs, close to a tie.
- Hybrid BOW appears especially weak in the structural pass-through run.

What this likely means:

- The BM25-based sparse signal is currently more useful than the BOW variant as the default sparse branch in this pipeline.

Practical implication:

- Hybrid BOW is currently better treated as a baseline or comparison branch than as a main candidate for further optimization.

---

### 3. Pass-through is a stronger baseline than expected

One of the most important findings is that reranking does **not** currently show a stable advantage over simply passing the retrieved ranking through.

Observed pattern:

- In several configurations, pass-through matches or outperforms heuristic and cross-encoder reranking on answer-level metrics.
- In some cases, reranking improves ranking-oriented context metrics without improving the final answer.
- This is especially visible in the hybrid BM25 runs, where retrieval and context-quality metrics improve, but answer-level gains remain weak or inconsistent.

What this likely means:

- The current rerankers are not yet aligned with what the generator needs.
- Better pairwise query–chunk relevance does not necessarily mean a better **top-4 context set** for answer synthesis.

This is a meaningful systems result, not just a disappointing one.
It shows that the pipeline already exposes misalignment between local ranking improvements and end-task quality.

---

### 4. Dense retrieval remains competitive

The dense retriever performs well enough that the results do not support a simple conclusion like “hybrid always wins.”

Observed pattern:

- Dense + structural configurations remain competitive on answer completeness, relevance, and groundedness.
- In some runs, dense retrieval performs similarly to or better than hybrid variants once chunking and reranking are taken into account.
- This is particularly true in the dense structural branch, which remains one of the strongest dense configurations in the whole matrix.

What this likely means:

- Final behavior depends on the interaction between retriever, chunking, and reranker rather than on retrieval family alone.

---

### 5. Retrieval quality and answer quality do not move together linearly

This is one of the most important findings in the dataset.

Observed pattern:

- Better retrieval or generation-context ranking metrics do not always lead to better completeness, groundedness, or answer relevance.
- Some configurations improve local ranking metrics while degrading answer-level performance.

What this likely means:

- The pipeline should not be optimized using only retrieval-side metrics.
- End-task quality depends on the usefulness of the selected context set as a whole, not just on pairwise ranking quality.

This supports evaluating the pipeline as a multi-stage system rather than treating retrieval quality as a sufficient proxy for final answer quality.

---

## What Is Still Unclear

The current reports are already useful for macro-level decisions, but they are not yet sufficient for precise causal diagnosis.

### 1. Per-question failure mechanisms are still hidden

Aggregate metrics show which configuration is stronger overall, but they do not explain:

- which specific questions failed,
- whether the same questions fail across all configs,
- whether reranking helped some questions but hurt others,
- or whether failures are caused by missing context, wrong prioritization, or generation drift.

Without per-question comparison, it is difficult to move from pattern recognition to mechanism-level diagnosis.

---

### 2. The reranker failure mode is still ambiguous

The reports show that reranking is not yet a stable win, but they do not fully explain why.

Several explanations remain plausible:

- the reranker optimizes pair relevance rather than set utility,
- chunk size is too large for the reranker to discriminate well,
- the top-4 truncation interacts badly with reranked ordering,
- the cross-encoder is noisy on this benchmark,
- or the question set is too small to separate noise from signal.

At this point, the reports identify the problem but do not isolate the cause.

---

### 3. Sample size limits confidence

A 20-question benchmark is enough to expose useful trends, but it is still small.

This means:

- moderate score differences may still be unstable,
- one or two question-specific failures can noticeably move aggregates,
- and conclusions should be treated as directional rather than final.

---

### 4. Judge outputs are not yet structured enough for fast diagnosis

Answer-level labels are useful, but debugging would be easier with normalized reason codes such as:

- missing key point,
- partially supported answer,
- unsupported claim,
- wrong scope,
- incomplete answer,
- citation mismatch.

That would make aggregate metrics much more actionable.

---

## Practical Takeaways From the Current Reports

Based on the current dataset, the following directions are already justified:

### Keep as primary candidates

- Dense + structural
- Hybrid BM25 + structural

These are the most promising combinations to continue analyzing.

### Treat as strong baseline

- Pass-through ranking

This should remain the baseline for all future reranker comparisons.

### Deprioritize for now

- Hybrid BOW as a main optimization path

It can remain as a comparison branch, but the current reports do not support prioritizing it.

### Treat as unresolved

- Heuristic reranking
- Cross-encoder reranking

Both are worth keeping in the experiment harness, but neither currently shows a stable downstream win.

---

## Future Backlog: Questions, Directions, and Hypotheses

The next iteration should aim less at adding new components and more at explaining the behavior already observed.

### A. Per-question comparative analysis

**Question:** On which exact questions does pass-through beat reranking, and why?

**Why it matters:** Aggregate metrics may hide opposite effects across question types.

**What to add:**

- Per-question comparison table across selected configs.
- Retrieved top-k and final selected top-4 side by side.
- Answer-level labels side by side.
- Short explanation of what changed.

---

### B. Reranker diagnosis

**Question:** Why does improved ranking sometimes fail to improve the final answer?

**Hypotheses to test:**

1. The reranker improves pair relevance but harms context-set diversity.
2. Chunk granularity is too large for the reranker to order reliably.
3. The generator benefits from broader supporting context rather than tighter local relevance.
4. Top-4 truncation magnifies small reranking mistakes.

**Suggested experiments:**

- Compare pass-through vs reranked top-4 for the same question.
- Test smaller rerank input units.
- Try structural chunking followed by splitting into smaller rerank units.
- Measure overlap/diversity of selected chunks before and after reranking.

---

### C. Benchmark expansion

**Question:** Which conclusions remain stable when the question set grows?

**Why it matters:** 20 questions are enough for signal discovery, but not enough for high confidence.

**Suggested next step:**

- Expand the benchmark to 50–100 questions.
- Keep the existing 20-question subset as a stable comparison slice.

---

### D. Failure taxonomy

**Question:** What kinds of failures dominate the weak runs?

**Hypotheses to test:**

- Some runs fail mostly because of missing evidence.
- Others fail because the answer is only partially complete.
- Others fail because correct evidence was retrieved but not used well in generation.

**Suggested next step:**

Add normalized reason codes to evaluation outputs and track their distribution per config.

---

### E. Context-set metrics

**Question:** Are the current retrieval metrics capturing what the generator actually needs?

**Hypothesis:** Pairwise ranking metrics may be insufficient because the generator depends on the utility of the selected context set as a whole.

**Suggested next step:**

Consider adding diagnostics that reflect set-level usefulness, such as:

- coverage of required evidence across the selected top-4,
- redundancy within selected chunks,
- missing-subtopic signals.

---

## Recommended Next Iteration

A practical next iteration could focus on the following sequence:

1. Freeze pass-through as the reranker baseline.
2. Focus comparisons on:
   - Dense + structural
   - Hybrid BM25 + structural
3. Build a per-question diff report.
4. Add normalized failure reasons.
5. Expand the benchmark.
6. Add latency and cost tracking.

This would turn the current reports from strong directional evidence into a stronger basis for causal diagnosis and future optimization.

---

## Final Summary

The current reports already support several useful conclusions:

- structural chunking is promising in several important settings,
- hybrid BM25 is the stronger sparse default than hybrid BOW,
- pass-through is a strong baseline,
- rerankers improve retrieval-side metrics more reliably than they improve final answers,
- rerankers do not yet show a stable downstream advantage over pass-through,
- and retrieval-side improvements do not automatically translate into better answers.

At the same time, the reports do **not** yet fully explain why some configurations underperform.
The most valuable next step is therefore not broad feature expansion, but sharper diagnosis: per-question comparisons, failure taxonomy, and larger benchmark coverage.

---

## Report Index

The table below links directly to the underlying 20-question `run_report.md` artifacts used to build this report.

| Run ID | Chunking | Retriever | Sparse strategy | Reranker |
|---|---|---|---|---|
| [`2d1d8fef`](../Evidence/evals/runs/2026-04-10T14-05-52.660537+00-00_2d1d8fef-4844-4198-9367-29d069a01c92/run_report.md) | fixed | Dense | n/a | PassThrough |
| [`a2ecf5fd`](../Evidence/evals/runs/2026-04-10T14-26-32.320818+00-00_a2ecf5fd-3264-4570-8b4d-fee01d3e928b/run_report.md) | structural | Dense | n/a | PassThrough |
| [`2d6399f1`](../Evidence/evals/runs/2026-04-10T14-56-47.298559+00-00_2d6399f1-a2f4-4378-98f3-a15a2901b3da/run_report.md) | fixed | Hybrid | bow | PassThrough |
| [`77ac1095`](../Evidence/evals/runs/2026-04-10T15-13-42.916397+00-00_77ac1095-2dff-4f21-8e8e-1b64e32f63b8/run_report.md) | fixed | Hybrid | bm25 | PassThrough |
| [`efebfc1b`](../Evidence/evals/runs/2026-04-10T15-25-59.209506+00-00_efebfc1b-b8f0-4213-b263-f82537895c1f/run_report.md) | structural | Hybrid | bow | PassThrough |
| [`4890ab41`](../Evidence/evals/runs/2026-04-10T15-38-38.668918+00-00_4890ab41-d02c-4bd2-86f9-4fdf5b6729dc/run_report.md) | structural | Hybrid | bm25 | PassThrough |
| [`a3e9f003`](../Evidence/evals/runs/2026-04-10T16-12-11.664119+00-00_a3e9f003-d593-4ba1-9561-4fdcda45fbbd/run_report.md) | fixed | Dense | n/a | CrossEncoder |
| [`837f0e8b`](../Evidence/evals/runs/2026-04-10T16-29-09.017806+00-00_837f0e8b-5551-49c4-b750-90945a9214d5/run_report.md) | structural | Dense | n/a | CrossEncoder |
| [`bb6f4bdd`](../Evidence/evals/runs/2026-04-10T16-52-01.680444+00-00_bb6f4bdd-8a7b-4584-8d37-3972e59e0d34/run_report.md) | fixed | Hybrid | bow | CrossEncoder |
| [`9961f583`](../Evidence/evals/runs/2026-04-10T17-09-47.352479+00-00_9961f583-aaad-47ce-91fc-ef8fe47b4568/run_report.md) | fixed | Hybrid | bm25 | CrossEncoder |
| [`c4c0b74b`](../Evidence/evals/runs/2026-04-10T17-30-33.091411+00-00_c4c0b74b-fbc2-4a5c-8c9d-f6e1f6491b0f/run_report.md) | structural | Hybrid | bow | CrossEncoder |
| [`7e13c930`](../Evidence/evals/runs/2026-04-10T18-00-35.281478+00-00_7e13c930-8fd2-4e9f-872f-433b6099b10b/run_report.md) | structural | Hybrid | bm25 | CrossEncoder |
| [`e815b405`](../Evidence/evals/runs/2026-04-10T18-10-41.971181+00-00_e815b405-8f89-43a1-9413-5eca3bd4106b/run_report.md) | fixed | Dense | n/a | Heuristic |
| [`cd2431e5`](../Evidence/evals/runs/2026-04-10T18-31-39.394994+00-00_cd2431e5-320c-479c-b4d0-b9e63e179fde/run_report.md) | structural | Hybrid | bm25 | Heuristic |
| [`c6fca38c`](../Evidence/evals/runs/2026-04-10T18-51-02.652038+00-00_c6fca38c-fe8a-4693-b0e4-40c83181b8f2/run_report.md) | structural | Hybrid | bow | CrossEncoder |
| [`5a5a0886`](../Evidence/evals/runs/2026-04-10T19-08-09.057640+00-00_5a5a0886-697b-42a8-94c8-f33916084b1e/run_report.md) | structural | Hybrid | bm25 | CrossEncoder |
| [`087199f2`](../Evidence/evals/runs/2026-04-10T19-25-53.240813+00-00_087199f2-82fd-45b5-b2ad-07632aa017de/run_report.md) | fixed | Hybrid | bow | CrossEncoder |
| [`0d85b984`](../Evidence/evals/runs/2026-04-10T19-42-16.271737+00-00_0d85b984-5f15-4529-a4b2-9ac11f496372/run_report.md) | fixed | Hybrid | bm25 | CrossEncoder |

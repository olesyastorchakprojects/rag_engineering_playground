# Golden Datasets

## What this document covers

This document explains the role of golden datasets in the project.

They are used to support controlled runtime evaluation, retrieval-quality measurement, and comparable experiment runs.

---

## Why they exist

Golden datasets provide a fixed evaluation surface.

They make it possible to:

- run the same question set across different pipeline variants;
- compute request-local retrieval-quality metrics during runtime;
- compare runs without changing the underlying benchmark scope.

Without that fixed surface, it would be much harder to tell whether differences between runs came from pipeline changes or from changed input scope.

---

## What they contain

In the current project, a dataset bundle contains:

- `questions.txt` — the batch question set;
- `metadata.json` — dataset identity and descriptive metadata;
- per-profile golden retrieval companion files such as:
  - `fixed_golden_retrievals.json`
  - `structural_golden_retrievals.json`

The companion files define the expected retrieval targets for each question.
They are the runtime-owned input for retrieval-quality evaluation in batch mode.

The question set is intentionally mixed rather than uniform.
In the current project, the questions combine four recurring types:

- causal why: "Why is X considered Y, and through which mechanisms is that achieved?"
- contrast: "What is the difference between A and B, and what class of problems does each protect against?"
- trade-off: "Why does solution C help in one respect but worsen another?"
- failure-oriented: "Why does this effect appear under failure, timeout, or packet loss, and what mitigates it?"

The default dataset root used by the launcher is:

- `Evidence/evals/datasets/`

---

## How they are used

Golden datasets are used in three closely related ways.

### 1. Controlled runtime batch execution

The launcher selects a dataset bundle and passes:

- the question set into batch runtime execution;
- the matching golden retrieval companion file into `rag_runtime`.

This enables evaluated batch runs over a fixed question scope.

### 2. Retrieval and reranking metrics

When golden retrieval targets are present, runtime retrieval and reranking compute request-local metrics such as:

- recall
- reciprocal rank
- nDCG
- first relevant rank

These metrics are then propagated into request-level runtime evidence instead of being computed only later from exported artifacts.

### 3. Comparative evaluation

Because the same question scope can be reused across variants, golden datasets support side-by-side comparison across:

- chunking strategies;
- retrieval variants;
- reranking variants.

That makes them part of the project's comparability story, not just a convenience input file.

---

## What they are not

Golden datasets are not a replacement for request capture.

They do not represent:

- live runtime traffic;
- the full offline evaluation storage model;
- the only source of truth for system quality.

Instead, they provide a controlled benchmark surface that complements:

- request capture for persisted real run evidence;
- offline eval runs for normalized judge outputs and run reports.

---

## Relationship to the rest of the evaluation stack

Golden datasets sit closest to evaluated batch runtime execution.

They provide fixed questions and retrieval targets before request capture is written.
Request capture then preserves the actual runtime result for each processed question.
Offline evaluation later turns those captured results into:

- judge tables;
- request summaries;
- run manifests;
- run reports;
- dashboard-ready comparison surfaces.

So the golden dataset defines the benchmark scope, while request capture and offline evaluation preserve what actually happened during the run.

---

## Current limitations

Golden datasets improve comparability, but they are still only one evaluation surface.

Their limitations are straightforward:

- they cover only the included questions;
- they encode retrieval expectations, not every possible quality dimension;
- they should not be mistaken for broad real-world usage coverage.

They are useful because they make controlled comparison possible, not because they eliminate the need for other evidence surfaces.

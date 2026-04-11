# Eval Run Report Contract

## Purpose

This document defines the semantic contract for the human-readable run report produced for one eval run.

`run_report.md` is the canonical human-readable snapshot artifact for one completed eval run.

It exists to:

- summarize the current state of the system for the requests included in one run;
- complement Grafana dashboards with a fixed run-scoped snapshot;
- provide a compact, shareable artifact for offline review.

## Scope

This document defines:

- the required report sections;
- the required aggregated metric blocks;
- the relationship between `run_report.md` and `run_manifest.json`.

This document does not define:

- dashboard panels;
- raw judge table schemas;
- request-level per-row dump formats.

## Artifact Placement

The required report path for one run is:

- `Evidence/evals/runs/<run_started_at>_<run_id>/run_report.md`

The corresponding structured manifest is:

- `Evidence/evals/runs/<run_started_at>_<run_id>/run_manifest.json`

Artifact-folder naming rules for the current version:

- `<run_started_at>` is the run start timestamp rendered in a filesystem-safe UTC form derived from `started_at`;
- the artifact folder must remain human-readable and sortable by run start time;
- `run_id` remains the canonical run identity even though the folder name also includes the timestamp.

## Report Relationship To Storage

The run report is a run-scoped snapshot artifact.

It must be built from:

- `run_manifest.json`
- `judge_llm_calls` filtered by `run_id`
- `judge_generation_results` filtered by `run_id`
- `judge_retrieval_results` filtered by `run_id`
- request-level context as needed

The report must not rely on `request_summaries` alone as its only source, because `request_summaries` is the current per-request derived table rather than a historical per-run table.

## Required Sections

The report must contain the following sections.

### 1. Run Metadata

This section must begin with a top-level bullet list containing:

- `run_id`
- `run_type`
- `status`
- `started_at`
- `completed_at`, when present
- `request_count`
- `requests_evaluated`
- enabled generation suite versions
- enabled retrieval suite versions

This section must then contain four H3 subsections in this order:

#### Retriever subsection

Required heading: `### Retriever`

Required fields (when retriever config is available):

- `kind` — retriever kind string
- `embedding_model` — from `retriever_config.embedding_model_name`
- `collection` — from `retriever_config.qdrant_collection_name`
- `corpus_version` — from `retriever_config.corpus_version`
- `chunking_strategy` — from `retriever_config.chunking_strategy`

#### Reranker subsection

Required heading: `### Reranker`

Required fields (when reranker kind is available):

- `kind` — reranker kind string
- For `CrossEncoder`: `model` from `reranker_config.cross_encoder.model_name`, `url` from `reranker_config.cross_encoder.url`
- For `Heuristic`: one bullet per weight from `reranker_config.weights`, using `weight.<name>: <value>` format
- For `PassThrough`: no additional fields

#### Generation subsection

Required heading: `### Generation`

Required fields (when generation config is available):

- `model` — from `generation_config.model`
- `model_endpoint` — from `generation_config.model_endpoint`
- `temperature` — from `generation_config.temperature`
- `max_context_chunks` — from `generation_config.max_context_chunks`

#### Judge subsection

Required heading: `### Judge`

Required fields (always present):

- `provider` — judge provider identifier for the run
- `model` — judge model identifier from run params
- `endpoint` — judge base URL from run params

### 7. Token Usage

This section must summarize token usage and cost for both runtime requests and eval judge calls.

Required heading:

- `## Token Usage`

The section must contain two H3 subsections in this order:

#### Runtime token-usage subsection

Required heading: `### Runtime`

Required table:

| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|

The table must contain exactly one row:

- row label: `runtime`

Field-source rules:

- `requests` — count of runtime requests in the run scope
- `prompt tokens` — sum of `request_captures.prompt_tokens` across the run scope
- `completion tokens` — sum of `request_captures.completion_tokens` across the run scope
- `total tokens` — sum of `request_captures.total_tokens` across the run scope
- `prompt cost usd` — sum of `prompt_tokens * generation_config.input_cost_per_million_tokens / 1_000_000`
- `completion cost usd` — sum of `completion_tokens * generation_config.output_cost_per_million_tokens / 1_000_000`
- `total cost usd` — sum of runtime prompt and completion cost

#### Judge token-usage subsection

Required heading: `### Judge`

Required table:

| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|

The table must contain exactly three rows in this order:

- `judge_generation`
- `judge_retrieval`
- `judge_total`

Field-source rules:

- all judge token and cost values must be aggregated from `judge_llm_calls` filtered by `run_id`
- `judge_generation` aggregates rows where `stage_name = 'judge_generation'`
- `judge_retrieval` aggregates rows where `stage_name = 'judge_retrieval'`
- `judge_total` is the sum of both judge stages

Below the two token-usage tables, the section must include exactly these two formula lines separated by one blank line:

- `Run total cost usd = runtime total cost usd + judge total cost usd`
- `Run total cost usd = <runtime_total> + <judge_total> = <run_total>`

All token counts must be rendered as integers. All cost values must be formatted to eight decimal places.

Placement rule:

- `## Token Usage` must be the final top-level section in the report

### 2. Aggregated Metrics

This is the primary analytical section of the report.

It must provide one compact table of aggregated metrics for the requests included in the run.

Required metrics for the current version:

- `requests_evaluated`
- `answer_completeness_mean`
- `groundedness_mean`
- `answer_relevance_mean`
- `correct_refusal_rate`
- `retrieval_relevance_mean`
- `retrieval_relevance_selected_mean`
- `retrieval_relevance_weighted_topk_mean`

For score-like metrics, the report should include:

- mean
- p50
- p90
- contributing count

For rate-like metrics, the report should include:

- rate
- contributing count

### 4. Label Distributions

This section must summarize categorical outcome distributions for the current run.

Required breakdowns:

- `answer_completeness`
  - `complete`
  - `partial`
  - `incomplete`
- `groundedness`
  - `grounded`
  - `partially_grounded`
  - `ungrounded`
- `answer_relevance`
  - `relevant`
  - `partially_relevant`
  - `irrelevant`
- `correct_refusal`
  - `correct_refusal`
  - `unnecessary_refusal`
  - `non_refusal`

Each breakdown should include:

- absolute count
- percentage within the run

### 5. Retrieval Quality

This section must summarize retrieval and reranking quality metrics for the requests included in the run.

This section must be omitted entirely if the aggregated query over `request_run_summaries` returns NULL for all metric columns (i.e. no request in the run has non-null retrieval quality metrics).

Required table:

| set | Recall soft | Recall strict | MRR soft | MRR strict | nDCG |
|---|---:|---:|---:|---:|---:|

The table must contain exactly two rows:

- row 1 label: `top{retrieval_evaluated_k}` — averaged values of `retrieval_recall_soft`, `retrieval_recall_strict`, `retrieval_rr_soft`, `retrieval_rr_strict`, `retrieval_ndcg`
- row 2 label: `top{reranking_evaluated_k}` — averaged values of `reranking_recall_soft`, `reranking_recall_strict`, `reranking_rr_soft`, `reranking_rr_strict`, `reranking_ndcg`

Label values (`retrieval_evaluated_k` and `reranking_evaluated_k`) must be the integer k values taken from the run data.

All numeric values must be formatted to four decimal places. If an individual metric value is NULL, it must be rendered as `n/a` in the table cell.

Below the table, the section must include these scalar values as a bullet list:

- `retrieval_context_loss_soft` — avg `retrieval_context_loss_soft` across the run
- `retrieval_context_loss_strict` — avg `retrieval_context_loss_strict` across the run
- `avg_num_relevant_in_top{retrieval_evaluated_k}_soft` — avg `retrieval_num_relevant_soft`
- `avg_num_relevant_in_top{retrieval_evaluated_k}_strict` — avg `retrieval_num_relevant_strict`
- `avg_num_relevant_in_top{reranking_evaluated_k}_soft` — avg `reranking_num_relevant_soft`
- `avg_num_relevant_in_top{reranking_evaluated_k}_strict` — avg `reranking_num_relevant_strict`

Scalar values must be formatted to four decimal places.

### 6. Conditional Retrieval→Generation Aggregates

Short description (rendered in report, with k values substituted):
"These aggregates show generation quality conditioned on whether retrieval supplied
relevant context, separately for top{retrieval_evaluated_k}/top{reranking_evaluated_k}
and soft/strict relevance."

The section must be omitted if all 20 aggregate expressions resolve to NULL.

Required table:

| metric | top{retrieval_evaluated_k}_soft | top{retrieval_evaluated_k}_strict | top{reranking_evaluated_k}_soft | top{reranking_evaluated_k}_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context        | ... | ... | ... | ... |
| answer_completeness_given_relevant_context | ... | ... | ... | ... |
| answer_relevance_given_relevant_context    | ... | ... | ... | ... |
| hallucination_rate_when_top1_irrelevant    | ... | ... | ... | ... |
| success_rate_when_at_least_one_relevant_in_topk | ... | ... | ... | ... |

**Note (deviation from original task):** Column headers use the shorter form `top{k}_soft` / `top{k}_strict` instead of `top{k}_soft_conditioned`. This was chosen for table width. Any reference implementation must match these exact shorter names.

Column header substitution:
- {retrieval_evaluated_k}  = retrieval_evaluated_k value for the run (e.g. 12)
- {reranking_evaluated_k}  = reranking_evaluated_k value for the run  (e.g.  4)

Value formatting:
- Decimal values: 4 digits after the decimal point
- Zero-denominator cells: render "n/a"; never coerce to 0.0000
- The definitions footer below the table must render as two separate italicized lines with one blank line between them

Metric definitions:

Conditions used as row filters (DB column prefix depends on the condition set):

  For retrieval conditions (topk = retrieval_evaluated_k):
    has_relevant:     retrieval_num_relevant_{flavor} > 0
    top1_irrelevant:  retrieval_first_relevant_rank_{flavor} IS DISTINCT FROM 1

  For reranking conditions (topk = reranking_evaluated_k):
    has_relevant:     reranking_num_relevant_{flavor} > 0
    top1_irrelevant:  reranking_first_relevant_rank_{flavor} IS DISTINCT FROM 1

  flavor ∈ {soft, strict}
  NULL first_relevant_rank is treated as irrelevant (IS DISTINCT FROM 1 = true)

Per-request flags:
  hallucinated   := groundedness_score < 1.0
  success        := groundedness_score = 1.0 AND answer_completeness_score = 1.0
                    (answer_relevance is NOT part of success)

Metric formulas:
  A) groundedness_given_relevant_context
     = mean(groundedness_score) where has_relevant == true

  B) answer_completeness_given_relevant_context
     = mean(answer_completeness_score) where has_relevant == true

  C) answer_relevance_given_relevant_context
     = mean(answer_relevance_score) where has_relevant == true

  D) hallucination_rate_when_top1_irrelevant
     = mean(hallucinated) where top1_irrelevant == true
     = count(hallucinated in subset) / count(subset)

  E) success_rate_when_at_least_one_relevant_in_topk
     = mean(success) where has_relevant == true
     = count(success in subset) / count(subset)

Rendered footer lines:

- `_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0_`
- blank line
- `_Definitions: hallucinated = groundedness < 1.0_`

### 6. Worst-Case Preview

This section should contain a short preview of the lowest-quality requests for the run.

For the current version, include small capped lists for:

- lowest groundedness requests
- lowest answer completeness requests

Each preview entry should include:

- `request_id`
- the relevant score
- optionally `trace_id`

The report must not dump every request row in full.

## Report Design Rules

The report must be:

- run-scoped;
- aggregated first;
- concise enough for human review;
- informative enough to represent the current system snapshot.

The report must not:

- become a full per-request export;
- include raw judge prompt text;
- include raw full judge responses inline;
- overwhelm the reader with low-signal metrics.

## Relationship To Grafana

Grafana dashboards provide time-windowed operational views.

`run_report.md` provides a fixed run-scoped snapshot.

Therefore the report must emphasize:

- the exact requests included in one run;
- the aggregate quality state of that run;
- the specific run provenance needed for later comparison.

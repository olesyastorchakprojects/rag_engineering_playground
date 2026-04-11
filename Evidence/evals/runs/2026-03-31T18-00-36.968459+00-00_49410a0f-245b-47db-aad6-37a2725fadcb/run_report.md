# Eval Run Report

## Run Metadata
- run_id: `49410a0f-245b-47db-aad6-37a2725fadcb`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-03-31T18:00:36.968459+00:00`
- completed_at: `2026-03-31T18:31:01.307143+00:00`
- reranker_kind: `Heuristic`
- request_count: `5`
- requests_evaluated: `5`
- judge_model: `qwen2.5:1.5b-instruct-q4_K_M`
- generation_suite_versions: `{"answer_completeness": "v1", "answer_relevance": "v1", "correct_refusal": "v1", "groundedness": "v1"}`
- retrieval_suite_versions: `{"retrieval_relevance": "v1"}`

## Aggregated Metrics
| metric | mean/rate | p50 | p90 | count |
|---|---:|---:|---:|---:|
| answer_completeness_mean | 1.0000 | 1.0000 | 1.0000 | 5 |
| groundedness_mean | 0.4000 | 0.5000 | 1.0000 | 5 |
| answer_relevance_mean | 1.0000 | 1.0000 | 1.0000 | 5 |
| correct_refusal_rate | 1.0000 | 1.0000 | 1.0000 | 5 |
| retrieval_relevance_mean | 0.3833 | 0.0000 | 1.0000 | 60 |
| retrieval_relevance_selected_mean | 0.5500 | 1.0000 | 1.0000 | 20 |
| retrieval_relevance_weighted_topk_mean | 0.4488 | 0.3894 | 0.6266 | 5 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 5 | 100.0% |
| answer_completeness | partial | 0 | 0.0% |
| answer_completeness | incomplete | 0 | 0.0% |
| groundedness | grounded | 1 | 20.0% |
| groundedness | partially_grounded | 2 | 40.0% |
| groundedness | ungrounded | 2 | 40.0% |
| answer_relevance | relevant | 5 | 100.0% |
| answer_relevance | partially_relevant | 0 | 0.0% |
| answer_relevance | irrelevant | 0 | 0.0% |
| correct_refusal | correct_refusal | 5 | 100.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 0 | 0.0% |

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`225493ad-f5f2-47d8-a52a-0de6f640b1ae` score=`0.0000` trace_id=`32b221cbd3f27486e52d7ff47824fe9b`
- request_id=`3de028b6-20ae-4c7f-887f-3afb105dbf56` score=`0.0000` trace_id=`1a6a6f02b4ac031755757d79f1c09f98`
- request_id=`01c27bc5-959a-417c-8c60-0c2e2522acaf` score=`0.5000` trace_id=`8ef6ad87d91158a3ff30783e84626d5c`
- request_id=`3f8b78e0-68db-465d-8d97-ebb587e82d45` score=`0.5000` trace_id=`d451fb5f1dbb3159ba6e027881d71cb8`
- request_id=`250f1e00-9621-48b7-8105-51f7340f8d3d` score=`1.0000` trace_id=`3530c734486d3936d9ff3be65e9ca6e2`

### Lowest answer_completeness requests
- request_id=`01c27bc5-959a-417c-8c60-0c2e2522acaf` score=`1.0000` trace_id=`8ef6ad87d91158a3ff30783e84626d5c`
- request_id=`225493ad-f5f2-47d8-a52a-0de6f640b1ae` score=`1.0000` trace_id=`32b221cbd3f27486e52d7ff47824fe9b`
- request_id=`250f1e00-9621-48b7-8105-51f7340f8d3d` score=`1.0000` trace_id=`3530c734486d3936d9ff3be65e9ca6e2`
- request_id=`3de028b6-20ae-4c7f-887f-3afb105dbf56` score=`1.0000` trace_id=`1a6a6f02b4ac031755757d79f1c09f98`
- request_id=`3f8b78e0-68db-465d-8d97-ebb587e82d45` score=`1.0000` trace_id=`d451fb5f1dbb3159ba6e027881d71cb8`

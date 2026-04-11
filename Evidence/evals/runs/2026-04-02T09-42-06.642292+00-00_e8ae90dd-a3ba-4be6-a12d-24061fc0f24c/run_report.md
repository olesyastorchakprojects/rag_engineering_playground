# Eval Run Report

## Run Metadata
- run_id: `e8ae90dd-a3ba-4be6-a12d-24061fc0f24c`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-02T09:42:06.642292+00:00`
- completed_at: `2026-04-02T10:05:00.917878+00:00`
- reranker_kind: `CrossEncoder`
- request_count: `5`
- requests_evaluated: `5`
- judge_model: `qwen2.5:1.5b-instruct-q4_K_M`
- generation_suite_versions: `{"answer_completeness": "v1", "answer_relevance": "v1", "correct_refusal": "v1", "groundedness": "v1"}`
- retrieval_suite_versions: `{"retrieval_relevance": "v1"}`

## Aggregated Metrics
| metric | mean/rate | p50 | p90 | count |
|---|---:|---:|---:|---:|
| answer_completeness_mean | 0.8000 | 1.0000 | 1.0000 | 5 |
| groundedness_mean | 0.1000 | 0.0000 | 0.5000 | 5 |
| answer_relevance_mean | 1.0000 | 1.0000 | 1.0000 | 5 |
| correct_refusal_rate | 1.0000 | 1.0000 | 1.0000 | 5 |
| retrieval_relevance_mean | 0.1333 | 0.0000 | 1.0000 | 60 |
| retrieval_relevance_selected_mean | 0.2000 | 0.0000 | 1.0000 | 20 |
| retrieval_relevance_weighted_topk_mean | 0.2315 | 0.1933 | 0.3222 | 5 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 3 | 60.0% |
| answer_completeness | partial | 2 | 40.0% |
| answer_completeness | incomplete | 0 | 0.0% |
| groundedness | grounded | 0 | 0.0% |
| groundedness | partially_grounded | 1 | 20.0% |
| groundedness | ungrounded | 4 | 80.0% |
| answer_relevance | relevant | 5 | 100.0% |
| answer_relevance | partially_relevant | 0 | 0.0% |
| answer_relevance | irrelevant | 0 | 0.0% |
| correct_refusal | correct_refusal | 5 | 100.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 0 | 0.0% |

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`04fbae96-499c-4d52-8c97-8d8b9b386126` score=`0.0000` trace_id=`78987bdecf9098213a8894d1dee126ab`
- request_id=`7ea8bc9f-b479-4789-bb73-c2a301fd9eeb` score=`0.0000` trace_id=`4a8f4ca56b81add1509749ce1db312db`
- request_id=`b791207d-a630-4b2b-b224-318755c48d85` score=`0.0000` trace_id=`2ac7bf81c7b909de859ee83046bea745`
- request_id=`f573c5d6-254b-4a9f-9e29-90f6f93d8e6d` score=`0.0000` trace_id=`6757a6a72a7097b619337dc3973b8598`
- request_id=`657356fa-7a8b-4cb0-a7ad-8b8966124e38` score=`0.5000` trace_id=`04e9fa319e346459b2d4e89cfcf6d909`

### Lowest answer_completeness requests
- request_id=`7ea8bc9f-b479-4789-bb73-c2a301fd9eeb` score=`0.5000` trace_id=`4a8f4ca56b81add1509749ce1db312db`
- request_id=`b791207d-a630-4b2b-b224-318755c48d85` score=`0.5000` trace_id=`2ac7bf81c7b909de859ee83046bea745`
- request_id=`04fbae96-499c-4d52-8c97-8d8b9b386126` score=`1.0000` trace_id=`78987bdecf9098213a8894d1dee126ab`
- request_id=`657356fa-7a8b-4cb0-a7ad-8b8966124e38` score=`1.0000` trace_id=`04e9fa319e346459b2d4e89cfcf6d909`
- request_id=`f573c5d6-254b-4a9f-9e29-90f6f93d8e6d` score=`1.0000` trace_id=`6757a6a72a7097b619337dc3973b8598`

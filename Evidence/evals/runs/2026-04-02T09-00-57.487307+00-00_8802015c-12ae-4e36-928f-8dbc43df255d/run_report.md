# Eval Run Report

## Run Metadata
- run_id: `8802015c-12ae-4e36-928f-8dbc43df255d`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-02T09:00:57.487307+00:00`
- completed_at: `2026-04-02T09:26:56.496329+00:00`
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
| groundedness_mean | 0.4000 | 0.5000 | 0.5000 | 5 |
| answer_relevance_mean | 1.0000 | 1.0000 | 1.0000 | 5 |
| correct_refusal_rate | 1.0000 | 1.0000 | 1.0000 | 5 |
| retrieval_relevance_mean | 0.1333 | 0.0000 | 1.0000 | 60 |
| retrieval_relevance_selected_mean | 0.2500 | 0.0000 | 1.0000 | 20 |
| retrieval_relevance_weighted_topk_mean | 0.2420 | 0.2614 | 0.3222 | 5 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 5 | 100.0% |
| answer_completeness | partial | 0 | 0.0% |
| answer_completeness | incomplete | 0 | 0.0% |
| groundedness | grounded | 0 | 0.0% |
| groundedness | partially_grounded | 4 | 80.0% |
| groundedness | ungrounded | 1 | 20.0% |
| answer_relevance | relevant | 5 | 100.0% |
| answer_relevance | partially_relevant | 0 | 0.0% |
| answer_relevance | irrelevant | 0 | 0.0% |
| correct_refusal | correct_refusal | 5 | 100.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 0 | 0.0% |

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`10adfab7-c791-436b-a5bf-c0a195e22901` score=`0.0000` trace_id=`0196e214493bab1de23c77af4f26f3fd`
- request_id=`45a8ac4f-bba4-4ad6-b2c0-131936e3ad48` score=`0.5000` trace_id=`0e368e658a245fc3d3d90bd8bf9cf4a2`
- request_id=`718711dd-a8f5-4fa1-8622-bc0ffd34d545` score=`0.5000` trace_id=`dade7da82ee6e04a324b1dd6459e5d02`
- request_id=`ab2f654c-d1ca-42cb-af96-a77756b43720` score=`0.5000` trace_id=`e9a2af29439021d964eda3ba27cb5947`
- request_id=`dbb5c073-3010-4824-a693-a82a8976b1b2` score=`0.5000` trace_id=`e6a4cc2405c4b7f163a9fefde88ed038`

### Lowest answer_completeness requests
- request_id=`10adfab7-c791-436b-a5bf-c0a195e22901` score=`1.0000` trace_id=`0196e214493bab1de23c77af4f26f3fd`
- request_id=`45a8ac4f-bba4-4ad6-b2c0-131936e3ad48` score=`1.0000` trace_id=`0e368e658a245fc3d3d90bd8bf9cf4a2`
- request_id=`718711dd-a8f5-4fa1-8622-bc0ffd34d545` score=`1.0000` trace_id=`dade7da82ee6e04a324b1dd6459e5d02`
- request_id=`ab2f654c-d1ca-42cb-af96-a77756b43720` score=`1.0000` trace_id=`e9a2af29439021d964eda3ba27cb5947`
- request_id=`dbb5c073-3010-4824-a693-a82a8976b1b2` score=`1.0000` trace_id=`e6a4cc2405c4b7f163a9fefde88ed038`

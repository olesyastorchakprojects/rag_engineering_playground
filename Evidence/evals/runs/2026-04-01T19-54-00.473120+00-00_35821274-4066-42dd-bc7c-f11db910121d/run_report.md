# Eval Run Report

## Run Metadata
- run_id: `35821274-4066-42dd-bc7c-f11db910121d`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-01T19:54:00.473120+00:00`
- completed_at: `2026-04-01T20:27:57.019672+00:00`
- reranker_kind: `PassThrough`
- request_count: `5`
- requests_evaluated: `5`
- judge_model: `qwen2.5:1.5b-instruct-q4_K_M`
- generation_suite_versions: `{"answer_completeness": "v1", "answer_relevance": "v1", "correct_refusal": "v1", "groundedness": "v1"}`
- retrieval_suite_versions: `{"retrieval_relevance": "v1"}`

## Aggregated Metrics
| metric | mean/rate | p50 | p90 | count |
|---|---:|---:|---:|---:|
| answer_completeness_mean | 1.0000 | 1.0000 | 1.0000 | 5 |
| groundedness_mean | 0.5000 | 0.5000 | 0.5000 | 5 |
| answer_relevance_mean | 1.0000 | 1.0000 | 1.0000 | 5 |
| correct_refusal_rate | 1.0000 | 1.0000 | 1.0000 | 5 |
| retrieval_relevance_mean | 0.1333 | 0.0000 | 1.0000 | 60 |
| retrieval_relevance_selected_mean | 0.2500 | 0.0000 | 1.0000 | 20 |
| retrieval_relevance_weighted_topk_mean | 0.2429 | 0.2614 | 0.3222 | 5 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 5 | 100.0% |
| answer_completeness | partial | 0 | 0.0% |
| answer_completeness | incomplete | 0 | 0.0% |
| groundedness | grounded | 0 | 0.0% |
| groundedness | partially_grounded | 5 | 100.0% |
| groundedness | ungrounded | 0 | 0.0% |
| answer_relevance | relevant | 5 | 100.0% |
| answer_relevance | partially_relevant | 0 | 0.0% |
| answer_relevance | irrelevant | 0 | 0.0% |
| correct_refusal | correct_refusal | 5 | 100.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 0 | 0.0% |

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`87eab15f-98de-4f86-9cb3-5592f5ad94d7` score=`0.5000` trace_id=`87952569cc5da0fe10909f05afcec109`
- request_id=`b647e6f0-6d20-4704-9499-04d63d68a08c` score=`0.5000` trace_id=`e4734cce62dc6aa3e38c6c648fdba72f`
- request_id=`be3a9e72-60cd-4840-93ff-82c61256c706` score=`0.5000` trace_id=`336c2f20c19a78a0a4c59bfef10f9163`
- request_id=`e2d5caf3-8f9a-4887-9984-e293b8e625dc` score=`0.5000` trace_id=`d38803babfd149ab6f83431099e538ea`
- request_id=`f62faf62-873b-4357-899d-54d004c6b0b6` score=`0.5000` trace_id=`64b5ff337300127d5d18c33a492d59e2`

### Lowest answer_completeness requests
- request_id=`87eab15f-98de-4f86-9cb3-5592f5ad94d7` score=`1.0000` trace_id=`87952569cc5da0fe10909f05afcec109`
- request_id=`b647e6f0-6d20-4704-9499-04d63d68a08c` score=`1.0000` trace_id=`e4734cce62dc6aa3e38c6c648fdba72f`
- request_id=`be3a9e72-60cd-4840-93ff-82c61256c706` score=`1.0000` trace_id=`336c2f20c19a78a0a4c59bfef10f9163`
- request_id=`e2d5caf3-8f9a-4887-9984-e293b8e625dc` score=`1.0000` trace_id=`d38803babfd149ab6f83431099e538ea`
- request_id=`f62faf62-873b-4357-899d-54d004c6b0b6` score=`1.0000` trace_id=`64b5ff337300127d5d18c33a492d59e2`

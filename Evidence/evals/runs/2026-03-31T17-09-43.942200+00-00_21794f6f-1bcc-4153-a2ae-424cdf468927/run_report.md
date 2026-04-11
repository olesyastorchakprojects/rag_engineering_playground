# Eval Run Report

## Run Metadata
- run_id: `21794f6f-1bcc-4153-a2ae-424cdf468927`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-03-31T17:09:43.942200+00:00`
- completed_at: `2026-03-31T17:45:08.126504+00:00`
- reranker_kind: `PassThrough`
- request_count: `5`
- requests_evaluated: `5`
- judge_model: `qwen2.5:1.5b-instruct-q4_K_M`
- generation_suite_versions: `{"answer_completeness": "v1", "answer_relevance": "v1", "correct_refusal": "v1", "groundedness": "v1"}`
- retrieval_suite_versions: `{"retrieval_relevance": "v1"}`

## Aggregated Metrics
| metric | mean/rate | p50 | p90 | count |
|---|---:|---:|---:|---:|
| answer_completeness_mean | 0.9000 | 1.0000 | 1.0000 | 5 |
| groundedness_mean | 0.3000 | 0.0000 | 1.0000 | 5 |
| answer_relevance_mean | 1.0000 | 1.0000 | 1.0000 | 5 |
| correct_refusal_rate | 1.0000 | 1.0000 | 1.0000 | 5 |
| retrieval_relevance_mean | 0.3833 | 0.0000 | 1.0000 | 60 |
| retrieval_relevance_selected_mean | 0.5000 | 0.0000 | 1.0000 | 20 |
| retrieval_relevance_weighted_topk_mean | 0.4432 | 0.3894 | 0.6266 | 5 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 4 | 80.0% |
| answer_completeness | partial | 1 | 20.0% |
| answer_completeness | incomplete | 0 | 0.0% |
| groundedness | grounded | 1 | 20.0% |
| groundedness | partially_grounded | 1 | 20.0% |
| groundedness | ungrounded | 3 | 60.0% |
| answer_relevance | relevant | 5 | 100.0% |
| answer_relevance | partially_relevant | 0 | 0.0% |
| answer_relevance | irrelevant | 0 | 0.0% |
| correct_refusal | correct_refusal | 5 | 100.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 0 | 0.0% |

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`46f5f1d0-74b1-4adb-be05-2f9f1ffa6239` score=`0.0000` trace_id=`66cc257caf3a29563047a04118aa726a`
- request_id=`ccfb81a5-6443-448b-872a-8ba6a86d4616` score=`0.0000` trace_id=`3597c31874aa6edf5c9c4a1eddeea5a8`
- request_id=`e5650de0-9913-44a6-8266-288ced6ad9d2` score=`0.0000` trace_id=`164d0cea8515d319a485d7c4093f5fea`
- request_id=`63411542-b66a-4745-963d-0bbec8af8303` score=`0.5000` trace_id=`710802bb7df130275ba0c04cce691ea7`
- request_id=`4001fc90-a08a-4118-a991-43ca2242e480` score=`1.0000` trace_id=`35072446c3649a65577434141970592f`

### Lowest answer_completeness requests
- request_id=`ccfb81a5-6443-448b-872a-8ba6a86d4616` score=`0.5000` trace_id=`3597c31874aa6edf5c9c4a1eddeea5a8`
- request_id=`4001fc90-a08a-4118-a991-43ca2242e480` score=`1.0000` trace_id=`35072446c3649a65577434141970592f`
- request_id=`46f5f1d0-74b1-4adb-be05-2f9f1ffa6239` score=`1.0000` trace_id=`66cc257caf3a29563047a04118aa726a`
- request_id=`63411542-b66a-4745-963d-0bbec8af8303` score=`1.0000` trace_id=`710802bb7df130275ba0c04cce691ea7`
- request_id=`e5650de0-9913-44a6-8266-288ced6ad9d2` score=`1.0000` trace_id=`164d0cea8515d319a485d7c4093f5fea`

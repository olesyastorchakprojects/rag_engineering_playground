# Eval Run Report

## Run Metadata
- run_id: `dad4c313-9c45-4b63-b89f-f78bf3999c66`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-03-31T18:46:58.372602+00:00`
- completed_at: `2026-03-31T19:21:51.001863+00:00`
- reranker_kind: `CrossEncoder`
- request_count: `5`
- requests_evaluated: `5`
- judge_model: `qwen2.5:1.5b-instruct-q4_K_M`
- generation_suite_versions: `{"answer_completeness": "v1", "answer_relevance": "v1", "correct_refusal": "v1", "groundedness": "v1"}`
- retrieval_suite_versions: `{"retrieval_relevance": "v1"}`

## Aggregated Metrics
| metric | mean/rate | p50 | p90 | count |
|---|---:|---:|---:|---:|
| answer_completeness_mean | 0.9000 | 1.0000 | 1.0000 | 5 |
| groundedness_mean | 0.2000 | 0.0000 | 0.5000 | 5 |
| answer_relevance_mean | 1.0000 | 1.0000 | 1.0000 | 5 |
| correct_refusal_rate | 1.0000 | 1.0000 | 1.0000 | 5 |
| retrieval_relevance_mean | 0.3833 | 0.0000 | 1.0000 | 60 |
| retrieval_relevance_selected_mean | 0.4500 | 0.0000 | 1.0000 | 20 |
| retrieval_relevance_weighted_topk_mean | 0.4641 | 0.5670 | 0.6176 | 5 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 4 | 80.0% |
| answer_completeness | partial | 1 | 20.0% |
| answer_completeness | incomplete | 0 | 0.0% |
| groundedness | grounded | 0 | 0.0% |
| groundedness | partially_grounded | 2 | 40.0% |
| groundedness | ungrounded | 3 | 60.0% |
| answer_relevance | relevant | 5 | 100.0% |
| answer_relevance | partially_relevant | 0 | 0.0% |
| answer_relevance | irrelevant | 0 | 0.0% |
| correct_refusal | correct_refusal | 5 | 100.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 0 | 0.0% |

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`080fde33-b47a-4ec0-92b1-50c2453f341c` score=`0.0000` trace_id=`0c9f117e30bd6ed9129e12ab518e1e39`
- request_id=`b6c28257-e6ee-455c-afcf-ae4251c9093e` score=`0.0000` trace_id=`e8a466f9d0b7dc997be44b83abfbf616`
- request_id=`eee7dc8a-fd2a-4085-a0e8-ff8c4955dc94` score=`0.0000` trace_id=`0df0c9a07d999269e39c97577e31262c`
- request_id=`70cd9481-d815-4755-8371-28fb9852e62c` score=`0.5000` trace_id=`f36762007a61337370949b49e80e3173`
- request_id=`714983cb-cd4c-4a0a-85da-c248ee9046d1` score=`0.5000` trace_id=`978a4491d93079b7165f0e087fbcef39`

### Lowest answer_completeness requests
- request_id=`b6c28257-e6ee-455c-afcf-ae4251c9093e` score=`0.5000` trace_id=`e8a466f9d0b7dc997be44b83abfbf616`
- request_id=`080fde33-b47a-4ec0-92b1-50c2453f341c` score=`1.0000` trace_id=`0c9f117e30bd6ed9129e12ab518e1e39`
- request_id=`70cd9481-d815-4755-8371-28fb9852e62c` score=`1.0000` trace_id=`f36762007a61337370949b49e80e3173`
- request_id=`714983cb-cd4c-4a0a-85da-c248ee9046d1` score=`1.0000` trace_id=`978a4491d93079b7165f0e087fbcef39`
- request_id=`eee7dc8a-fd2a-4085-a0e8-ff8c4955dc94` score=`1.0000` trace_id=`0df0c9a07d999269e39c97577e31262c`

# Eval Run Report

## Run Metadata
- run_id: `f2f41aad-10af-45cc-9cfc-04a276715468`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-06T14:15:26.967246+00:00`
- completed_at: `2026-04-06T14:59:55.721719+00:00`
- retriever_kind: `Dense`
- reranker_kind: `PassThrough`
- request_count: `5`
- requests_evaluated: `5`
- judge_model: `qwen2.5:1.5b-instruct-ctx32k`
- generation_suite_versions: `{"answer_completeness": "v1", "answer_relevance": "v1", "correct_refusal": "v1", "groundedness": "v1"}`
- retrieval_suite_versions: `{"retrieval_relevance": "v1"}`

## Aggregated Metrics
| metric | mean/rate | p50 | p90 | count |
|---|---:|---:|---:|---:|
| answer_completeness_mean | 0.9000 | 1.0000 | 1.0000 | 5 |
| groundedness_mean | 0.1000 | 0.0000 | 0.5000 | 5 |
| answer_relevance_mean | 1.0000 | 1.0000 | 1.0000 | 5 |
| correct_refusal_rate | 1.0000 | 1.0000 | 1.0000 | 5 |
| retrieval_relevance_mean | 0.2833 | 0.0000 | 1.0000 | 60 |
| retrieval_relevance_selected_mean | 0.5000 | 0.0000 | 1.0000 | 20 |
| retrieval_relevance_weighted_topk_mean | 0.3917 | 0.3464 | 0.6499 | 5 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 4 | 80.0% |
| answer_completeness | partial | 1 | 20.0% |
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

## Retrieval Quality

| set | Recall soft | Recall strict | MRR soft | MRR strict | nDCG |
|---|---:|---:|---:|---:|---:|
| top12 | 0.5100 | 0.7533 | 1.0000 | 1.0000 | 0.6169 |
| top4 | 0.2067 | 0.4200 | 1.0000 | 1.0000 | 0.6249 |

- retrieval_context_loss_soft: 0.3033
- retrieval_context_loss_strict: 0.3333
- avg_num_relevant_in_top12_soft: 6.0000
- avg_num_relevant_in_top12_strict: 2.8000
- avg_num_relevant_in_top4_soft: 2.4000
- avg_num_relevant_in_top4_strict: 1.4000

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for top12/top4 and soft/strict relevance.

| metric | top12_soft | top12_strict | top4_soft | top4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.1000 | 0.1000 | 0.1000 | 0.1000 |
| answer_completeness_given_relevant_context | 0.9000 | 0.9000 | 0.9000 | 0.9000 |
| answer_relevance_given_relevant_context | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| hallucination_rate_when_top1_irrelevant | n/a | n/a | n/a | n/a |
| success_rate_when_at_least_one_relevant_in_topk | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`4f15f91b-c30b-4146-8b95-4661ddb348ce` score=`0.0000` trace_id=`de0bf7faebcc1d708eaa915c60063aaf`
- request_id=`777a6f8f-d250-4d15-9b97-daeb5d45878a` score=`0.0000` trace_id=`8d0851ebc48e6aed6408f90082fa6c5a`
- request_id=`deeebe25-cfca-4a92-9f66-9f53b66a3da4` score=`0.0000` trace_id=`8e2565b02da0c4fb28fd75b93695aa78`
- request_id=`f5736cf8-4e07-40e2-88c4-09ae7e6a6f92` score=`0.0000` trace_id=`73088bd4bbaab4a39263466c8eb7cdab`
- request_id=`0967d7b6-31f2-4368-9e92-136d04df0755` score=`0.5000` trace_id=`520eb60df46f32880bc8a574cb21515f`

### Lowest answer_completeness requests
- request_id=`deeebe25-cfca-4a92-9f66-9f53b66a3da4` score=`0.5000` trace_id=`8e2565b02da0c4fb28fd75b93695aa78`
- request_id=`0967d7b6-31f2-4368-9e92-136d04df0755` score=`1.0000` trace_id=`520eb60df46f32880bc8a574cb21515f`
- request_id=`4f15f91b-c30b-4146-8b95-4661ddb348ce` score=`1.0000` trace_id=`de0bf7faebcc1d708eaa915c60063aaf`
- request_id=`777a6f8f-d250-4d15-9b97-daeb5d45878a` score=`1.0000` trace_id=`8d0851ebc48e6aed6408f90082fa6c5a`
- request_id=`f5736cf8-4e07-40e2-88c4-09ae7e6a6f92` score=`1.0000` trace_id=`73088bd4bbaab4a39263466c8eb7cdab`

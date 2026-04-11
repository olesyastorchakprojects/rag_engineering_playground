# Eval Run Report

## Run Metadata
- run_id: `768b73f7-d5d8-4f02-b621-7353f49704e7`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-06T15:37:07.114298+00:00`
- completed_at: `2026-04-06T15:58:21.370428+00:00`
- retriever_kind: `Dense`
- reranker_kind: `CrossEncoder`
- request_count: `5`
- requests_evaluated: `5`
- judge_model: `qwen2.5:1.5b-instruct-ctx32k`
- generation_suite_versions: `{"answer_completeness": "v1", "answer_relevance": "v1", "correct_refusal": "v1", "groundedness": "v1"}`
- retrieval_suite_versions: `{"retrieval_relevance": "v1"}`

## Aggregated Metrics
| metric | mean/rate | p50 | p90 | count |
|---|---:|---:|---:|---:|
| answer_completeness_mean | 1.0000 | 1.0000 | 1.0000 | 5 |
| groundedness_mean | 0.0000 | 0.0000 | 0.0000 | 5 |
| answer_relevance_mean | 1.0000 | 1.0000 | 1.0000 | 5 |
| correct_refusal_rate | 1.0000 | 1.0000 | 1.0000 | 5 |
| retrieval_relevance_mean | 0.1333 | 0.0000 | 1.0000 | 60 |
| retrieval_relevance_selected_mean | 0.2500 | 0.0000 | 1.0000 | 20 |
| retrieval_relevance_weighted_topk_mean | 0.2515 | 0.1611 | 0.5729 | 5 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 5 | 100.0% |
| answer_completeness | partial | 0 | 0.0% |
| answer_completeness | incomplete | 0 | 0.0% |
| groundedness | grounded | 0 | 0.0% |
| groundedness | partially_grounded | 0 | 0.0% |
| groundedness | ungrounded | 5 | 100.0% |
| answer_relevance | relevant | 5 | 100.0% |
| answer_relevance | partially_relevant | 0 | 0.0% |
| answer_relevance | irrelevant | 0 | 0.0% |
| correct_refusal | correct_refusal | 5 | 100.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 0 | 0.0% |

## Retrieval Quality

| set | Recall soft | Recall strict | MRR soft | MRR strict | nDCG |
|---|---:|---:|---:|---:|---:|
| top12 | 0.5200 | 0.8833 | 1.0000 | 1.0000 | 0.6872 |
| top4 | 0.3200 | 0.7167 | 1.0000 | 1.0000 | 0.8102 |

- retrieval_context_loss_soft: 0.2000
- retrieval_context_loss_strict: 0.1667
- avg_num_relevant_in_top12_soft: 5.2000
- avg_num_relevant_in_top12_strict: 2.6000
- avg_num_relevant_in_top4_soft: 3.2000
- avg_num_relevant_in_top4_strict: 2.0000

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for top12/top4 and soft/strict relevance.

| metric | top12_soft | top12_strict | top4_soft | top4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| answer_completeness_given_relevant_context | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| answer_relevance_given_relevant_context | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| hallucination_rate_when_top1_irrelevant | n/a | n/a | n/a | n/a |
| success_rate_when_at_least_one_relevant_in_topk | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`07bdcf03-54db-4543-9d30-2a582301d52b` score=`0.0000` trace_id=`2b601d027bf40c9f5adbfc76cbfc0b89`
- request_id=`26ef2cb4-6862-4b68-8a0f-9f69d32b2337` score=`0.0000` trace_id=`4e6b080eb65590e0a0719b63bdfa9c1c`
- request_id=`42333be6-0700-4664-8ca1-f9c1532f4d22` score=`0.0000` trace_id=`eb84cf248912a18a8fe1d96f1526fbc1`
- request_id=`a6a7e443-9226-4729-b4ec-af5714f449c4` score=`0.0000` trace_id=`62af0a10f21f241935d0b6cc2b691c5d`
- request_id=`ba205c19-ca6a-451f-bcdf-03d1efc7675d` score=`0.0000` trace_id=`bfbc270cde18eb3d1d4671d9786eb023`

### Lowest answer_completeness requests
- request_id=`07bdcf03-54db-4543-9d30-2a582301d52b` score=`1.0000` trace_id=`2b601d027bf40c9f5adbfc76cbfc0b89`
- request_id=`26ef2cb4-6862-4b68-8a0f-9f69d32b2337` score=`1.0000` trace_id=`4e6b080eb65590e0a0719b63bdfa9c1c`
- request_id=`42333be6-0700-4664-8ca1-f9c1532f4d22` score=`1.0000` trace_id=`eb84cf248912a18a8fe1d96f1526fbc1`
- request_id=`a6a7e443-9226-4729-b4ec-af5714f449c4` score=`1.0000` trace_id=`62af0a10f21f241935d0b6cc2b691c5d`
- request_id=`ba205c19-ca6a-451f-bcdf-03d1efc7675d` score=`1.0000` trace_id=`bfbc270cde18eb3d1d4671d9786eb023`

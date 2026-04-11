# Eval Run Report

## Run Metadata
- run_id: `54d866a8-d282-4be1-ad01-0bed4b23cbe3`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-08T14:38:48.610171+00:00`
- completed_at: `2026-04-08T14:41:42.895817+00:00`
- request_count: `5`
- requests_evaluated: `5`
- generation_suite_versions: `{"answer_completeness": "v1", "answer_relevance": "v1", "correct_refusal": "v1", "groundedness": "v1"}`
- retrieval_suite_versions: `{"retrieval_relevance": "v1"}`

### Retriever
- kind: `Dense`
- embedding_model: `qwen3-embedding:0.6b`
- collection: `chunks_dense_qwen3_fixed`
- corpus_version: `v2`
- chunking_strategy: `fixed`
- top_k: `12`

### Reranker
- kind: `Heuristic`
- weight.retrieval_score: `1.0`
- weight.phrase_match_bonus: `1.0`
- weight.query_term_coverage: `1.0`
- weight.title_section_match_bonus: `1.0`

### Generation
- model: `openai/gpt-oss-20b`
- model_endpoint: `https://api.together.xyz`
- temperature: `0.0`
- max_context_chunks: `4`

### Judge
- provider: `together`
- model: `openai/gpt-oss-20b`
- endpoint: `https://api.together.xyz/v1`

## Aggregated Metrics
| metric | mean/rate | p50 | p90 | count |
|---|---:|---:|---:|---:|
| answer_completeness_mean | 0.8000 | 1.0000 | 1.0000 | 5 |
| groundedness_mean | 0.8000 | 1.0000 | 1.0000 | 5 |
| answer_relevance_mean | 0.8000 | 1.0000 | 1.0000 | 5 |
| correct_refusal_rate | 0.0000 | 0.0000 | 0.0000 | 5 |
| retrieval_relevance_mean | 0.2750 | 0.0000 | 1.0000 | 60 |
| retrieval_relevance_selected_mean | 0.4750 | 0.5000 | 1.0000 | 20 |
| retrieval_relevance_weighted_topk_mean | 0.4771 | 0.4565 | 0.6353 | 5 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 4 | 80.0% |
| answer_completeness | partial | 0 | 0.0% |
| answer_completeness | incomplete | 1 | 20.0% |
| groundedness | grounded | 4 | 80.0% |
| groundedness | partially_grounded | 0 | 0.0% |
| groundedness | ungrounded | 1 | 20.0% |
| answer_relevance | relevant | 4 | 80.0% |
| answer_relevance | partially_relevant | 0 | 0.0% |
| answer_relevance | irrelevant | 1 | 20.0% |
| correct_refusal | correct_refusal | 0 | 0.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 5 | 100.0% |

## Retrieval Quality

| set | Recall soft | Recall strict | MRR soft | MRR strict | nDCG |
|---|---:|---:|---:|---:|---:|
| top12 | 0.5200 | 0.8833 | 1.0000 | 1.0000 | 0.6872 |
| top4 | 0.3000 | 0.7667 | 1.0000 | 1.0000 | 0.8155 |

- retrieval_context_loss_soft: 0.2200
- retrieval_context_loss_strict: 0.1167
- avg_num_relevant_in_top12_soft: 5.2000
- avg_num_relevant_in_top12_strict: 2.6000
- avg_num_relevant_in_top4_soft: 3.0000
- avg_num_relevant_in_top4_strict: 2.2000

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for top12/top4 and soft/strict relevance.

| metric | top12_soft | top12_strict | top4_soft | top4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| answer_completeness_given_relevant_context | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| answer_relevance_given_relevant_context | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| hallucination_rate_when_top1_irrelevant | n/a | n/a | n/a | n/a |
| success_rate_when_at_least_one_relevant_in_topk | 0.8000 | 0.8000 | 0.8000 | 0.8000 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0_

_Definitions: hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`2dc57ea6-a432-4c24-a63d-b170a0afd585` score=`0.0000` trace_id=`f9a1d65438f543a2a020d7b1d1d198f2`
- request_id=`10529bcb-db85-4abf-9ef8-00d5dcb907a3` score=`1.0000` trace_id=`f1c2b6add082985dcae236bdae3513aa`
- request_id=`6f362a74-dccd-442e-bc16-dee65a474a81` score=`1.0000` trace_id=`90fc09c466b37fcf68b037081545d6d5`
- request_id=`88ebd2de-7d0a-47e4-a0b6-17cf49a845a1` score=`1.0000` trace_id=`ca3dbb3f5265fc2f35bc3a28c7069a31`
- request_id=`fc2e4eb4-ef40-4445-8abf-6151ab6c3a81` score=`1.0000` trace_id=`55c00770c9d54f26ead0f15d2d79c186`

### Lowest answer_completeness requests
- request_id=`2dc57ea6-a432-4c24-a63d-b170a0afd585` score=`0.0000` trace_id=`f9a1d65438f543a2a020d7b1d1d198f2`
- request_id=`10529bcb-db85-4abf-9ef8-00d5dcb907a3` score=`1.0000` trace_id=`f1c2b6add082985dcae236bdae3513aa`
- request_id=`6f362a74-dccd-442e-bc16-dee65a474a81` score=`1.0000` trace_id=`90fc09c466b37fcf68b037081545d6d5`
- request_id=`88ebd2de-7d0a-47e4-a0b6-17cf49a845a1` score=`1.0000` trace_id=`ca3dbb3f5265fc2f35bc3a28c7069a31`
- request_id=`fc2e4eb4-ef40-4445-8abf-6151ab6c3a81` score=`1.0000` trace_id=`55c00770c9d54f26ead0f15d2d79c186`

## Token Usage

### Runtime
| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| runtime | 5 | 8,829 | 2,280 | 11,109 | 0.00044145 | 0.00045600 | 0.00089745 |

### Judge
| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| judge_generation | 20 | 19,128 | 6,016 | 25,144 | 0.00095640 | 0.00120320 | 0.00215960 |
| judge_retrieval | 60 | 37,940 | 12,260 | 50,200 | 0.00189700 | 0.00245200 | 0.00434900 |
| judge_total | 80 | 57,068 | 18,276 | 75,344 | 0.00285340 | 0.00365520 | 0.00650860 |

Run total cost usd = runtime total cost usd + judge total cost usd

Run total cost usd = 0.00089745 + 0.00650860 = 0.00740605

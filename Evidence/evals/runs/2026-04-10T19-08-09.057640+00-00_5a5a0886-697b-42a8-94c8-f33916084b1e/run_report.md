# Eval Run Report

## Run Metadata
- eval_run_id: `5a5a0886-697b-42a8-94c8-f33916084b1e`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-10T19:08:09.057640+00:00`
- runtime_run_id: `bbd91c88-a23b-4e15-9e4c-d09a3969ca78`
- completed_at: `2026-04-10T19:16:59.376336+00:00`
- request_count: `20`
- requests_evaluated: `20`
- generation_suite_versions: `{"answer_completeness": "v1", "answer_relevance": "v1", "correct_refusal": "v1", "groundedness": "v1"}`
- retrieval_suite_versions: `{"retrieval_relevance": "v1"}`

### Retriever
- kind: `Hybrid - bm25`
- embedding_model: `qwen3-embedding:0.6b`
- collection: `chunks_hybrid_structural_qwen3`
- corpus_version: `v1`
- chunking_strategy: `structural`
- top_k: `12`
- actual_chunks_returned: `mean=7.60, min=5, max=9`

### Reranker
- kind: `CrossEncoder`
- model: `rerank-2.5`
- url: `https://api.voyageai.com/v1/rerank`

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
| answer_completeness_mean | 0.7500 | 1.0000 | 1.0000 | 20 |
| groundedness_mean | 0.7500 | 1.0000 | 1.0000 | 20 |
| answer_relevance_mean | 0.7500 | 1.0000 | 1.0000 | 20 |
| correct_refusal_rate | 0.0000 | 0.0000 | 0.0000 | 20 |
| retrieval_relevance_mean | 0.3224 | 0.5000 | 1.0000 | 152 |
| retrieval_relevance_selected_mean | 0.4750 | 0.5000 | 1.0000 | 80 |
| retrieval_relevance_weighted_topk_mean | 0.5057 | 0.5155 | 0.6730 | 20 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 15 | 75.0% |
| answer_completeness | partial | 0 | 0.0% |
| answer_completeness | incomplete | 5 | 25.0% |
| groundedness | grounded | 15 | 75.0% |
| groundedness | partially_grounded | 0 | 0.0% |
| groundedness | ungrounded | 5 | 25.0% |
| answer_relevance | relevant | 15 | 75.0% |
| answer_relevance | partially_relevant | 0 | 0.0% |
| answer_relevance | irrelevant | 5 | 25.0% |
| correct_refusal | correct_refusal | 0 | 0.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 20 | 100.0% |

## Retrieval Quality

| set | Recall soft | Recall strict | MRR soft | MRR strict | nDCG |
|---|---:|---:|---:|---:|---:|
| retrieval@12 | 0.6700 | 1.0000 | 1.0000 | 0.9667 | 0.7936 |
| generation_context@4 | 0.5700 | 0.9750 | 1.0000 | 0.9750 | 0.8320 |

- retrieval_context_loss_soft: 0.1000
- retrieval_context_loss_strict: 0.0250
- avg_num_relevant_in_retrieval@12_soft: 3.3500
- avg_num_relevant_in_retrieval@12_strict: 1.4500
- avg_num_relevant_in_generation_context@4_soft: 2.8500
- avg_num_relevant_in_generation_context@4_strict: 1.4000

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for retrieval@12/generation_context@4 and soft/strict relevance.

| metric | retrieval@12_soft | retrieval@12_strict | generation_context@4_soft | generation_context@4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.7500 | 0.7500 | 0.7500 | 0.7500 |
| answer_completeness_given_relevant_context | 0.7500 | 0.7500 | 0.7500 | 0.7500 |
| answer_relevance_given_relevant_context | 0.7500 | 0.7500 | 0.7500 | 0.7500 |
| hallucination_rate_when_top1_irrelevant | n/a | 0.0000 | n/a | 0.0000 |
| success_rate_when_at_least_one_relevant_in_topk | 0.7500 | 0.7500 | 0.7500 | 0.7500 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0_

_Definitions: hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`17925711-a7ec-4cd8-876a-07e10fa78f91` score=`0.0000` trace_id=`f39ac50ee5471f73a76f80181e452db6`
- request_id=`5f90fa4d-c2c1-424a-9be6-fa06608667dc` score=`0.0000` trace_id=`4b5c3b1564cb85bb9ada452d02962151`
- request_id=`61550e95-f28e-4442-896f-0839be15aa66` score=`0.0000` trace_id=`1f3f6c9ec42393e9f2ea2fe324836ab2`
- request_id=`a2c06bca-c555-428a-b8d3-2674a8323402` score=`0.0000` trace_id=`751b7b50193c80278e8949b0b2869bb2`
- request_id=`bfa72d0e-b196-421d-8b40-247fe9925deb` score=`0.0000` trace_id=`7a72776396830fad801d0f6b0a217d44`

### Lowest answer_completeness requests
- request_id=`17925711-a7ec-4cd8-876a-07e10fa78f91` score=`0.0000` trace_id=`f39ac50ee5471f73a76f80181e452db6`
- request_id=`5f90fa4d-c2c1-424a-9be6-fa06608667dc` score=`0.0000` trace_id=`4b5c3b1564cb85bb9ada452d02962151`
- request_id=`61550e95-f28e-4442-896f-0839be15aa66` score=`0.0000` trace_id=`1f3f6c9ec42393e9f2ea2fe324836ab2`
- request_id=`a2c06bca-c555-428a-b8d3-2674a8323402` score=`0.0000` trace_id=`751b7b50193c80278e8949b0b2869bb2`
- request_id=`bfa72d0e-b196-421d-8b40-247fe9925deb` score=`0.0000` trace_id=`7a72776396830fad801d0f6b0a217d44`

## Token Usage

### Runtime
| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| runtime | 20 | 48,959 | 10,472 | 59,431 | 0.00244795 | 0.00209440 | 0.00454235 |

### Judge
| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| judge_generation | 80 | 89,122 | 24,052 | 113,174 | 0.00445610 | 0.00481040 | 0.00926650 |
| judge_retrieval | 152 | 127,075 | 33,194 | 160,269 | 0.00635375 | 0.00663880 | 0.01299255 |
| judge_total | 232 | 216,197 | 57,246 | 273,443 | 0.01080985 | 0.01144920 | 0.02225905 |

Run total cost usd = runtime total cost usd + judge total cost usd

Run total cost usd = 0.00454235 + 0.02225905 = 0.02680140

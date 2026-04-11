# Eval Run Report

## Run Metadata
- eval_run_id: `efebfc1b-b8f0-4213-b263-f82537895c1f`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-10T15:25:59.209506+00:00`
- runtime_run_id: `5e37178c-5a99-463c-b887-314e2b5ddb19`
- completed_at: `2026-04-10T15:33:12.482343+00:00`
- request_count: `20`
- requests_evaluated: `20`
- generation_suite_versions: `{"answer_completeness": "v1", "answer_relevance": "v1", "correct_refusal": "v1", "groundedness": "v1"}`
- retrieval_suite_versions: `{"retrieval_relevance": "v1"}`

### Retriever
- kind: `Hybrid - bow`
- embedding_model: `qwen3-embedding:0.6b`
- collection: `chunks_hybrid_structural_qwen3`
- corpus_version: `v1`
- chunking_strategy: `structural`
- top_k: `12`
- actual_chunks_returned: `mean=8.00, min=6, max=10`

### Reranker
- kind: `PassThrough`

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
| answer_completeness_mean | 0.6000 | 1.0000 | 1.0000 | 20 |
| groundedness_mean | 0.7000 | 1.0000 | 1.0000 | 20 |
| answer_relevance_mean | 0.6000 | 1.0000 | 1.0000 | 20 |
| correct_refusal_rate | 0.0500 | 0.0000 | 0.0000 | 20 |
| retrieval_relevance_mean | 0.2344 | 0.0000 | 1.0000 | 160 |
| retrieval_relevance_selected_mean | 0.3125 | 0.0000 | 1.0000 | 80 |
| retrieval_relevance_weighted_topk_mean | 0.3371 | 0.3084 | 0.4599 | 20 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 12 | 60.0% |
| answer_completeness | partial | 0 | 0.0% |
| answer_completeness | incomplete | 8 | 40.0% |
| groundedness | grounded | 14 | 70.0% |
| groundedness | partially_grounded | 0 | 0.0% |
| groundedness | ungrounded | 6 | 30.0% |
| answer_relevance | relevant | 12 | 60.0% |
| answer_relevance | partially_relevant | 0 | 0.0% |
| answer_relevance | irrelevant | 8 | 40.0% |
| correct_refusal | correct_refusal | 1 | 5.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 19 | 95.0% |

## Retrieval Quality

| set | Recall soft | Recall strict | MRR soft | MRR strict | nDCG |
|---|---:|---:|---:|---:|---:|
| retrieval@12 | 0.5500 | 0.9500 | 0.8500 | 0.7800 | 0.6170 |
| generation_context@4 | 0.3400 | 0.9250 | 0.8500 | 0.7750 | 0.5776 |

- retrieval_context_loss_soft: 0.2100
- retrieval_context_loss_strict: 0.0250
- avg_num_relevant_in_retrieval@12_soft: 2.7500
- avg_num_relevant_in_retrieval@12_strict: 1.3500
- avg_num_relevant_in_generation_context@4_soft: 1.7000
- avg_num_relevant_in_generation_context@4_strict: 1.3000

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for retrieval@12/generation_context@4 and soft/strict relevance.

| metric | retrieval@12_soft | retrieval@12_strict | generation_context@4_soft | generation_context@4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.7000 | 0.7000 | 0.7000 | 0.7368 |
| answer_completeness_given_relevant_context | 0.6000 | 0.6000 | 0.6000 | 0.6316 |
| answer_relevance_given_relevant_context | 0.6000 | 0.6000 | 0.6000 | 0.6316 |
| hallucination_rate_when_top1_irrelevant | 0.1667 | 0.2500 | 0.1667 | 0.2500 |
| success_rate_when_at_least_one_relevant_in_topk | 0.6000 | 0.6000 | 0.6000 | 0.6316 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0_

_Definitions: hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`29845abd-fa27-4ba2-ace2-64f346b04b64` score=`0.0000` trace_id=`3772ea215f30285a5be87102d33672ca`
- request_id=`2ba1fdf9-aaad-4696-b926-ee4e1f7e0c38` score=`0.0000` trace_id=`f08630a0536b1ba607df934962a375a2`
- request_id=`556bfba8-626d-467d-bd10-14b07565938e` score=`0.0000` trace_id=`a91b4348204b2c86f0511953455ee904`
- request_id=`812a7a14-2fde-4925-b124-05a8c476ad1e` score=`0.0000` trace_id=`d5d4bb16757956ab75c0ac5a58ddcb81`
- request_id=`ac1cf875-23cc-4528-954b-79d6d0b97d49` score=`0.0000` trace_id=`aaada360775e4b56d51a2dbf5cea04b0`

### Lowest answer_completeness requests
- request_id=`29845abd-fa27-4ba2-ace2-64f346b04b64` score=`0.0000` trace_id=`3772ea215f30285a5be87102d33672ca`
- request_id=`2ba1fdf9-aaad-4696-b926-ee4e1f7e0c38` score=`0.0000` trace_id=`f08630a0536b1ba607df934962a375a2`
- request_id=`556bfba8-626d-467d-bd10-14b07565938e` score=`0.0000` trace_id=`a91b4348204b2c86f0511953455ee904`
- request_id=`5e21141f-4e6b-41ec-971b-ff51d693ef83` score=`0.0000` trace_id=`b4f6ddef3cdfd468b7b71f59970794fe`
- request_id=`812a7a14-2fde-4925-b124-05a8c476ad1e` score=`0.0000` trace_id=`d5d4bb16757956ab75c0ac5a58ddcb81`

## Token Usage

### Runtime
| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| runtime | 20 | 92,733 | 11,093 | 103,826 | 0.00463665 | 0.00221860 | 0.00685525 |

### Judge
| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| judge_generation | 80 | 131,164 | 23,369 | 154,533 | 0.00655820 | 0.00467380 | 0.01123200 |
| judge_retrieval | 160 | 202,204 | 31,070 | 233,274 | 0.01011020 | 0.00621400 | 0.01632420 |
| judge_total | 240 | 333,368 | 54,439 | 387,807 | 0.01666840 | 0.01088780 | 0.02755620 |

Run total cost usd = runtime total cost usd + judge total cost usd

Run total cost usd = 0.00685525 + 0.02755620 = 0.03441145

# Eval Run Report

## Run Metadata
- eval_run_id: `77ac1095-2dff-4f21-8e8e-1b64e32f63b8`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-10T15:13:42.916397+00:00`
- runtime_run_id: `2df55d1d-296f-4f5b-9cfc-707704d8fad0`
- completed_at: `2026-04-10T15:20:27.538908+00:00`
- request_count: `20`
- requests_evaluated: `20`
- generation_suite_versions: `{"answer_completeness": "v1", "answer_relevance": "v1", "correct_refusal": "v1", "groundedness": "v1"}`
- retrieval_suite_versions: `{"retrieval_relevance": "v1"}`

### Retriever
- kind: `Hybrid - bm25`
- embedding_model: `qwen3-embedding:0.6b`
- collection: `chunks_hybrid_fixed_qwen3`
- corpus_version: `v1`
- chunking_strategy: `fixed`
- top_k: `12`
- actual_chunks_returned: `mean=6.85, min=5, max=9`

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
| answer_completeness_mean | 0.9000 | 1.0000 | 1.0000 | 20 |
| groundedness_mean | 0.9000 | 1.0000 | 1.0000 | 20 |
| answer_relevance_mean | 0.9000 | 1.0000 | 1.0000 | 20 |
| correct_refusal_rate | 0.0000 | 0.0000 | 0.0000 | 20 |
| retrieval_relevance_mean | 0.4562 | 0.5000 | 1.0000 | 137 |
| retrieval_relevance_selected_mean | 0.5500 | 0.5000 | 1.0000 | 80 |
| retrieval_relevance_weighted_topk_mean | 0.5913 | 0.6105 | 0.6855 | 20 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 18 | 90.0% |
| answer_completeness | partial | 0 | 0.0% |
| answer_completeness | incomplete | 2 | 10.0% |
| groundedness | grounded | 18 | 90.0% |
| groundedness | partially_grounded | 0 | 0.0% |
| groundedness | ungrounded | 2 | 10.0% |
| answer_relevance | relevant | 18 | 90.0% |
| answer_relevance | partially_relevant | 0 | 0.0% |
| answer_relevance | irrelevant | 2 | 10.0% |
| correct_refusal | correct_refusal | 0 | 0.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 20 | 100.0% |

## Retrieval Quality

| set | Recall soft | Recall strict | MRR soft | MRR strict | nDCG |
|---|---:|---:|---:|---:|---:|
| retrieval@12 | 0.6400 | 0.8958 | 0.9750 | 0.9750 | 0.7737 |
| generation_context@4 | 0.4896 | 0.8167 | 0.9750 | 0.9750 | 0.8166 |

- retrieval_context_loss_soft: 0.1504
- retrieval_context_loss_strict: 0.0792
- avg_num_relevant_in_retrieval@12_soft: 3.9500
- avg_num_relevant_in_retrieval@12_strict: 2.5000
- avg_num_relevant_in_generation_context@4_soft: 3.0000
- avg_num_relevant_in_generation_context@4_strict: 2.3000

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for retrieval@12/generation_context@4 and soft/strict relevance.

| metric | retrieval@12_soft | retrieval@12_strict | generation_context@4_soft | generation_context@4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.9000 | 0.9000 | 0.9000 | 0.9000 |
| answer_completeness_given_relevant_context | 0.9000 | 0.9000 | 0.9000 | 0.9000 |
| answer_relevance_given_relevant_context | 0.9000 | 0.9000 | 0.9000 | 0.9000 |
| hallucination_rate_when_top1_irrelevant | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| success_rate_when_at_least_one_relevant_in_topk | 0.9000 | 0.9000 | 0.9000 | 0.9000 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0_

_Definitions: hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`1fc179d8-31f3-48a7-8b27-fd1faed55a42` score=`0.0000` trace_id=`4adb1d9d744765985233b9566902095c`
- request_id=`f16b62f3-55dd-4ea5-9ed6-d743488dd0c2` score=`0.0000` trace_id=`59c719fc8b28c5c34dfbca77ab237ef2`
- request_id=`019c4bbd-d9da-4def-afeb-4aa6e8bdf96a` score=`1.0000` trace_id=`eb0ce7aab829779b068206a337dae59e`
- request_id=`0804be0b-59ad-4f5f-9ffa-ea69d2e5cf33` score=`1.0000` trace_id=`6bcbe044c2d4c1f2b84ef603fa253db4`
- request_id=`246aef13-ca00-4511-9168-6d6d3a25904f` score=`1.0000` trace_id=`133cdc75f6e7a385f34626241ee73233`

### Lowest answer_completeness requests
- request_id=`1fc179d8-31f3-48a7-8b27-fd1faed55a42` score=`0.0000` trace_id=`4adb1d9d744765985233b9566902095c`
- request_id=`f16b62f3-55dd-4ea5-9ed6-d743488dd0c2` score=`0.0000` trace_id=`59c719fc8b28c5c34dfbca77ab237ef2`
- request_id=`019c4bbd-d9da-4def-afeb-4aa6e8bdf96a` score=`1.0000` trace_id=`eb0ce7aab829779b068206a337dae59e`
- request_id=`0804be0b-59ad-4f5f-9ffa-ea69d2e5cf33` score=`1.0000` trace_id=`6bcbe044c2d4c1f2b84ef603fa253db4`
- request_id=`246aef13-ca00-4511-9168-6d6d3a25904f` score=`1.0000` trace_id=`133cdc75f6e7a385f34626241ee73233`

## Token Usage

### Runtime
| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| runtime | 20 | 35,548 | 9,532 | 45,080 | 0.00177740 | 0.00190640 | 0.00368380 |

### Judge
| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| judge_generation | 80 | 78,310 | 26,154 | 104,464 | 0.00391550 | 0.00523080 | 0.00914630 |
| judge_retrieval | 137 | 87,393 | 34,511 | 121,904 | 0.00436965 | 0.00690220 | 0.01127185 |
| judge_total | 217 | 165,703 | 60,665 | 226,368 | 0.00828515 | 0.01213300 | 0.02041815 |

Run total cost usd = runtime total cost usd + judge total cost usd

Run total cost usd = 0.00368380 + 0.02041815 = 0.02410195

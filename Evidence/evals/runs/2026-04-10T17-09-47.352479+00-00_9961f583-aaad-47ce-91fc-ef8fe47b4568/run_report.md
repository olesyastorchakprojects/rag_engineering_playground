# Eval Run Report

## Run Metadata
- eval_run_id: `9961f583-aaad-47ce-91fc-ef8fe47b4568`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-10T17:09:47.352479+00:00`
- runtime_run_id: `8d4c9b1b-fdc3-4d1d-9d71-0dc8b3191331`
- completed_at: `2026-04-10T17:16:54.382818+00:00`
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
| answer_completeness_mean | 0.6500 | 1.0000 | 1.0000 | 20 |
| groundedness_mean | 0.6750 | 1.0000 | 1.0000 | 20 |
| answer_relevance_mean | 0.7000 | 1.0000 | 1.0000 | 20 |
| correct_refusal_rate | 0.0000 | 0.0000 | 0.0000 | 20 |
| retrieval_relevance_mean | 0.4562 | 0.5000 | 1.0000 | 137 |
| retrieval_relevance_selected_mean | 0.6062 | 0.5000 | 1.0000 | 80 |
| retrieval_relevance_weighted_topk_mean | 0.6235 | 0.6473 | 0.7296 | 20 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 13 | 65.0% |
| answer_completeness | partial | 0 | 0.0% |
| answer_completeness | incomplete | 7 | 35.0% |
| groundedness | grounded | 13 | 65.0% |
| groundedness | partially_grounded | 1 | 5.0% |
| groundedness | ungrounded | 6 | 30.0% |
| answer_relevance | relevant | 14 | 70.0% |
| answer_relevance | partially_relevant | 0 | 0.0% |
| answer_relevance | irrelevant | 6 | 30.0% |
| correct_refusal | correct_refusal | 0 | 0.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 20 | 100.0% |

## Retrieval Quality

| set | Recall soft | Recall strict | MRR soft | MRR strict | nDCG |
|---|---:|---:|---:|---:|---:|
| retrieval@12 | 0.6400 | 0.8958 | 1.0000 | 1.0000 | 0.7779 |
| generation_context@4 | 0.4875 | 0.8167 | 1.0000 | 1.0000 | 0.8222 |

- retrieval_context_loss_soft: 0.1525
- retrieval_context_loss_strict: 0.0792
- avg_num_relevant_in_retrieval@12_soft: 3.9500
- avg_num_relevant_in_retrieval@12_strict: 2.5000
- avg_num_relevant_in_generation_context@4_soft: 3.0000
- avg_num_relevant_in_generation_context@4_strict: 2.3000

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for retrieval@12/generation_context@4 and soft/strict relevance.

| metric | retrieval@12_soft | retrieval@12_strict | generation_context@4_soft | generation_context@4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.6750 | 0.6750 | 0.6750 | 0.6750 |
| answer_completeness_given_relevant_context | 0.6500 | 0.6500 | 0.6500 | 0.6500 |
| answer_relevance_given_relevant_context | 0.7000 | 0.7000 | 0.7000 | 0.7000 |
| hallucination_rate_when_top1_irrelevant | n/a | n/a | n/a | n/a |
| success_rate_when_at_least_one_relevant_in_topk | 0.6000 | 0.6000 | 0.6000 | 0.6000 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0_

_Definitions: hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`124bfb84-d714-44fd-b658-8276425d70be` score=`0.0000` trace_id=`cb682072d26355a2a4b66427952c1e54`
- request_id=`3f8d8001-d11e-47f8-a4de-5bc133248dc5` score=`0.0000` trace_id=`a3e130c87c36dae9998db3c4b8009c45`
- request_id=`528fd8a9-6c94-4a82-800a-25e1e3bf0430` score=`0.0000` trace_id=`b86711cb58cddad2a405a83b9d179a2e`
- request_id=`6212bf5c-1132-4e3c-acb0-4b3184e5ebca` score=`0.0000` trace_id=`0a1457d7c11fedd6ef0898e2d7e9b465`
- request_id=`8a7061f4-454a-4026-bc91-aff88461406f` score=`0.0000` trace_id=`8249efb9e89ee3f6bf35fd5e3e9bb36c`

### Lowest answer_completeness requests
- request_id=`124bfb84-d714-44fd-b658-8276425d70be` score=`0.0000` trace_id=`cb682072d26355a2a4b66427952c1e54`
- request_id=`3e92a614-69f8-4880-a9c5-5dfdc8b67077` score=`0.0000` trace_id=`d5c4bca600fd82e045041f1edb31a534`
- request_id=`3f8d8001-d11e-47f8-a4de-5bc133248dc5` score=`0.0000` trace_id=`a3e130c87c36dae9998db3c4b8009c45`
- request_id=`528fd8a9-6c94-4a82-800a-25e1e3bf0430` score=`0.0000` trace_id=`b86711cb58cddad2a405a83b9d179a2e`
- request_id=`6212bf5c-1132-4e3c-acb0-4b3184e5ebca` score=`0.0000` trace_id=`0a1457d7c11fedd6ef0898e2d7e9b465`

## Token Usage

### Runtime
| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| runtime | 20 | 35,432 | 9,992 | 45,424 | 0.00177160 | 0.00199840 | 0.00377000 |

### Judge
| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| judge_generation | 80 | 76,310 | 22,829 | 99,139 | 0.00381550 | 0.00456580 | 0.00838130 |
| judge_retrieval | 137 | 87,393 | 33,960 | 121,353 | 0.00436965 | 0.00679200 | 0.01116165 |
| judge_total | 217 | 163,703 | 56,789 | 220,492 | 0.00818515 | 0.01135780 | 0.01954295 |

Run total cost usd = runtime total cost usd + judge total cost usd

Run total cost usd = 0.00377000 + 0.01954295 = 0.02331295

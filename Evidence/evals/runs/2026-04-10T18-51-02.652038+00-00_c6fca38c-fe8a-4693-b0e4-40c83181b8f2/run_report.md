# Eval Run Report

## Run Metadata
- eval_run_id: `c6fca38c-fe8a-4693-b0e4-40c83181b8f2`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-10T18:51:02.652038+00:00`
- runtime_run_id: `bf3e92f3-3f0c-4fde-a8aa-e2840cbb95fe`
- completed_at: `2026-04-10T19:02:24.844967+00:00`
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
| answer_completeness_mean | 0.7250 | 1.0000 | 1.0000 | 20 |
| groundedness_mean | 0.8000 | 1.0000 | 1.0000 | 20 |
| answer_relevance_mean | 0.8000 | 1.0000 | 1.0000 | 20 |
| correct_refusal_rate | 0.0000 | 0.0000 | 0.0000 | 20 |
| retrieval_relevance_mean | 0.2344 | 0.0000 | 1.0000 | 160 |
| retrieval_relevance_selected_mean | 0.4375 | 0.5000 | 1.0000 | 80 |
| retrieval_relevance_weighted_topk_mean | 0.4579 | 0.4599 | 0.5672 | 20 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 14 | 70.0% |
| answer_completeness | partial | 1 | 5.0% |
| answer_completeness | incomplete | 5 | 25.0% |
| groundedness | grounded | 16 | 80.0% |
| groundedness | partially_grounded | 0 | 0.0% |
| groundedness | ungrounded | 4 | 20.0% |
| answer_relevance | relevant | 16 | 80.0% |
| answer_relevance | partially_relevant | 0 | 0.0% |
| answer_relevance | irrelevant | 4 | 20.0% |
| correct_refusal | correct_refusal | 0 | 0.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 20 | 100.0% |

## Retrieval Quality

| set | Recall soft | Recall strict | MRR soft | MRR strict | nDCG |
|---|---:|---:|---:|---:|---:|
| retrieval@12 | 0.5500 | 0.9500 | 0.8000 | 0.7306 | 0.5985 |
| generation_context@4 | 0.5100 | 0.9500 | 1.0000 | 0.9667 | 0.7865 |

- retrieval_context_loss_soft: 0.0400
- retrieval_context_loss_strict: 0.0000
- avg_num_relevant_in_retrieval@12_soft: 2.7500
- avg_num_relevant_in_retrieval@12_strict: 1.3500
- avg_num_relevant_in_generation_context@4_soft: 2.5500
- avg_num_relevant_in_generation_context@4_strict: 1.3500

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for retrieval@12/generation_context@4 and soft/strict relevance.

| metric | retrieval@12_soft | retrieval@12_strict | generation_context@4_soft | generation_context@4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| answer_completeness_given_relevant_context | 0.7250 | 0.7250 | 0.7250 | 0.7250 |
| answer_relevance_given_relevant_context | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| hallucination_rate_when_top1_irrelevant | 0.2500 | 0.2000 | n/a | 0.0000 |
| success_rate_when_at_least_one_relevant_in_topk | 0.7000 | 0.7000 | 0.7000 | 0.7000 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0_

_Definitions: hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`1430d866-0e84-4190-9749-47b8cc497225` score=`0.0000` trace_id=`3d0771d2b3cdebc74ba07d98b9066681`
- request_id=`7fdf1ee6-7a24-48f4-be5a-cbe0b6e8d7f5` score=`0.0000` trace_id=`f6cfb3d55f2df4ed0258f6848b33cce4`
- request_id=`c6e5dc4a-c551-4469-84fb-b968130fb66c` score=`0.0000` trace_id=`bbd7b78ae3c7ffb5b9bcf850f85a4509`
- request_id=`fc5baef3-3093-435d-b7ca-86bf5d2d88bd` score=`0.0000` trace_id=`2d77b3202860a6a9d58e36a28407488f`
- request_id=`063d2230-d663-4548-8934-7e215b281aba` score=`1.0000` trace_id=`90e1c6f6e4d81e2133aa25a5f304187b`

### Lowest answer_completeness requests
- request_id=`063d2230-d663-4548-8934-7e215b281aba` score=`0.0000` trace_id=`90e1c6f6e4d81e2133aa25a5f304187b`
- request_id=`1430d866-0e84-4190-9749-47b8cc497225` score=`0.0000` trace_id=`3d0771d2b3cdebc74ba07d98b9066681`
- request_id=`7fdf1ee6-7a24-48f4-be5a-cbe0b6e8d7f5` score=`0.0000` trace_id=`f6cfb3d55f2df4ed0258f6848b33cce4`
- request_id=`c6e5dc4a-c551-4469-84fb-b968130fb66c` score=`0.0000` trace_id=`bbd7b78ae3c7ffb5b9bcf850f85a4509`
- request_id=`fc5baef3-3093-435d-b7ca-86bf5d2d88bd` score=`0.0000` trace_id=`2d77b3202860a6a9d58e36a28407488f`

## Token Usage

### Runtime
| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| runtime | 20 | 56,183 | 10,280 | 66,463 | 0.00280915 | 0.00205600 | 0.00486515 |

### Judge
| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| judge_generation | 80 | 97,175 | 26,421 | 123,596 | 0.00485875 | 0.00528420 | 0.01014295 |
| judge_retrieval | 160 | 202,204 | 30,763 | 232,967 | 0.01011020 | 0.00615260 | 0.01626280 |
| judge_total | 240 | 299,379 | 57,184 | 356,563 | 0.01496895 | 0.01143680 | 0.02640575 |

Run total cost usd = runtime total cost usd + judge total cost usd

Run total cost usd = 0.00486515 + 0.02640575 = 0.03127090

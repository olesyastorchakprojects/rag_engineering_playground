# Eval Run Report

## Run Metadata
- eval_run_id: `0d85b984-5f15-4529-a4b2-9ac11f496372`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-10T19:42:16.271737+00:00`
- runtime_run_id: `109b1205-c40d-44ed-b5e4-fda04816d589`
- completed_at: `2026-04-10T19:51:56.052527+00:00`
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
| answer_completeness_mean | 0.7250 | 1.0000 | 1.0000 | 20 |
| groundedness_mean | 0.7250 | 1.0000 | 1.0000 | 20 |
| answer_relevance_mean | 0.7500 | 1.0000 | 1.0000 | 20 |
| correct_refusal_rate | 0.0000 | 0.0000 | 0.0000 | 20 |
| retrieval_relevance_mean | 0.4599 | 0.5000 | 1.0000 | 137 |
| retrieval_relevance_selected_mean | 0.6188 | 0.5000 | 1.0000 | 80 |
| retrieval_relevance_weighted_topk_mean | 0.6284 | 0.6331 | 0.7313 | 20 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 14 | 70.0% |
| answer_completeness | partial | 1 | 5.0% |
| answer_completeness | incomplete | 5 | 25.0% |
| groundedness | grounded | 14 | 70.0% |
| groundedness | partially_grounded | 1 | 5.0% |
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
| retrieval@12 | 0.6400 | 0.8958 | 0.9750 | 0.9750 | 0.7700 |
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
| groundedness_given_relevant_context | 0.7250 | 0.7250 | 0.7250 | 0.7250 |
| answer_completeness_given_relevant_context | 0.7250 | 0.7250 | 0.7250 | 0.7250 |
| answer_relevance_given_relevant_context | 0.7500 | 0.7500 | 0.7500 | 0.7500 |
| hallucination_rate_when_top1_irrelevant | 0.0000 | 0.0000 | n/a | n/a |
| success_rate_when_at_least_one_relevant_in_topk | 0.7000 | 0.7000 | 0.7000 | 0.7000 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0_

_Definitions: hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`0d0a5423-d35c-4f44-9815-3a6d2f19bd75` score=`0.0000` trace_id=`4ec2a10beb6e64aa19445f7d803c4b66`
- request_id=`23f63c26-e906-4885-a369-f3cbbfb6ed10` score=`0.0000` trace_id=`75fc830b86a628f0496f20e0ee455e4f`
- request_id=`6332e026-1e64-4183-9c80-6ee9b12fbdf6` score=`0.0000` trace_id=`8a8683729150322c660c45e6b29a9a80`
- request_id=`69f84728-4c11-46d9-a5ce-75bc13bc4506` score=`0.0000` trace_id=`5f29ed8fec2b9697280cb942e11ec907`
- request_id=`b0319984-c1f6-45f9-b241-c9ba3fe91036` score=`0.0000` trace_id=`273001bf8f27fbc93e0f5ea2f331bbd3`

### Lowest answer_completeness requests
- request_id=`0d0a5423-d35c-4f44-9815-3a6d2f19bd75` score=`0.0000` trace_id=`4ec2a10beb6e64aa19445f7d803c4b66`
- request_id=`23f63c26-e906-4885-a369-f3cbbfb6ed10` score=`0.0000` trace_id=`75fc830b86a628f0496f20e0ee455e4f`
- request_id=`6332e026-1e64-4183-9c80-6ee9b12fbdf6` score=`0.0000` trace_id=`8a8683729150322c660c45e6b29a9a80`
- request_id=`69f84728-4c11-46d9-a5ce-75bc13bc4506` score=`0.0000` trace_id=`5f29ed8fec2b9697280cb942e11ec907`
- request_id=`b0319984-c1f6-45f9-b241-c9ba3fe91036` score=`0.0000` trace_id=`273001bf8f27fbc93e0f5ea2f331bbd3`

## Token Usage

### Runtime
| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| runtime | 20 | 35,432 | 9,790 | 45,222 | 0.00177160 | 0.00195800 | 0.00372960 |

### Judge
| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| judge_generation | 80 | 77,242 | 25,149 | 102,391 | 0.00386210 | 0.00502980 | 0.00889190 |
| judge_retrieval | 137 | 87,393 | 34,354 | 121,747 | 0.00436965 | 0.00687080 | 0.01124045 |
| judge_total | 217 | 164,635 | 59,503 | 224,138 | 0.00823175 | 0.01190060 | 0.02013235 |

Run total cost usd = runtime total cost usd + judge total cost usd

Run total cost usd = 0.00372960 + 0.02013235 = 0.02386195

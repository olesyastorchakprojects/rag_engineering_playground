# Eval Run Report

## Run Metadata
- eval_run_id: `087199f2-82fd-45b5-b2ad-07632aa017de`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-10T19:25:53.240813+00:00`
- runtime_run_id: `549bb870-700a-48d6-8ab6-f6d260a177fa`
- completed_at: `2026-04-10T19:34:18.264210+00:00`
- request_count: `20`
- requests_evaluated: `20`
- generation_suite_versions: `{"answer_completeness": "v1", "answer_relevance": "v1", "correct_refusal": "v1", "groundedness": "v1"}`
- retrieval_suite_versions: `{"retrieval_relevance": "v1"}`

### Retriever
- kind: `Hybrid - bow`
- embedding_model: `qwen3-embedding:0.6b`
- collection: `chunks_hybrid_fixed_qwen3`
- corpus_version: `v1`
- chunking_strategy: `fixed`
- top_k: `12`
- actual_chunks_returned: `mean=7.50, min=6, max=9`

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
| retrieval_relevance_mean | 0.3333 | 0.5000 | 1.0000 | 150 |
| retrieval_relevance_selected_mean | 0.5625 | 0.5000 | 1.0000 | 80 |
| retrieval_relevance_weighted_topk_mean | 0.5573 | 0.5464 | 0.6910 | 20 |

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
| retrieval@12 | 0.5582 | 0.7833 | 0.9417 | 0.9417 | 0.6650 |
| generation_context@4 | 0.5058 | 0.7833 | 1.0000 | 1.0000 | 0.8213 |

- retrieval_context_loss_soft: 0.0524
- retrieval_context_loss_strict: 0.0000
- avg_num_relevant_in_retrieval@12_soft: 3.4500
- avg_num_relevant_in_retrieval@12_strict: 2.2500
- avg_num_relevant_in_generation_context@4_soft: 3.1000
- avg_num_relevant_in_generation_context@4_strict: 2.2500

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for retrieval@12/generation_context@4 and soft/strict relevance.

| metric | retrieval@12_soft | retrieval@12_strict | generation_context@4_soft | generation_context@4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.7500 | 0.7500 | 0.7500 | 0.7500 |
| answer_completeness_given_relevant_context | 0.7500 | 0.7500 | 0.7500 | 0.7500 |
| answer_relevance_given_relevant_context | 0.7500 | 0.7500 | 0.7500 | 0.7500 |
| hallucination_rate_when_top1_irrelevant | 0.5000 | 0.5000 | n/a | n/a |
| success_rate_when_at_least_one_relevant_in_topk | 0.7500 | 0.7500 | 0.7500 | 0.7500 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0_

_Definitions: hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`840e5c6d-db88-46f4-8aba-581bba9ca473` score=`0.0000` trace_id=`bed60061b77f9eb3b0ca535ba6795ba1`
- request_id=`a1f06825-4270-4aad-b0e7-0ddbb448db99` score=`0.0000` trace_id=`d56145eeb59d90de1c7c098ae3779c21`
- request_id=`ebbb734f-c2eb-43d4-ab79-1ab538d1659b` score=`0.0000` trace_id=`2277b03dcad6074e2158c5ea6a23e47c`
- request_id=`efac2343-947f-4adb-b3b7-846b019e066b` score=`0.0000` trace_id=`50dc4503ba011b76fdc5e20557091659`
- request_id=`fcae7391-a95e-4af0-af6a-013d496339b4` score=`0.0000` trace_id=`72a8665b82a4e32751bbcd57d17bdbd8`

### Lowest answer_completeness requests
- request_id=`840e5c6d-db88-46f4-8aba-581bba9ca473` score=`0.0000` trace_id=`bed60061b77f9eb3b0ca535ba6795ba1`
- request_id=`a1f06825-4270-4aad-b0e7-0ddbb448db99` score=`0.0000` trace_id=`d56145eeb59d90de1c7c098ae3779c21`
- request_id=`ebbb734f-c2eb-43d4-ab79-1ab538d1659b` score=`0.0000` trace_id=`2277b03dcad6074e2158c5ea6a23e47c`
- request_id=`efac2343-947f-4adb-b3b7-846b019e066b` score=`0.0000` trace_id=`50dc4503ba011b76fdc5e20557091659`
- request_id=`fcae7391-a95e-4af0-af6a-013d496339b4` score=`0.0000` trace_id=`72a8665b82a4e32751bbcd57d17bdbd8`

## Token Usage

### Runtime
| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| runtime | 20 | 35,615 | 11,792 | 47,407 | 0.00178075 | 0.00235840 | 0.00413915 |

### Judge
| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| judge_generation | 80 | 77,060 | 23,471 | 100,531 | 0.00385300 | 0.00469420 | 0.00854720 |
| judge_retrieval | 150 | 96,558 | 31,282 | 127,840 | 0.00482790 | 0.00625640 | 0.01108430 |
| judge_total | 230 | 173,618 | 54,753 | 228,371 | 0.00868090 | 0.01095060 | 0.01963150 |

Run total cost usd = runtime total cost usd + judge total cost usd

Run total cost usd = 0.00413915 + 0.01963150 = 0.02377065

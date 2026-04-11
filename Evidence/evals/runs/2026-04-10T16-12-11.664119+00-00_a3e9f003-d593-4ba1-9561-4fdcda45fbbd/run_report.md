# Eval Run Report

## Run Metadata
- eval_run_id: `a3e9f003-d593-4ba1-9561-4fdcda45fbbd`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-10T16:12:11.664119+00:00`
- runtime_run_id: `798667c7-a9aa-410d-a39d-9f2d2024164e`
- completed_at: `2026-04-10T16:25:39.850557+00:00`
- request_count: `20`
- requests_evaluated: `20`
- generation_suite_versions: `{"answer_completeness": "v1", "answer_relevance": "v1", "correct_refusal": "v1", "groundedness": "v1"}`
- retrieval_suite_versions: `{"retrieval_relevance": "v1"}`

### Retriever
- kind: `Dense`
- embedding_model: `qwen3-embedding:0.6b`
- collection: `chunks_dense_qwen3_fixed`
- corpus_version: `v2`
- chunking_strategy: `fixed`
- top_k: `12`
- actual_chunks_returned: `mean=12.00, min=12, max=12`

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
| answer_completeness_mean | 0.7000 | 1.0000 | 1.0000 | 20 |
| groundedness_mean | 0.7250 | 1.0000 | 1.0000 | 20 |
| answer_relevance_mean | 0.7500 | 1.0000 | 1.0000 | 20 |
| correct_refusal_rate | 0.0000 | 0.0000 | 0.0000 | 20 |
| retrieval_relevance_mean | 0.3083 | 0.5000 | 0.5000 | 240 |
| retrieval_relevance_selected_mean | 0.6062 | 0.5000 | 1.0000 | 80 |
| retrieval_relevance_weighted_topk_mean | 0.5362 | 0.5559 | 0.6315 | 20 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 14 | 70.0% |
| answer_completeness | partial | 0 | 0.0% |
| answer_completeness | incomplete | 6 | 30.0% |
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
| retrieval@12 | 0.7697 | 0.9042 | 1.0000 | 1.0000 | 0.8201 |
| generation_context@4 | 0.5130 | 0.7833 | 1.0000 | 1.0000 | 0.8272 |

- retrieval_context_loss_soft: 0.2567
- retrieval_context_loss_strict: 0.1208
- avg_num_relevant_in_retrieval@12_soft: 4.7500
- avg_num_relevant_in_retrieval@12_strict: 2.6000
- avg_num_relevant_in_generation_context@4_soft: 3.1500
- avg_num_relevant_in_generation_context@4_strict: 2.2500

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for retrieval@12/generation_context@4 and soft/strict relevance.

| metric | retrieval@12_soft | retrieval@12_strict | generation_context@4_soft | generation_context@4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.7250 | 0.7250 | 0.7250 | 0.7250 |
| answer_completeness_given_relevant_context | 0.7000 | 0.7000 | 0.7000 | 0.7000 |
| answer_relevance_given_relevant_context | 0.7500 | 0.7500 | 0.7500 | 0.7500 |
| hallucination_rate_when_top1_irrelevant | n/a | n/a | n/a | n/a |
| success_rate_when_at_least_one_relevant_in_topk | 0.7000 | 0.7000 | 0.7000 | 0.7000 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0_

_Definitions: hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`019d7006-dbec-49fe-9f1c-5047f2889c9e` score=`0.0000` trace_id=`4a06d80b0a53a02bbdc58d1bcaef3798`
- request_id=`5827317c-22db-4e77-9da6-59f40b63b5f5` score=`0.0000` trace_id=`763eb5550f028be2ceead80873b1c954`
- request_id=`a64179cd-0789-42b4-94c1-121fb3274ed7` score=`0.0000` trace_id=`91993a8eef4a0b6253404f4c5b95ed2b`
- request_id=`b687aba7-05cf-4458-8878-cb2467d051b8` score=`0.0000` trace_id=`1e407b718e1d1c080af0c50907a574df`
- request_id=`e49c0b93-ddfa-476a-aa6e-c1235b6c14cb` score=`0.0000` trace_id=`5dceec55373e83e55d606387a39b7341`

### Lowest answer_completeness requests
- request_id=`019d7006-dbec-49fe-9f1c-5047f2889c9e` score=`0.0000` trace_id=`4a06d80b0a53a02bbdc58d1bcaef3798`
- request_id=`5827317c-22db-4e77-9da6-59f40b63b5f5` score=`0.0000` trace_id=`763eb5550f028be2ceead80873b1c954`
- request_id=`a64179cd-0789-42b4-94c1-121fb3274ed7` score=`0.0000` trace_id=`91993a8eef4a0b6253404f4c5b95ed2b`
- request_id=`af9b7d40-961e-4f25-8ed1-274030147821` score=`0.0000` trace_id=`f856c72cbe3adffa7bd6457d5ae3fc99`
- request_id=`b687aba7-05cf-4458-8878-cb2467d051b8` score=`0.0000` trace_id=`1e407b718e1d1c080af0c50907a574df`

## Token Usage

### Runtime
| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| runtime | 20 | 35,447 | 9,227 | 44,674 | 0.00177235 | 0.00184540 | 0.00361775 |

### Judge
| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| judge_generation | 80 | 75,363 | 25,224 | 100,587 | 0.00376815 | 0.00504480 | 0.00881295 |
| judge_retrieval | 240 | 152,952 | 54,768 | 207,720 | 0.00764760 | 0.01095360 | 0.01860120 |
| judge_total | 320 | 228,315 | 79,992 | 308,307 | 0.01141575 | 0.01599840 | 0.02741415 |

Run total cost usd = runtime total cost usd + judge total cost usd

Run total cost usd = 0.00361775 + 0.02741415 = 0.03103190

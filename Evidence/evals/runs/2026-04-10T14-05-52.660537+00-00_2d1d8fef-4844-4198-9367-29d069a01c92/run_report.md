# Eval Run Report

## Run Metadata
- eval_run_id: `2d1d8fef-4844-4198-9367-29d069a01c92`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-10T14:05:52.660537+00:00`
- runtime_run_id: `2ca709ff-59a2-4cdd-ab93-5b02678133fa`
- completed_at: `2026-04-10T14:16:12.351123+00:00`
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
| answer_completeness_mean | 0.8000 | 1.0000 | 1.0000 | 20 |
| groundedness_mean | 0.8500 | 1.0000 | 1.0000 | 20 |
| answer_relevance_mean | 0.8000 | 1.0000 | 1.0000 | 20 |
| correct_refusal_rate | 0.0000 | 0.0000 | 0.0000 | 20 |
| retrieval_relevance_mean | 0.3000 | 0.0000 | 1.0000 | 240 |
| retrieval_relevance_selected_mean | 0.5625 | 0.5000 | 1.0000 | 80 |
| retrieval_relevance_weighted_topk_mean | 0.5121 | 0.5290 | 0.6671 | 20 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 16 | 80.0% |
| answer_completeness | partial | 0 | 0.0% |
| answer_completeness | incomplete | 4 | 20.0% |
| groundedness | grounded | 17 | 85.0% |
| groundedness | partially_grounded | 0 | 0.0% |
| groundedness | ungrounded | 3 | 15.0% |
| answer_relevance | relevant | 16 | 80.0% |
| answer_relevance | partially_relevant | 0 | 0.0% |
| answer_relevance | irrelevant | 4 | 20.0% |
| correct_refusal | correct_refusal | 0 | 0.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 20 | 100.0% |

## Retrieval Quality

| set | Recall soft | Recall strict | MRR soft | MRR strict | nDCG |
|---|---:|---:|---:|---:|---:|
| retrieval@12 | 0.7697 | 0.9042 | 1.0000 | 1.0000 | 0.8201 |
| generation_context@4 | 0.4887 | 0.7708 | 1.0000 | 1.0000 | 0.8076 |

- retrieval_context_loss_soft: 0.2810
- retrieval_context_loss_strict: 0.1333
- avg_num_relevant_in_retrieval@12_soft: 4.7500
- avg_num_relevant_in_retrieval@12_strict: 2.6000
- avg_num_relevant_in_generation_context@4_soft: 3.0000
- avg_num_relevant_in_generation_context@4_strict: 2.2000

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for retrieval@12/generation_context@4 and soft/strict relevance.

| metric | retrieval@12_soft | retrieval@12_strict | generation_context@4_soft | generation_context@4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.8500 | 0.8500 | 0.8500 | 0.8500 |
| answer_completeness_given_relevant_context | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| answer_relevance_given_relevant_context | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| hallucination_rate_when_top1_irrelevant | n/a | n/a | n/a | n/a |
| success_rate_when_at_least_one_relevant_in_topk | 0.8000 | 0.8000 | 0.8000 | 0.8000 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0_

_Definitions: hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`82334b0a-6b2e-43ff-8335-efbf0e9357af` score=`0.0000` trace_id=`ceb5fbced5e2827b498352c92f32f8a2`
- request_id=`c352ab22-3aaf-4a8c-8abc-df3a56e5ecf2` score=`0.0000` trace_id=`8f33eab61ed683049628a270746ae700`
- request_id=`faa28cbe-5733-4479-97e0-a7adad1b1933` score=`0.0000` trace_id=`58935d69cceed25d10666cd06f10fba7`
- request_id=`0e34a3e9-f829-4c1b-9f25-51b0cf37d2b2` score=`1.0000` trace_id=`418e63e317af623324ffa48e9e88df30`
- request_id=`16d02824-3d8e-4527-9cdb-60bbd3382aca` score=`1.0000` trace_id=`095f6abe01bb5ae4d8a7c278d668b0c6`

### Lowest answer_completeness requests
- request_id=`82334b0a-6b2e-43ff-8335-efbf0e9357af` score=`0.0000` trace_id=`ceb5fbced5e2827b498352c92f32f8a2`
- request_id=`c352ab22-3aaf-4a8c-8abc-df3a56e5ecf2` score=`0.0000` trace_id=`8f33eab61ed683049628a270746ae700`
- request_id=`cbdc3846-26a2-4558-9388-a402edec8f3f` score=`0.0000` trace_id=`02866dc1923d184485577c4022cfe2e5`
- request_id=`faa28cbe-5733-4479-97e0-a7adad1b1933` score=`0.0000` trace_id=`58935d69cceed25d10666cd06f10fba7`
- request_id=`0e34a3e9-f829-4c1b-9f25-51b0cf37d2b2` score=`1.0000` trace_id=`418e63e317af623324ffa48e9e88df30`

## Token Usage

### Runtime
| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| runtime | 20 | 35,580 | 9,233 | 44,813 | 0.00177900 | 0.00184660 | 0.00362560 |

### Judge
| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| judge_generation | 80 | 77,976 | 22,436 | 100,412 | 0.00389880 | 0.00448720 | 0.00838600 |
| judge_retrieval | 240 | 152,952 | 54,824 | 207,776 | 0.00764760 | 0.01096480 | 0.01861240 |
| judge_total | 320 | 230,928 | 77,260 | 308,188 | 0.01154640 | 0.01545200 | 0.02699840 |

Run total cost usd = runtime total cost usd + judge total cost usd

Run total cost usd = 0.00362560 + 0.02699840 = 0.03062400

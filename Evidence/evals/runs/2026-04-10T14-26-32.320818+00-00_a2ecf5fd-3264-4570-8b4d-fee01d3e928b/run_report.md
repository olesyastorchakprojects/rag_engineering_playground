# Eval Run Report

## Run Metadata
- eval_run_id: `a2ecf5fd-3264-4570-8b4d-fee01d3e928b`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-10T14:26:32.320818+00:00`
- runtime_run_id: `65c3a20f-2daa-4d11-8444-81f30176cf6f`
- completed_at: `2026-04-10T14:40:39.048216+00:00`
- request_count: `20`
- requests_evaluated: `20`
- generation_suite_versions: `{"answer_completeness": "v1", "answer_relevance": "v1", "correct_refusal": "v1", "groundedness": "v1"}`
- retrieval_suite_versions: `{"retrieval_relevance": "v1"}`

### Retriever
- kind: `Dense`
- embedding_model: `qwen3-embedding:0.6b`
- collection: `chunks_dense_qwen3`
- corpus_version: `v1`
- chunking_strategy: `structural`
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
| groundedness_mean | 0.9000 | 1.0000 | 1.0000 | 20 |
| answer_relevance_mean | 0.8500 | 1.0000 | 1.0000 | 20 |
| correct_refusal_rate | 0.0000 | 0.0000 | 0.0000 | 20 |
| retrieval_relevance_mean | 0.2396 | 0.0000 | 0.5000 | 240 |
| retrieval_relevance_selected_mean | 0.4375 | 0.5000 | 1.0000 | 80 |
| retrieval_relevance_weighted_topk_mean | 0.4391 | 0.4350 | 0.5241 | 20 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 16 | 80.0% |
| answer_completeness | partial | 0 | 0.0% |
| answer_completeness | incomplete | 4 | 20.0% |
| groundedness | grounded | 18 | 90.0% |
| groundedness | partially_grounded | 0 | 0.0% |
| groundedness | ungrounded | 2 | 10.0% |
| answer_relevance | relevant | 17 | 85.0% |
| answer_relevance | partially_relevant | 0 | 0.0% |
| answer_relevance | irrelevant | 3 | 15.0% |
| correct_refusal | correct_refusal | 0 | 0.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 20 | 100.0% |

## Retrieval Quality

| set | Recall soft | Recall strict | MRR soft | MRR strict | nDCG |
|---|---:|---:|---:|---:|---:|
| retrieval@12 | 0.7700 | 1.0000 | 1.0000 | 0.9625 | 0.8258 |
| generation_context@4 | 0.5200 | 0.9500 | 1.0000 | 0.9625 | 0.7899 |

- retrieval_context_loss_soft: 0.2500
- retrieval_context_loss_strict: 0.0500
- avg_num_relevant_in_retrieval@12_soft: 3.8500
- avg_num_relevant_in_retrieval@12_strict: 1.4500
- avg_num_relevant_in_generation_context@4_soft: 2.6000
- avg_num_relevant_in_generation_context@4_strict: 1.3500

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for retrieval@12/generation_context@4 and soft/strict relevance.

| metric | retrieval@12_soft | retrieval@12_strict | generation_context@4_soft | generation_context@4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.9000 | 0.9000 | 0.9000 | 0.9000 |
| answer_completeness_given_relevant_context | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| answer_relevance_given_relevant_context | 0.8500 | 0.8500 | 0.8500 | 0.8500 |
| hallucination_rate_when_top1_irrelevant | n/a | 0.0000 | n/a | 0.0000 |
| success_rate_when_at_least_one_relevant_in_topk | 0.8000 | 0.8000 | 0.8000 | 0.8000 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0_

_Definitions: hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`6600bd91-b15e-496c-a2a8-5f222f60be19` score=`0.0000` trace_id=`512d768cd8af562e53bb631785db24d3`
- request_id=`9dc2f21e-d5b7-4393-aa03-f8b610dbfc94` score=`0.0000` trace_id=`4e6513677f028a9472208802429a0090`
- request_id=`008ee95c-adf5-48a9-a46c-20bedfca6a07` score=`1.0000` trace_id=`a873c18e72f3d78f3072ae9f8f294fda`
- request_id=`02077c01-a26e-4d7b-aea0-0562df76b699` score=`1.0000` trace_id=`402003c6b9b933b8bbf0a4a8dc58afc2`
- request_id=`10aabd3c-1ff3-4a63-92cd-8e0e7e137247` score=`1.0000` trace_id=`0e1e6f6e7b43040b5365f75830b6d113`

### Lowest answer_completeness requests
- request_id=`13b5d845-9063-487a-b3b2-d21620fd25f1` score=`0.0000` trace_id=`fad4bc99e29a985a960231a889549b5c`
- request_id=`6600bd91-b15e-496c-a2a8-5f222f60be19` score=`0.0000` trace_id=`512d768cd8af562e53bb631785db24d3`
- request_id=`8f9724de-ec47-4cce-8517-e9b1a93e85d9` score=`0.0000` trace_id=`7c9d32516d2c3fd3be6ac2b5fd2fc72a`
- request_id=`9dc2f21e-d5b7-4393-aa03-f8b610dbfc94` score=`0.0000` trace_id=`4e6513677f028a9472208802429a0090`
- request_id=`008ee95c-adf5-48a9-a46c-20bedfca6a07` score=`1.0000` trace_id=`a873c18e72f3d78f3072ae9f8f294fda`

## Token Usage

### Runtime
| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| runtime | 20 | 47,045 | 9,673 | 56,718 | 0.00235225 | 0.00193460 | 0.00428685 |

### Judge
| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| judge_generation | 80 | 88,148 | 23,622 | 111,770 | 0.00440740 | 0.00472440 | 0.00913180 |
| judge_retrieval | 240 | 185,923 | 48,629 | 234,552 | 0.00929615 | 0.00972580 | 0.01902195 |
| judge_total | 320 | 274,071 | 72,251 | 346,322 | 0.01370355 | 0.01445020 | 0.02815375 |

Run total cost usd = runtime total cost usd + judge total cost usd

Run total cost usd = 0.00428685 + 0.02815375 = 0.03244060

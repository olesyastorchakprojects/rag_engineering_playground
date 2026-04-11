# Eval Run Report

## Run Metadata
- run_id: `0dced961-985e-435e-b06d-6b20d963526c`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-08T13:22:15.337790+00:00`
- completed_at: `2026-04-08T13:25:52.885782+00:00`
- request_count: `5`
- requests_evaluated: `5`
- generation_suite_versions: `{"answer_completeness": "v1", "answer_relevance": "v1", "correct_refusal": "v1", "groundedness": "v1"}`
- retrieval_suite_versions: `{"retrieval_relevance": "v1"}`

### Retriever
- kind: `Dense`
- embedding_model: `qwen3-embedding:0.6b`
- collection: `chunks_dense_qwen3_fixed`
- corpus_version: `v2`
- chunking_strategy: `fixed`
- top_k: `12`

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
| answer_completeness_mean | 0.8000 | 1.0000 | 1.0000 | 5 |
| groundedness_mean | 0.8000 | 1.0000 | 1.0000 | 5 |
| answer_relevance_mean | 0.8000 | 1.0000 | 1.0000 | 5 |
| correct_refusal_rate | 0.0000 | 0.0000 | 0.0000 | 5 |
| retrieval_relevance_mean | 0.2667 | 0.0000 | 1.0000 | 60 |
| retrieval_relevance_selected_mean | 0.4750 | 0.5000 | 1.0000 | 20 |
| retrieval_relevance_weighted_topk_mean | 0.4927 | 0.4565 | 0.6424 | 5 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 4 | 80.0% |
| answer_completeness | partial | 0 | 0.0% |
| answer_completeness | incomplete | 1 | 20.0% |
| groundedness | grounded | 4 | 80.0% |
| groundedness | partially_grounded | 0 | 0.0% |
| groundedness | ungrounded | 1 | 20.0% |
| answer_relevance | relevant | 4 | 80.0% |
| answer_relevance | partially_relevant | 0 | 0.0% |
| answer_relevance | irrelevant | 1 | 20.0% |
| correct_refusal | correct_refusal | 0 | 0.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 5 | 100.0% |

## Retrieval Quality

| set | Recall soft | Recall strict | MRR soft | MRR strict | nDCG |
|---|---:|---:|---:|---:|---:|
| top12 | 0.5200 | 0.8833 | 1.0000 | 1.0000 | 0.6872 |
| top4 | 0.3000 | 0.7667 | 1.0000 | 1.0000 | 0.7959 |

- retrieval_context_loss_soft: 0.2200
- retrieval_context_loss_strict: 0.1167
- avg_num_relevant_in_top12_soft: 5.2000
- avg_num_relevant_in_top12_strict: 2.6000
- avg_num_relevant_in_top4_soft: 3.0000
- avg_num_relevant_in_top4_strict: 2.2000

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for top12/top4 and soft/strict relevance.

| metric | top12_soft | top12_strict | top4_soft | top4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| answer_completeness_given_relevant_context | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| answer_relevance_given_relevant_context | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| hallucination_rate_when_top1_irrelevant | n/a | n/a | n/a | n/a |
| success_rate_when_at_least_one_relevant_in_topk | 0.8000 | 0.8000 | 0.8000 | 0.8000 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0; hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`da32ec0e-0803-4ed6-b8f1-ffb5f1e21f86` score=`0.0000` trace_id=`c307ae834902e540fc94b01c1c090a75`
- request_id=`13c8fffb-a1cb-47ba-b039-52de9ae05b7f` score=`1.0000` trace_id=`fb2c70d0c7ffe0210e78278e1695f79a`
- request_id=`49d392ba-65b8-4450-9042-90f0f7e8df0b` score=`1.0000` trace_id=`fecf6a23d5a82b0eaebe827d9e68db41`
- request_id=`4b8fb265-8782-458e-9b9a-946b4e5b608c` score=`1.0000` trace_id=`8e0e6fb6ffdcfdc57066ee333c7999f5`
- request_id=`ba1f2bd8-fdd8-4887-be1d-7041b0221bad` score=`1.0000` trace_id=`b78f46dc34b905db8c0cc86df39c1db3`

### Lowest answer_completeness requests
- request_id=`da32ec0e-0803-4ed6-b8f1-ffb5f1e21f86` score=`0.0000` trace_id=`c307ae834902e540fc94b01c1c090a75`
- request_id=`13c8fffb-a1cb-47ba-b039-52de9ae05b7f` score=`1.0000` trace_id=`fb2c70d0c7ffe0210e78278e1695f79a`
- request_id=`49d392ba-65b8-4450-9042-90f0f7e8df0b` score=`1.0000` trace_id=`fecf6a23d5a82b0eaebe827d9e68db41`
- request_id=`4b8fb265-8782-458e-9b9a-946b4e5b608c` score=`1.0000` trace_id=`8e0e6fb6ffdcfdc57066ee333c7999f5`
- request_id=`ba1f2bd8-fdd8-4887-be1d-7041b0221bad` score=`1.0000` trace_id=`b78f46dc34b905db8c0cc86df39c1db3`

## Token Usage

### Runtime
| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| runtime | 5 | 8,834 | 2,839 | 11,673 | 0.00044170 | 0.00056780 | 0.00100950 |

### Judge
| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| judge_generation | 20 | 18,818 | 5,817 | 24,635 | 0.00094090 | 0.00116340 | 0.00210430 |
| judge_retrieval | 60 | 37,940 | 12,523 | 50,463 | 0.00189700 | 0.00250460 | 0.00440160 |
| judge_total | 80 | 56,758 | 18,340 | 75,098 | 0.00283790 | 0.00366800 | 0.00650590 |

Run total cost usd = runtime total cost usd + judge total cost usd

Run total cost usd = 0.00100950 + 0.00650590 = 0.00751540

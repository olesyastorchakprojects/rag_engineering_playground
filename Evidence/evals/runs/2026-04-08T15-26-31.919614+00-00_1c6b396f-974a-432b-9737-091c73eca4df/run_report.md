# Eval Run Report

## Run Metadata
- run_id: `1c6b396f-974a-432b-9737-091c73eca4df`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-08T15:26:31.919614+00:00`
- completed_at: `2026-04-08T15:30:01.858857+00:00`
- request_count: `5`
- requests_evaluated: `5`
- generation_suite_versions: `{"answer_completeness": "v1", "answer_relevance": "v1", "correct_refusal": "v1", "groundedness": "v1"}`
- retrieval_suite_versions: `{"retrieval_relevance": "v1"}`

### Retriever
- kind: `Hybrid`
- embedding_model: `qwen3-embedding:0.6b`
- collection: `chunks_hybrid_structural_qwen3`
- corpus_version: `v1`
- chunking_strategy: `structural`
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
| retrieval_relevance_mean | 0.1795 | 0.0000 | 1.0000 | 39 |
| retrieval_relevance_selected_mean | 0.3000 | 0.0000 | 1.0000 | 20 |
| retrieval_relevance_weighted_topk_mean | 0.3632 | 0.3679 | 0.4770 | 5 |

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
| top12 | 0.2433 | 0.4200 | 1.0000 | 0.9000 | 0.3998 |
| top4 | 0.1567 | 0.4200 | 1.0000 | 0.9000 | 0.5363 |

- retrieval_context_loss_soft: 0.0867
- retrieval_context_loss_strict: 0.0000
- avg_num_relevant_in_top12_soft: 2.8000
- avg_num_relevant_in_top12_strict: 1.4000
- avg_num_relevant_in_top4_soft: 1.8000
- avg_num_relevant_in_top4_strict: 1.4000

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for top12/top4 and soft/strict relevance.

| metric | top12_soft | top12_strict | top4_soft | top4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| answer_completeness_given_relevant_context | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| answer_relevance_given_relevant_context | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| hallucination_rate_when_top1_irrelevant | n/a | 0.0000 | n/a | 0.0000 |
| success_rate_when_at_least_one_relevant_in_topk | 0.8000 | 0.8000 | 0.8000 | 0.8000 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0_

_Definitions: hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`85205a54-95c7-4489-8d3b-8e2ea2783b3c` score=`0.0000` trace_id=`30ba7ff2f239d54cd0affd771749a0bd`
- request_id=`9382024f-2d4a-4b1a-ae0e-3f9f89bf0850` score=`1.0000` trace_id=`4335fadfee5f1dfc2011925e4a04d207`
- request_id=`aa1ee1fb-d11a-4d2a-a60a-12d0b5656f99` score=`1.0000` trace_id=`80d1df79723bd4aa7f6661955d15b86b`
- request_id=`b4dd5a35-c219-4d73-bb73-ecaee9436766` score=`1.0000` trace_id=`6046c398dc55c1a28862c1c3023c4a44`
- request_id=`e7ed97c9-9920-4ed7-b93e-5163d0a95f71` score=`1.0000` trace_id=`c60834481acf2d2871d17515bcb85f0e`

### Lowest answer_completeness requests
- request_id=`85205a54-95c7-4489-8d3b-8e2ea2783b3c` score=`0.0000` trace_id=`30ba7ff2f239d54cd0affd771749a0bd`
- request_id=`9382024f-2d4a-4b1a-ae0e-3f9f89bf0850` score=`1.0000` trace_id=`4335fadfee5f1dfc2011925e4a04d207`
- request_id=`aa1ee1fb-d11a-4d2a-a60a-12d0b5656f99` score=`1.0000` trace_id=`80d1df79723bd4aa7f6661955d15b86b`
- request_id=`b4dd5a35-c219-4d73-bb73-ecaee9436766` score=`1.0000` trace_id=`6046c398dc55c1a28862c1c3023c4a44`
- request_id=`e7ed97c9-9920-4ed7-b93e-5163d0a95f71` score=`1.0000` trace_id=`c60834481acf2d2871d17515bcb85f0e`

## Token Usage

### Runtime
| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| runtime | 5 | 22,195 | 2,754 | 24,949 | 0.00110975 | 0.00055080 | 0.00166055 |

### Judge
| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| judge_generation | 20 | 31,341 | 6,187 | 37,528 | 0.00156705 | 0.00123740 | 0.00280445 |
| judge_retrieval | 39 | 48,700 | 6,564 | 55,264 | 0.00243500 | 0.00131280 | 0.00374780 |
| judge_total | 59 | 80,041 | 12,751 | 92,792 | 0.00400205 | 0.00255020 | 0.00655225 |

Run total cost usd = runtime total cost usd + judge total cost usd

Run total cost usd = 0.00166055 + 0.00655225 = 0.00821280

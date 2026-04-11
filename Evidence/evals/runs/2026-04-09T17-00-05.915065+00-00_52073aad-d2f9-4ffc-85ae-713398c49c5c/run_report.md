# Eval Run Report

## Run Metadata
- eval_run_id: `52073aad-d2f9-4ffc-85ae-713398c49c5c`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-09T17:00:05.915065+00:00`
- runtime_run_id: `e10e6a0c-2782-47a1-b74c-a9c75d9392d4`
- completed_at: `2026-04-09T17:14:37.084485+00:00`
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
| answer_completeness_mean | 1.0000 | 1.0000 | 1.0000 | 5 |
| groundedness_mean | 0.9000 | 1.0000 | 1.0000 | 5 |
| answer_relevance_mean | 1.0000 | 1.0000 | 1.0000 | 5 |
| correct_refusal_rate | 0.0000 | 0.0000 | 0.0000 | 5 |
| retrieval_relevance_mean | 0.2833 | 0.0000 | 1.0000 | 60 |
| retrieval_relevance_selected_mean | 0.5750 | 0.5000 | 1.0000 | 20 |
| retrieval_relevance_weighted_topk_mean | 0.5345 | 0.5156 | 0.6540 | 5 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 5 | 100.0% |
| answer_completeness | partial | 0 | 0.0% |
| answer_completeness | incomplete | 0 | 0.0% |
| groundedness | grounded | 4 | 80.0% |
| groundedness | partially_grounded | 1 | 20.0% |
| groundedness | ungrounded | 0 | 0.0% |
| answer_relevance | relevant | 5 | 100.0% |
| answer_relevance | partially_relevant | 0 | 0.0% |
| answer_relevance | irrelevant | 0 | 0.0% |
| correct_refusal | correct_refusal | 0 | 0.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 5 | 100.0% |

## Retrieval Quality

| set | Recall soft | Recall strict | MRR soft | MRR strict | nDCG |
|---|---:|---:|---:|---:|---:|
| top12 | 0.5200 | 0.8833 | 1.0000 | 1.0000 | 0.6872 |
| top4 | 0.2800 | 0.6833 | 1.0000 | 1.0000 | 0.7581 |

- retrieval_context_loss_soft: 0.2400
- retrieval_context_loss_strict: 0.2000
- avg_num_relevant_in_top12_soft: 5.2000
- avg_num_relevant_in_top12_strict: 2.6000
- avg_num_relevant_in_top4_soft: 2.8000
- avg_num_relevant_in_top4_strict: 2.0000

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for top12/top4 and soft/strict relevance.

| metric | top12_soft | top12_strict | top4_soft | top4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.9000 | 0.9000 | 0.9000 | 0.9000 |
| answer_completeness_given_relevant_context | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| answer_relevance_given_relevant_context | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| hallucination_rate_when_top1_irrelevant | n/a | n/a | n/a | n/a |
| success_rate_when_at_least_one_relevant_in_topk | 0.8000 | 0.8000 | 0.8000 | 0.8000 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0_

_Definitions: hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`9257ac41-c069-4f0b-acd2-2bc09402de05` score=`0.5000` trace_id=`69f235f7e39452eb369cf767539991a8`
- request_id=`0ddd8da7-7fe3-4fc6-a992-ebc162a766c4` score=`1.0000` trace_id=`a937cb87498b3c917f38bc2dfc245cf9`
- request_id=`8540bec7-10cd-4e1d-a558-f0aef4702381` score=`1.0000` trace_id=`de7d33d9a22e44a5ee1853addc282f84`
- request_id=`a5b23c18-b4de-415d-9d03-bfb3cda7ae37` score=`1.0000` trace_id=`4409bd51b4d915d583644867af757da2`
- request_id=`c4bb86bb-8723-436a-a830-679a8464060f` score=`1.0000` trace_id=`d2ea78a3c33fb71b7fa2f7654cb39055`

### Lowest answer_completeness requests
- request_id=`0ddd8da7-7fe3-4fc6-a992-ebc162a766c4` score=`1.0000` trace_id=`a937cb87498b3c917f38bc2dfc245cf9`
- request_id=`8540bec7-10cd-4e1d-a558-f0aef4702381` score=`1.0000` trace_id=`de7d33d9a22e44a5ee1853addc282f84`
- request_id=`9257ac41-c069-4f0b-acd2-2bc09402de05` score=`1.0000` trace_id=`69f235f7e39452eb369cf767539991a8`
- request_id=`a5b23c18-b4de-415d-9d03-bfb3cda7ae37` score=`1.0000` trace_id=`4409bd51b4d915d583644867af757da2`
- request_id=`c4bb86bb-8723-436a-a830-679a8464060f` score=`1.0000` trace_id=`d2ea78a3c33fb71b7fa2f7654cb39055`

## Token Usage

### Runtime
| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| runtime | 5 | 8,791 | 2,450 | 11,241 | 0.00043955 | 0.00049000 | 0.00092955 |

### Judge
| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| judge_generation | 20 | 18,976 | 6,210 | 25,186 | 0.00094880 | 0.00124200 | 0.00219080 |
| judge_retrieval | 60 | 37,940 | 12,098 | 50,038 | 0.00189700 | 0.00241960 | 0.00431660 |
| judge_total | 80 | 56,916 | 18,308 | 75,224 | 0.00284580 | 0.00366160 | 0.00650740 |

Run total cost usd = runtime total cost usd + judge total cost usd

Run total cost usd = 0.00092955 + 0.00650740 = 0.00743695

# Eval Run Report

## Run Metadata
- eval_run_id: `4890ab41-d02c-4bd2-86f9-4fdf5b6729dc`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-10T15:38:38.668918+00:00`
- runtime_run_id: `1b6f08ac-972f-4042-a7ad-f1a42f608040`
- completed_at: `2026-04-10T15:47:15.100898+00:00`
- request_count: `20`
- requests_evaluated: `20`
- generation_suite_versions: `{"answer_completeness": "v1", "answer_relevance": "v1", "correct_refusal": "v1", "groundedness": "v1"}`
- retrieval_suite_versions: `{"retrieval_relevance": "v1"}`

### Retriever
- kind: `Hybrid - bm25`
- embedding_model: `qwen3-embedding:0.6b`
- collection: `chunks_hybrid_structural_qwen3`
- corpus_version: `v1`
- chunking_strategy: `structural`
- top_k: `12`
- actual_chunks_returned: `mean=7.60, min=5, max=9`

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
| answer_completeness_mean | 0.9000 | 1.0000 | 1.0000 | 20 |
| groundedness_mean | 0.9000 | 1.0000 | 1.0000 | 20 |
| answer_relevance_mean | 0.9000 | 1.0000 | 1.0000 | 20 |
| correct_refusal_rate | 0.0000 | 0.0000 | 0.0000 | 20 |
| retrieval_relevance_mean | 0.3289 | 0.5000 | 1.0000 | 152 |
| retrieval_relevance_selected_mean | 0.4688 | 0.5000 | 1.0000 | 80 |
| retrieval_relevance_weighted_topk_mean | 0.5022 | 0.5101 | 0.6500 | 20 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 18 | 90.0% |
| answer_completeness | partial | 0 | 0.0% |
| answer_completeness | incomplete | 2 | 10.0% |
| groundedness | grounded | 18 | 90.0% |
| groundedness | partially_grounded | 0 | 0.0% |
| groundedness | ungrounded | 2 | 10.0% |
| answer_relevance | relevant | 18 | 90.0% |
| answer_relevance | partially_relevant | 0 | 0.0% |
| answer_relevance | irrelevant | 2 | 10.0% |
| correct_refusal | correct_refusal | 0 | 0.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 20 | 100.0% |

## Retrieval Quality

| set | Recall soft | Recall strict | MRR soft | MRR strict | nDCG |
|---|---:|---:|---:|---:|---:|
| retrieval@12 | 0.6700 | 1.0000 | 1.0000 | 0.9667 | 0.7951 |
| generation_context@4 | 0.5300 | 1.0000 | 1.0000 | 0.9667 | 0.8093 |

- retrieval_context_loss_soft: 0.1400
- retrieval_context_loss_strict: 0.0000
- avg_num_relevant_in_retrieval@12_soft: 3.3500
- avg_num_relevant_in_retrieval@12_strict: 1.4500
- avg_num_relevant_in_generation_context@4_soft: 2.6500
- avg_num_relevant_in_generation_context@4_strict: 1.4500

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for retrieval@12/generation_context@4 and soft/strict relevance.

| metric | retrieval@12_soft | retrieval@12_strict | generation_context@4_soft | generation_context@4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.9000 | 0.9000 | 0.9000 | 0.9000 |
| answer_completeness_given_relevant_context | 0.9000 | 0.9000 | 0.9000 | 0.9000 |
| answer_relevance_given_relevant_context | 0.9000 | 0.9000 | 0.9000 | 0.9000 |
| hallucination_rate_when_top1_irrelevant | n/a | 0.0000 | n/a | 0.0000 |
| success_rate_when_at_least_one_relevant_in_topk | 0.9000 | 0.9000 | 0.9000 | 0.9000 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0_

_Definitions: hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`5248033a-9009-4e3f-901c-d97375bc67a9` score=`0.0000` trace_id=`24db65bb3b83e32dfa7dfe93f0a41adf`
- request_id=`ab3c7f4a-4af5-4cc7-bb78-1c74e71b3a3b` score=`0.0000` trace_id=`9796a2c95397041943b44031f865e534`
- request_id=`1a558979-66b3-49a7-b822-cec969a2c19e` score=`1.0000` trace_id=`582e8fafca6bdffe4b8606e298fdf77c`
- request_id=`246e4739-4392-4371-91c2-ea83e6dd33c5` score=`1.0000` trace_id=`0142d565887e4703a891ffc4e1874f75`
- request_id=`27a4a77e-e571-4bf8-9061-bba151c56b6e` score=`1.0000` trace_id=`fc9e6b0a4ec39954d2e40c7659c46065`

### Lowest answer_completeness requests
- request_id=`5248033a-9009-4e3f-901c-d97375bc67a9` score=`0.0000` trace_id=`24db65bb3b83e32dfa7dfe93f0a41adf`
- request_id=`ab3c7f4a-4af5-4cc7-bb78-1c74e71b3a3b` score=`0.0000` trace_id=`9796a2c95397041943b44031f865e534`
- request_id=`1a558979-66b3-49a7-b822-cec969a2c19e` score=`1.0000` trace_id=`582e8fafca6bdffe4b8606e298fdf77c`
- request_id=`246e4739-4392-4371-91c2-ea83e6dd33c5` score=`1.0000` trace_id=`0142d565887e4703a891ffc4e1874f75`
- request_id=`27a4a77e-e571-4bf8-9061-bba151c56b6e` score=`1.0000` trace_id=`fc9e6b0a4ec39954d2e40c7659c46065`

## Token Usage

### Runtime
| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| runtime | 20 | 52,243 | 11,144 | 63,387 | 0.00261215 | 0.00222880 | 0.00484095 |

### Judge
| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| judge_generation | 80 | 95,695 | 24,467 | 120,162 | 0.00478475 | 0.00489340 | 0.00967815 |
| judge_retrieval | 152 | 127,075 | 33,436 | 160,511 | 0.00635375 | 0.00668720 | 0.01304095 |
| judge_total | 232 | 222,770 | 57,903 | 280,673 | 0.01113850 | 0.01158060 | 0.02271910 |

Run total cost usd = runtime total cost usd + judge total cost usd

Run total cost usd = 0.00484095 + 0.02271910 = 0.02756005

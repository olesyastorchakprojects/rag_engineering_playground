# Eval Run Report

## Run Metadata
- eval_run_id: `70a99def-a2d5-460c-a542-9b44c9432573`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-09T18:19:29.856175+00:00`
- runtime_run_id: `b16e94b0-7b50-4aee-af9d-9abd18ef2665`
- completed_at: `2026-04-09T18:21:51.680803+00:00`
- request_count: `5`
- requests_evaluated: `5`
- generation_suite_versions: `{"answer_completeness": "v1", "answer_relevance": "v1", "correct_refusal": "v1", "groundedness": "v1"}`
- retrieval_suite_versions: `{"retrieval_relevance": "v1"}`

### Retriever
- kind: `Hybrid - bm25`
- embedding_model: `qwen3-embedding:0.6b`
- collection: `chunks_hybrid_fixed_qwen3`
- corpus_version: `v1`
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
| answer_completeness_mean | 0.4000 | 0.0000 | 1.0000 | 5 |
| groundedness_mean | 0.4000 | 0.0000 | 1.0000 | 5 |
| answer_relevance_mean | 0.4000 | 0.0000 | 1.0000 | 5 |
| correct_refusal_rate | 0.0000 | 0.0000 | 0.0000 | 5 |
| retrieval_relevance_mean | 0.4189 | 0.5000 | 1.0000 | 37 |
| retrieval_relevance_selected_mean | 0.6000 | 0.5000 | 1.0000 | 20 |
| retrieval_relevance_weighted_topk_mean | 0.6067 | 0.5946 | 0.6577 | 5 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 2 | 40.0% |
| answer_completeness | partial | 0 | 0.0% |
| answer_completeness | incomplete | 3 | 60.0% |
| groundedness | grounded | 2 | 40.0% |
| groundedness | partially_grounded | 0 | 0.0% |
| groundedness | ungrounded | 3 | 60.0% |
| answer_relevance | relevant | 2 | 40.0% |
| answer_relevance | partially_relevant | 0 | 0.0% |
| answer_relevance | irrelevant | 3 | 60.0% |
| correct_refusal | correct_refusal | 0 | 0.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 5 | 100.0% |

## Retrieval Quality

| set | Recall soft | Recall strict | MRR soft | MRR strict | nDCG |
|---|---:|---:|---:|---:|---:|
| top12 | 0.4000 | 0.7667 | 1.0000 | 1.0000 | 0.6107 |
| top4 | 0.2800 | 0.6167 | 1.0000 | 1.0000 | 0.7425 |

- retrieval_context_loss_soft: 0.1200
- retrieval_context_loss_strict: 0.1500
- avg_num_relevant_in_top12_soft: 4.0000
- avg_num_relevant_in_top12_strict: 2.2000
- avg_num_relevant_in_top4_soft: 2.8000
- avg_num_relevant_in_top4_strict: 1.8000

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for top12/top4 and soft/strict relevance.

| metric | top12_soft | top12_strict | top4_soft | top4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.4000 | 0.4000 | 0.4000 | 0.4000 |
| answer_completeness_given_relevant_context | 0.4000 | 0.4000 | 0.4000 | 0.4000 |
| answer_relevance_given_relevant_context | 0.4000 | 0.4000 | 0.4000 | 0.4000 |
| hallucination_rate_when_top1_irrelevant | n/a | n/a | n/a | n/a |
| success_rate_when_at_least_one_relevant_in_topk | 0.4000 | 0.4000 | 0.4000 | 0.4000 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0_

_Definitions: hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`7f5d07a5-0533-44d0-bca6-edefedd9e1a4` score=`0.0000` trace_id=`1b59966be94696492975128a007bb2c2`
- request_id=`88c55af1-3040-4725-b359-a36601df77e4` score=`0.0000` trace_id=`4217aa23ae3828c070300f4bccf6d23f`
- request_id=`ae417f15-2df4-4a32-8884-ff3e1fb99797` score=`0.0000` trace_id=`545658de705e351b53af2f48c9c348e2`
- request_id=`0af71d54-0e7a-43bf-a1ff-6c982db1308d` score=`1.0000` trace_id=`369dd88e4b2899ff367fb3a2fb26b45e`
- request_id=`2bd527d1-ec6b-4efd-a47c-dcd0b9024cdb` score=`1.0000` trace_id=`a9aa8599ae9778b181fa949c685edfef`

### Lowest answer_completeness requests
- request_id=`7f5d07a5-0533-44d0-bca6-edefedd9e1a4` score=`0.0000` trace_id=`1b59966be94696492975128a007bb2c2`
- request_id=`88c55af1-3040-4725-b359-a36601df77e4` score=`0.0000` trace_id=`4217aa23ae3828c070300f4bccf6d23f`
- request_id=`ae417f15-2df4-4a32-8884-ff3e1fb99797` score=`0.0000` trace_id=`545658de705e351b53af2f48c9c348e2`
- request_id=`0af71d54-0e7a-43bf-a1ff-6c982db1308d` score=`1.0000` trace_id=`369dd88e4b2899ff367fb3a2fb26b45e`
- request_id=`2bd527d1-ec6b-4efd-a47c-dcd0b9024cdb` score=`1.0000` trace_id=`a9aa8599ae9778b181fa949c685edfef`

## Token Usage

### Runtime
| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| runtime | 5 | 8,794 | 2,314 | 11,108 | 0.00043970 | 0.00046280 | 0.00090250 |

### Judge
| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| judge_generation | 20 | 17,169 | 5,177 | 22,346 | 0.00085845 | 0.00103540 | 0.00189385 |
| judge_retrieval | 37 | 23,494 | 8,440 | 31,934 | 0.00117470 | 0.00168800 | 0.00286270 |
| judge_total | 57 | 40,663 | 13,617 | 54,280 | 0.00203315 | 0.00272340 | 0.00475655 |

Run total cost usd = runtime total cost usd + judge total cost usd

Run total cost usd = 0.00090250 + 0.00475655 = 0.00565905

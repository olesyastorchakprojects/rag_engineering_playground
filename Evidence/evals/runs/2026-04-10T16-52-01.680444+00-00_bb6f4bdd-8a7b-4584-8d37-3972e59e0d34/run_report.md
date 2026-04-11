# Eval Run Report

## Run Metadata
- eval_run_id: `bb6f4bdd-8a7b-4584-8d37-3972e59e0d34`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-10T16:52:01.680444+00:00`
- runtime_run_id: `99ea37d9-f935-4652-a9ae-87f79859c88c`
- completed_at: `2026-04-10T17:00:21.995796+00:00`
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
| answer_completeness_mean | 0.8000 | 1.0000 | 1.0000 | 20 |
| groundedness_mean | 0.8000 | 1.0000 | 1.0000 | 20 |
| answer_relevance_mean | 0.8000 | 1.0000 | 1.0000 | 20 |
| correct_refusal_rate | 0.0000 | 0.0000 | 0.0000 | 20 |
| retrieval_relevance_mean | 0.3300 | 0.0000 | 1.0000 | 150 |
| retrieval_relevance_selected_mean | 0.5625 | 0.5000 | 1.0000 | 80 |
| retrieval_relevance_weighted_topk_mean | 0.5551 | 0.5464 | 0.6701 | 20 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 16 | 80.0% |
| answer_completeness | partial | 0 | 0.0% |
| answer_completeness | incomplete | 4 | 20.0% |
| groundedness | grounded | 16 | 80.0% |
| groundedness | partially_grounded | 0 | 0.0% |
| groundedness | ungrounded | 4 | 20.0% |
| answer_relevance | relevant | 16 | 80.0% |
| answer_relevance | partially_relevant | 0 | 0.0% |
| answer_relevance | irrelevant | 4 | 20.0% |
| correct_refusal | correct_refusal | 0 | 0.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 20 | 100.0% |

## Retrieval Quality

| set | Recall soft | Recall strict | MRR soft | MRR strict | nDCG |
|---|---:|---:|---:|---:|---:|
| retrieval@12 | 0.5582 | 0.7833 | 0.8917 | 0.8917 | 0.6483 |
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
| groundedness_given_relevant_context | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| answer_completeness_given_relevant_context | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| answer_relevance_given_relevant_context | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| hallucination_rate_when_top1_irrelevant | 0.0000 | 0.0000 | n/a | n/a |
| success_rate_when_at_least_one_relevant_in_topk | 0.8000 | 0.8000 | 0.8000 | 0.8000 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0_

_Definitions: hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`469d12b7-f18c-465b-ade7-b7d49931939e` score=`0.0000` trace_id=`af59ab0cbb456690d9febb27776e1d17`
- request_id=`5d324cc4-ef68-4736-b6db-0f90f757fe12` score=`0.0000` trace_id=`e8f15d1700ffea78d5c7d94c11e1cb4b`
- request_id=`65023987-a5ac-48d1-a883-17ed2bb2d9fe` score=`0.0000` trace_id=`ff18fa9761bef1879523f56bfefba4ef`
- request_id=`6b509195-f02a-4c81-9353-71b5978249e6` score=`0.0000` trace_id=`b5fa4a6ec3d46f76335bc55757440607`
- request_id=`059dac59-7fc4-43c0-aa03-7abf6803727e` score=`1.0000` trace_id=`d04a8e5fbd42ef524bbdbe9c0d859416`

### Lowest answer_completeness requests
- request_id=`469d12b7-f18c-465b-ade7-b7d49931939e` score=`0.0000` trace_id=`af59ab0cbb456690d9febb27776e1d17`
- request_id=`5d324cc4-ef68-4736-b6db-0f90f757fe12` score=`0.0000` trace_id=`e8f15d1700ffea78d5c7d94c11e1cb4b`
- request_id=`65023987-a5ac-48d1-a883-17ed2bb2d9fe` score=`0.0000` trace_id=`ff18fa9761bef1879523f56bfefba4ef`
- request_id=`6b509195-f02a-4c81-9353-71b5978249e6` score=`0.0000` trace_id=`b5fa4a6ec3d46f76335bc55757440607`
- request_id=`059dac59-7fc4-43c0-aa03-7abf6803727e` score=`1.0000` trace_id=`d04a8e5fbd42ef524bbdbe9c0d859416`

## Token Usage

### Runtime
| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| runtime | 20 | 35,615 | 14,067 | 49,682 | 0.00178075 | 0.00281340 | 0.00459415 |

### Judge
| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| judge_generation | 80 | 76,328 | 24,672 | 101,000 | 0.00381640 | 0.00493440 | 0.00875080 |
| judge_retrieval | 150 | 96,558 | 32,322 | 128,880 | 0.00482790 | 0.00646440 | 0.01129230 |
| judge_total | 230 | 172,886 | 56,994 | 229,880 | 0.00864430 | 0.01139880 | 0.02004310 |

Run total cost usd = runtime total cost usd + judge total cost usd

Run total cost usd = 0.00459415 + 0.02004310 = 0.02463725

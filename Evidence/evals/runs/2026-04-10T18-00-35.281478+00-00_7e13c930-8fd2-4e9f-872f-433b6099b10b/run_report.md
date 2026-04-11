# Eval Run Report

## Run Metadata
- eval_run_id: `7e13c930-8fd2-4e9f-872f-433b6099b10b`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-10T18:00:35.281478+00:00`
- runtime_run_id: `1d354ad4-5917-4ca8-b53f-1a6e5750a5ae`
- completed_at: `2026-04-10T18:07:44.843285+00:00`
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
| groundedness_mean | 0.7500 | 1.0000 | 1.0000 | 20 |
| answer_relevance_mean | 0.7250 | 1.0000 | 1.0000 | 20 |
| correct_refusal_rate | 0.0000 | 0.0000 | 0.0000 | 20 |
| retrieval_relevance_mean | 0.3125 | 0.0000 | 1.0000 | 152 |
| retrieval_relevance_selected_mean | 0.4812 | 0.5000 | 1.0000 | 80 |
| retrieval_relevance_weighted_topk_mean | 0.5057 | 0.4821 | 0.6671 | 20 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 14 | 70.0% |
| answer_completeness | partial | 0 | 0.0% |
| answer_completeness | incomplete | 6 | 30.0% |
| groundedness | grounded | 15 | 75.0% |
| groundedness | partially_grounded | 0 | 0.0% |
| groundedness | ungrounded | 5 | 25.0% |
| answer_relevance | relevant | 14 | 70.0% |
| answer_relevance | partially_relevant | 1 | 5.0% |
| answer_relevance | irrelevant | 5 | 25.0% |
| correct_refusal | correct_refusal | 0 | 0.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 20 | 100.0% |

## Retrieval Quality

| set | Recall soft | Recall strict | MRR soft | MRR strict | nDCG |
|---|---:|---:|---:|---:|---:|
| retrieval@12 | 0.6700 | 1.0000 | 1.0000 | 0.9667 | 0.7925 |
| generation_context@4 | 0.5700 | 0.9750 | 1.0000 | 0.9750 | 0.8320 |

- retrieval_context_loss_soft: 0.1000
- retrieval_context_loss_strict: 0.0250
- avg_num_relevant_in_retrieval@12_soft: 3.3500
- avg_num_relevant_in_retrieval@12_strict: 1.4500
- avg_num_relevant_in_generation_context@4_soft: 2.8500
- avg_num_relevant_in_generation_context@4_strict: 1.4000

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for retrieval@12/generation_context@4 and soft/strict relevance.

| metric | retrieval@12_soft | retrieval@12_strict | generation_context@4_soft | generation_context@4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.7500 | 0.7500 | 0.7500 | 0.7500 |
| answer_completeness_given_relevant_context | 0.7000 | 0.7000 | 0.7000 | 0.7000 |
| answer_relevance_given_relevant_context | 0.7250 | 0.7250 | 0.7250 | 0.7250 |
| hallucination_rate_when_top1_irrelevant | n/a | 0.0000 | n/a | 0.0000 |
| success_rate_when_at_least_one_relevant_in_topk | 0.7000 | 0.7000 | 0.7000 | 0.7000 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0_

_Definitions: hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`1b33dce2-2301-4c1b-ae07-fb6fa2943a8b` score=`0.0000` trace_id=`9fedc8e3873d8f92f0dc2b189aab30ad`
- request_id=`4076d6fb-6324-4a37-907c-cd8d6f5b139b` score=`0.0000` trace_id=`7f9ad5fcf0b75bc7ee76a6dbff784e63`
- request_id=`5b5d9f49-4d69-4163-b32b-02d7af19494f` score=`0.0000` trace_id=`1f8249c00cdfb7f65b48a52b3bc59f6c`
- request_id=`bcfd7303-35db-4f37-a54c-84d3958d50d7` score=`0.0000` trace_id=`5fceffc0b996822cc8b366d2165a47f0`
- request_id=`c257cbaa-2aab-4aea-8d6a-20ebc9b7e84a` score=`0.0000` trace_id=`e4d673e477023f8670286e8cba32eff1`

### Lowest answer_completeness requests
- request_id=`0f1b7757-74e2-490f-a5d6-6621857e09a2` score=`0.0000` trace_id=`126509faf083a8ce4973e77aecd8c84a`
- request_id=`1b33dce2-2301-4c1b-ae07-fb6fa2943a8b` score=`0.0000` trace_id=`9fedc8e3873d8f92f0dc2b189aab30ad`
- request_id=`4076d6fb-6324-4a37-907c-cd8d6f5b139b` score=`0.0000` trace_id=`7f9ad5fcf0b75bc7ee76a6dbff784e63`
- request_id=`5b5d9f49-4d69-4163-b32b-02d7af19494f` score=`0.0000` trace_id=`1f8249c00cdfb7f65b48a52b3bc59f6c`
- request_id=`bcfd7303-35db-4f37-a54c-84d3958d50d7` score=`0.0000` trace_id=`5fceffc0b996822cc8b366d2165a47f0`

## Token Usage

### Runtime
| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| runtime | 20 | 48,959 | 10,645 | 59,604 | 0.00244795 | 0.00212900 | 0.00457695 |

### Judge
| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| judge_generation | 80 | 89,334 | 25,751 | 115,085 | 0.00446670 | 0.00515020 | 0.00961690 |
| judge_retrieval | 152 | 127,075 | 33,548 | 160,623 | 0.00635375 | 0.00670960 | 0.01306335 |
| judge_total | 232 | 216,409 | 59,299 | 275,708 | 0.01082045 | 0.01185980 | 0.02268025 |

Run total cost usd = runtime total cost usd + judge total cost usd

Run total cost usd = 0.00457695 + 0.02268025 = 0.02725720

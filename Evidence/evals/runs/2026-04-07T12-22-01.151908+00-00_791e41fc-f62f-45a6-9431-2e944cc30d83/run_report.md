# Eval Run Report

## Run Metadata
- run_id: `791e41fc-f62f-45a6-9431-2e944cc30d83`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-07T12:22:01.151908+00:00`
- completed_at: `2026-04-07T12:44:58.076201+00:00`
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
- model: `mixedbread-ai/mxbai-rerank-base-v2`
- endpoint: `http://localhost:8081`

### Generation
- model: `qwen2.5:1.5b-instruct-ctx32k`
- model_endpoint: `http://localhost:11434`
- temperature: `0.0`
- max_context_chunks: `4`

### Judge
- model: `qwen2.5:1.5b-instruct-ctx32k`
- endpoint: `http://localhost:11434/v1`

## Aggregated Metrics
| metric | mean/rate | p50 | p90 | count |
|---|---:|---:|---:|---:|
| answer_completeness_mean | 1.0000 | 1.0000 | 1.0000 | 5 |
| groundedness_mean | 0.0000 | 0.0000 | 0.0000 | 5 |
| answer_relevance_mean | 1.0000 | 1.0000 | 1.0000 | 5 |
| correct_refusal_rate | 1.0000 | 1.0000 | 1.0000 | 5 |
| retrieval_relevance_mean | 0.1333 | 0.0000 | 1.0000 | 60 |
| retrieval_relevance_selected_mean | 0.2500 | 0.0000 | 1.0000 | 20 |
| retrieval_relevance_weighted_topk_mean | 0.2515 | 0.1611 | 0.5729 | 5 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 5 | 100.0% |
| answer_completeness | partial | 0 | 0.0% |
| answer_completeness | incomplete | 0 | 0.0% |
| groundedness | grounded | 0 | 0.0% |
| groundedness | partially_grounded | 0 | 0.0% |
| groundedness | ungrounded | 5 | 100.0% |
| answer_relevance | relevant | 5 | 100.0% |
| answer_relevance | partially_relevant | 0 | 0.0% |
| answer_relevance | irrelevant | 0 | 0.0% |
| correct_refusal | correct_refusal | 5 | 100.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 0 | 0.0% |

## Retrieval Quality

| set | Recall soft | Recall strict | MRR soft | MRR strict | nDCG |
|---|---:|---:|---:|---:|---:|
| top12 | 0.5200 | 0.8833 | 1.0000 | 1.0000 | 0.6872 |
| top4 | 0.3200 | 0.7167 | 1.0000 | 1.0000 | 0.8102 |

- retrieval_context_loss_soft: 0.2000
- retrieval_context_loss_strict: 0.1667
- avg_num_relevant_in_top12_soft: 5.2000
- avg_num_relevant_in_top12_strict: 2.6000
- avg_num_relevant_in_top4_soft: 3.2000
- avg_num_relevant_in_top4_strict: 2.0000

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for top12/top4 and soft/strict relevance.

| metric | top12_soft | top12_strict | top4_soft | top4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| answer_completeness_given_relevant_context | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| answer_relevance_given_relevant_context | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| hallucination_rate_when_top1_irrelevant | n/a | n/a | n/a | n/a |
| success_rate_when_at_least_one_relevant_in_topk | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0; hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`01b45d35-e334-46d7-8b15-9dd9ff185a36` score=`0.0000` trace_id=`933316f69c20b7122c590ba144dd3906`
- request_id=`7ae22a0a-327a-473b-8f3b-687c2b07c687` score=`0.0000` trace_id=`d8aec3de60a269ce1caa57db85cb8d6f`
- request_id=`b32dc056-337f-4cfe-b77b-b2bd14743036` score=`0.0000` trace_id=`bc5742aae1d1e949fddd347b66730d4b`
- request_id=`de9e3284-2182-4623-b913-a26b4f14210c` score=`0.0000` trace_id=`2a6787ad0da6acab56a4b65d6e61184e`
- request_id=`ee7c6664-a4c9-4aa6-91ff-b6c1af024039` score=`0.0000` trace_id=`52e091843b4ef60f4507211a9966d3bf`

### Lowest answer_completeness requests
- request_id=`01b45d35-e334-46d7-8b15-9dd9ff185a36` score=`1.0000` trace_id=`933316f69c20b7122c590ba144dd3906`
- request_id=`7ae22a0a-327a-473b-8f3b-687c2b07c687` score=`1.0000` trace_id=`d8aec3de60a269ce1caa57db85cb8d6f`
- request_id=`b32dc056-337f-4cfe-b77b-b2bd14743036` score=`1.0000` trace_id=`bc5742aae1d1e949fddd347b66730d4b`
- request_id=`de9e3284-2182-4623-b913-a26b4f14210c` score=`1.0000` trace_id=`2a6787ad0da6acab56a4b65d6e61184e`
- request_id=`ee7c6664-a4c9-4aa6-91ff-b6c1af024039` score=`1.0000` trace_id=`52e091843b4ef60f4507211a9966d3bf`

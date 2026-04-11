# Eval Run Report

## Run Metadata
- eval_run_id: `cd2431e5-320c-479c-b4d0-b9e63e179fde`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-10T18:31:39.394994+00:00`
- runtime_run_id: `268f2a4f-e5ec-4bca-a085-f21f07719dec`
- completed_at: `2026-04-10T18:46:03.229619+00:00`
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
- kind: `Heuristic`
- weight.retrieval_score: `1.0`
- weight.phrase_match_bonus: `1.0`
- weight.query_term_coverage: `1.0`
- weight.title_section_match_bonus: `1.0`

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
| retrieval_relevance_mean | 0.3158 | 0.0000 | 1.0000 | 152 |
| retrieval_relevance_selected_mean | 0.4562 | 0.5000 | 1.0000 | 80 |
| retrieval_relevance_weighted_topk_mean | 0.4956 | 0.4698 | 0.6577 | 20 |

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
| retrieval@12 | 0.6700 | 1.0000 | 1.0000 | 0.9667 | 0.7922 |
| generation_context@4 | 0.4800 | 1.0000 | 1.0000 | 0.9750 | 0.7756 |

- retrieval_context_loss_soft: 0.1900
- retrieval_context_loss_strict: 0.0000
- avg_num_relevant_in_retrieval@12_soft: 3.3500
- avg_num_relevant_in_retrieval@12_strict: 1.4500
- avg_num_relevant_in_generation_context@4_soft: 2.4000
- avg_num_relevant_in_generation_context@4_strict: 1.4500

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for retrieval@12/generation_context@4 and soft/strict relevance.

| metric | retrieval@12_soft | retrieval@12_strict | generation_context@4_soft | generation_context@4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.8500 | 0.8500 | 0.8500 | 0.8500 |
| answer_completeness_given_relevant_context | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| answer_relevance_given_relevant_context | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| hallucination_rate_when_top1_irrelevant | n/a | 0.0000 | n/a | 0.0000 |
| success_rate_when_at_least_one_relevant_in_topk | 0.8000 | 0.8000 | 0.8000 | 0.8000 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0_

_Definitions: hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`440e8b82-0059-42c0-9efa-5931462efcae` score=`0.0000` trace_id=`3d9431884d34156b451630ea36a2221e`
- request_id=`44cf9fdf-1822-442b-a9a7-2d28157eaaa2` score=`0.0000` trace_id=`cfd3350489bb20390d8cddab6a81a67c`
- request_id=`b4ca74b1-7b0d-4d96-b28c-acac0c5ff0ab` score=`0.0000` trace_id=`a47681f8c3e9f88e36162dda6cc137ec`
- request_id=`37ec6ff8-d994-47b3-995d-2f66351560a0` score=`1.0000` trace_id=`5fc514ecad47d7ba45b23ef1a985fab6`
- request_id=`5ebe7a71-6141-4d14-b466-64174c7d24a0` score=`1.0000` trace_id=`1394db1a42312cc45c15c23902c4449f`

### Lowest answer_completeness requests
- request_id=`440e8b82-0059-42c0-9efa-5931462efcae` score=`0.0000` trace_id=`3d9431884d34156b451630ea36a2221e`
- request_id=`44cf9fdf-1822-442b-a9a7-2d28157eaaa2` score=`0.0000` trace_id=`cfd3350489bb20390d8cddab6a81a67c`
- request_id=`9b056e95-7587-4fc3-b902-b5eee13daed5` score=`0.0000` trace_id=`86cb6a2953930a2ebac0cafc8693bda9`
- request_id=`b4ca74b1-7b0d-4d96-b28c-acac0c5ff0ab` score=`0.0000` trace_id=`a47681f8c3e9f88e36162dda6cc137ec`
- request_id=`37ec6ff8-d994-47b3-995d-2f66351560a0` score=`1.0000` trace_id=`5fc514ecad47d7ba45b23ef1a985fab6`

## Token Usage

### Runtime
| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| runtime | 20 | 56,814 | 9,840 | 66,654 | 0.00284070 | 0.00196800 | 0.00480870 |

### Judge
| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| judge_generation | 80 | 97,378 | 22,386 | 119,764 | 0.00486890 | 0.00447720 | 0.00934610 |
| judge_retrieval | 152 | 127,075 | 32,668 | 159,743 | 0.00635375 | 0.00653360 | 0.01288735 |
| judge_total | 232 | 224,453 | 55,054 | 279,507 | 0.01122265 | 0.01101080 | 0.02223345 |

Run total cost usd = runtime total cost usd + judge total cost usd

Run total cost usd = 0.00480870 + 0.02223345 = 0.02704215

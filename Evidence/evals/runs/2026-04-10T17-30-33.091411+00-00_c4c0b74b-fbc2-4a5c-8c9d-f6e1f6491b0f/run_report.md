# Eval Run Report

## Run Metadata
- eval_run_id: `c4c0b74b-fbc2-4a5c-8c9d-f6e1f6491b0f`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-10T17:30:33.091411+00:00`
- runtime_run_id: `ba9d19d5-aa94-49b4-a021-6a78fbad698d`
- completed_at: `2026-04-10T17:37:04.672796+00:00`
- request_count: `20`
- requests_evaluated: `20`
- generation_suite_versions: `{"answer_completeness": "v1", "answer_relevance": "v1", "correct_refusal": "v1", "groundedness": "v1"}`
- retrieval_suite_versions: `{"retrieval_relevance": "v1"}`

### Retriever
- kind: `Hybrid - bow`
- embedding_model: `qwen3-embedding:0.6b`
- collection: `chunks_hybrid_structural_qwen3`
- corpus_version: `v1`
- chunking_strategy: `structural`
- top_k: `12`
- actual_chunks_returned: `mean=8.00, min=6, max=10`

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
| answer_completeness_mean | 0.8500 | 1.0000 | 1.0000 | 20 |
| groundedness_mean | 0.8250 | 1.0000 | 1.0000 | 20 |
| answer_relevance_mean | 0.8500 | 1.0000 | 1.0000 | 20 |
| correct_refusal_rate | 0.0000 | 0.0000 | 0.0000 | 20 |
| retrieval_relevance_mean | 0.2344 | 0.0000 | 1.0000 | 160 |
| retrieval_relevance_selected_mean | 0.4438 | 0.5000 | 1.0000 | 80 |
| retrieval_relevance_weighted_topk_mean | 0.4529 | 0.4325 | 0.5979 | 20 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 17 | 85.0% |
| answer_completeness | partial | 0 | 0.0% |
| answer_completeness | incomplete | 3 | 15.0% |
| groundedness | grounded | 16 | 80.0% |
| groundedness | partially_grounded | 1 | 5.0% |
| groundedness | ungrounded | 3 | 15.0% |
| answer_relevance | relevant | 17 | 85.0% |
| answer_relevance | partially_relevant | 0 | 0.0% |
| answer_relevance | irrelevant | 3 | 15.0% |
| correct_refusal | correct_refusal | 0 | 0.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 20 | 100.0% |

## Retrieval Quality

| set | Recall soft | Recall strict | MRR soft | MRR strict | nDCG |
|---|---:|---:|---:|---:|---:|
| retrieval@12 | 0.5500 | 0.9500 | 0.8250 | 0.7550 | 0.6061 |
| generation_context@4 | 0.5100 | 0.9500 | 1.0000 | 0.9667 | 0.7865 |

- retrieval_context_loss_soft: 0.0400
- retrieval_context_loss_strict: 0.0000
- avg_num_relevant_in_retrieval@12_soft: 2.7500
- avg_num_relevant_in_retrieval@12_strict: 1.3500
- avg_num_relevant_in_generation_context@4_soft: 2.5500
- avg_num_relevant_in_generation_context@4_strict: 1.3500

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for retrieval@12/generation_context@4 and soft/strict relevance.

| metric | retrieval@12_soft | retrieval@12_strict | generation_context@4_soft | generation_context@4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.8250 | 0.8250 | 0.8250 | 0.8250 |
| answer_completeness_given_relevant_context | 0.8500 | 0.8500 | 0.8500 | 0.8500 |
| answer_relevance_given_relevant_context | 0.8500 | 0.8500 | 0.8500 | 0.8500 |
| hallucination_rate_when_top1_irrelevant | 0.1429 | 0.2222 | n/a | 1.0000 |
| success_rate_when_at_least_one_relevant_in_topk | 0.8000 | 0.8000 | 0.8000 | 0.8000 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0_

_Definitions: hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`270aaa88-0881-4912-a852-bdeccc9e65aa` score=`0.0000` trace_id=`c8d9a9aa52254f42bafc6cf8445a3531`
- request_id=`338a0d68-d499-4bf0-9d00-d214d6f09f5c` score=`0.0000` trace_id=`3b3e7c0e74ff759f8b291532bc0a1cd9`
- request_id=`9ee8de7a-9e95-4c5a-af81-829de25d4a08` score=`0.0000` trace_id=`db283d4d09a60b0f1f12c6e8968f401c`
- request_id=`017f3b3c-675d-44b7-851d-687acc46383b` score=`0.5000` trace_id=`862ed002f7dfb96e8cbad611fab1492c`
- request_id=`115a8ca4-754a-44a4-95af-1dfcd092d0a5` score=`1.0000` trace_id=`377c9bedbbfa005df4ae3037c9dc23c3`

### Lowest answer_completeness requests
- request_id=`270aaa88-0881-4912-a852-bdeccc9e65aa` score=`0.0000` trace_id=`c8d9a9aa52254f42bafc6cf8445a3531`
- request_id=`338a0d68-d499-4bf0-9d00-d214d6f09f5c` score=`0.0000` trace_id=`3b3e7c0e74ff759f8b291532bc0a1cd9`
- request_id=`9ee8de7a-9e95-4c5a-af81-829de25d4a08` score=`0.0000` trace_id=`db283d4d09a60b0f1f12c6e8968f401c`
- request_id=`017f3b3c-675d-44b7-851d-687acc46383b` score=`1.0000` trace_id=`862ed002f7dfb96e8cbad611fab1492c`
- request_id=`115a8ca4-754a-44a4-95af-1dfcd092d0a5` score=`1.0000` trace_id=`377c9bedbbfa005df4ae3037c9dc23c3`

## Token Usage

### Runtime
| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| runtime | 20 | 56,183 | 10,816 | 66,999 | 0.00280915 | 0.00216320 | 0.00497235 |

### Judge
| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| judge_generation | 80 | 97,831 | 26,251 | 124,082 | 0.00489155 | 0.00525020 | 0.01014175 |
| judge_retrieval | 160 | 202,204 | 30,296 | 232,500 | 0.01011020 | 0.00605920 | 0.01616940 |
| judge_total | 240 | 300,035 | 56,547 | 356,582 | 0.01500175 | 0.01130940 | 0.02631115 |

Run total cost usd = runtime total cost usd + judge total cost usd

Run total cost usd = 0.00497235 + 0.02631115 = 0.03128350

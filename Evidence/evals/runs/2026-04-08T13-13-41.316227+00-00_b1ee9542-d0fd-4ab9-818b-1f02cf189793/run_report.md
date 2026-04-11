# Eval Run Report

## Run Metadata
- run_id: `b1ee9542-d0fd-4ab9-818b-1f02cf189793`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-08T13:13:41.316227+00:00`
- completed_at: `2026-04-08T13:15:01.430546+00:00`
- request_count: `1`
- requests_evaluated: `1`
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

## Token Usage

### Runtime
| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| runtime | 1 | 1,772 | 438 | 2,210 | 0.00008860 | 0.00008760 | 0.00017620 |

### Judge
| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| judge_generation | 4 | 3,817 | 1,426 | 5,243 | 0.00019085 | 0.00028520 | 0.00047605 |
| judge_retrieval | 12 | 7,645 | 3,152 | 10,797 | 0.00038225 | 0.00063040 | 0.00101265 |
| judge_total | 16 | 11,462 | 4,578 | 16,040 | 0.00057310 | 0.00091560 | 0.00148870 |

Run total cost usd = runtime total cost usd + judge total cost usd
Run total cost usd = 0.00017620 + 0.00148870 = 0.00166490

## Aggregated Metrics
| metric | mean/rate | p50 | p90 | count |
|---|---:|---:|---:|---:|
| answer_completeness_mean | 1.0000 | 1.0000 | 1.0000 | 1 |
| groundedness_mean | 0.5000 | 0.5000 | 0.5000 | 1 |
| answer_relevance_mean | 1.0000 | 1.0000 | 1.0000 | 1 |
| correct_refusal_rate | 0.0000 | 0.0000 | 0.0000 | 1 |
| retrieval_relevance_mean | 0.4583 | 0.5000 | 1.0000 | 12 |
| retrieval_relevance_selected_mean | 0.6250 | 0.5000 | 1.0000 | 4 |
| retrieval_relevance_weighted_topk_mean | 0.6424 | 0.6424 | 0.6424 | 1 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 1 | 100.0% |
| answer_completeness | partial | 0 | 0.0% |
| answer_completeness | incomplete | 0 | 0.0% |
| groundedness | grounded | 0 | 0.0% |
| groundedness | partially_grounded | 1 | 100.0% |
| groundedness | ungrounded | 0 | 0.0% |
| answer_relevance | relevant | 1 | 100.0% |
| answer_relevance | partially_relevant | 0 | 0.0% |
| answer_relevance | irrelevant | 0 | 0.0% |
| correct_refusal | correct_refusal | 0 | 0.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 1 | 100.0% |

## Retrieval Quality

| set | Recall soft | Recall strict | MRR soft | MRR strict | nDCG |
|---|---:|---:|---:|---:|---:|
| top12 | 0.8000 | 1.0000 | 1.0000 | 1.0000 | 0.8965 |
| top4 | 0.4000 | 0.7500 | 1.0000 | 1.0000 | 0.9024 |

- retrieval_context_loss_soft: 0.4000
- retrieval_context_loss_strict: 0.2500
- avg_num_relevant_in_top12_soft: 8.0000
- avg_num_relevant_in_top12_strict: 4.0000
- avg_num_relevant_in_top4_soft: 4.0000
- avg_num_relevant_in_top4_strict: 3.0000

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for top12/top4 and soft/strict relevance.

| metric | top12_soft | top12_strict | top4_soft | top4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.5000 | 0.5000 | 0.5000 | 0.5000 |
| answer_completeness_given_relevant_context | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| answer_relevance_given_relevant_context | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| hallucination_rate_when_top1_irrelevant | n/a | n/a | n/a | n/a |
| success_rate_when_at_least_one_relevant_in_topk | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0; hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`f51da11c-3706-4acc-bf59-237e1a032297` score=`0.5000` trace_id=`dd11b3d2459a93c4e98a2afd65a2e37f`

### Lowest answer_completeness requests
- request_id=`f51da11c-3706-4acc-bf59-237e1a032297` score=`1.0000` trace_id=`dd11b3d2459a93c4e98a2afd65a2e37f`

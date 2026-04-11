# Eval Run Report

## Run Metadata
- eval_run_id: `f3965d14-3f63-4a22-910d-25c3bc6741a1`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-09T16:45:15.659023+00:00`
- runtime_run_id: `531572c2-690f-4ec2-ae4b-f3f5bf1a2af8`
- completed_at: `2026-04-09T16:48:11.880824+00:00`
- request_count: `5`
- requests_evaluated: `5`
- generation_suite_versions: `{"answer_completeness": "v1", "answer_relevance": "v1", "correct_refusal": "v1", "groundedness": "v1"}`
- retrieval_suite_versions: `{"retrieval_relevance": "v1"}`

### Retriever
- kind: `Dense`
- embedding_model: `qwen3-embedding:0.6b`
- collection: `chunks_dense_qwen3`
- corpus_version: `v1`
- chunking_strategy: `structural`
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
| groundedness_mean | 1.0000 | 1.0000 | 1.0000 | 5 |
| answer_relevance_mean | 1.0000 | 1.0000 | 1.0000 | 5 |
| correct_refusal_rate | 0.0000 | 0.0000 | 0.0000 | 5 |
| retrieval_relevance_mean | 0.1583 | 0.0000 | 0.5000 | 60 |
| retrieval_relevance_selected_mean | 0.4000 | 0.5000 | 1.0000 | 20 |
| retrieval_relevance_weighted_topk_mean | 0.3776 | 0.3679 | 0.5534 | 5 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 5 | 100.0% |
| answer_completeness | partial | 0 | 0.0% |
| answer_completeness | incomplete | 0 | 0.0% |
| groundedness | grounded | 5 | 100.0% |
| groundedness | partially_grounded | 0 | 0.0% |
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
| top12 | 0.5100 | 0.7533 | 1.0000 | 1.0000 | 0.6169 |
| top4 | 0.2400 | 0.6333 | 1.0000 | 1.0000 | 0.7618 |

- retrieval_context_loss_soft: 0.2700
- retrieval_context_loss_strict: 0.1200
- avg_num_relevant_in_top12_soft: 6.0000
- avg_num_relevant_in_top12_strict: 2.8000
- avg_num_relevant_in_top4_soft: 2.8000
- avg_num_relevant_in_top4_strict: 2.2000

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for top12/top4 and soft/strict relevance.

| metric | top12_soft | top12_strict | top4_soft | top4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| answer_completeness_given_relevant_context | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| answer_relevance_given_relevant_context | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| hallucination_rate_when_top1_irrelevant | n/a | n/a | n/a | n/a |
| success_rate_when_at_least_one_relevant_in_topk | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0_

_Definitions: hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`2f650c3e-2dc6-4320-a500-82e35e0c3f9e` score=`1.0000` trace_id=`5b19fd96f1f051fbd0539d40cf8f43f3`
- request_id=`337d2d4d-1b5c-4a16-831a-53413d3146b9` score=`1.0000` trace_id=`5b99bc4b31b725096badfd3a5fa743d3`
- request_id=`54ac9ab3-5c79-421e-8466-f65b186e5666` score=`1.0000` trace_id=`3b06da819c106bd9a0d6be388071522f`
- request_id=`de41036a-893c-4e79-9959-6332ef121150` score=`1.0000` trace_id=`9c5f25f1f845e057ec5ed9ea1ee3b9b4`
- request_id=`e80ccbe0-6b6f-470e-97a8-15422f15cc99` score=`1.0000` trace_id=`ccd265ca56609adb8ef7445bc8768898`

### Lowest answer_completeness requests
- request_id=`2f650c3e-2dc6-4320-a500-82e35e0c3f9e` score=`1.0000` trace_id=`5b19fd96f1f051fbd0539d40cf8f43f3`
- request_id=`337d2d4d-1b5c-4a16-831a-53413d3146b9` score=`1.0000` trace_id=`5b99bc4b31b725096badfd3a5fa743d3`
- request_id=`54ac9ab3-5c79-421e-8466-f65b186e5666` score=`1.0000` trace_id=`3b06da819c106bd9a0d6be388071522f`
- request_id=`de41036a-893c-4e79-9959-6332ef121150` score=`1.0000` trace_id=`9c5f25f1f845e057ec5ed9ea1ee3b9b4`
- request_id=`e80ccbe0-6b6f-470e-97a8-15422f15cc99` score=`1.0000` trace_id=`ccd265ca56609adb8ef7445bc8768898`

## Token Usage

### Runtime
| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| runtime | 5 | 11,809 | 2,753 | 14,562 | 0.00059045 | 0.00055060 | 0.00114105 |

### Judge
| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| judge_generation | 20 | 22,138 | 5,509 | 27,647 | 0.00110690 | 0.00110180 | 0.00220870 |
| judge_retrieval | 60 | 42,087 | 11,554 | 53,641 | 0.00210435 | 0.00231080 | 0.00441515 |
| judge_total | 80 | 64,225 | 17,063 | 81,288 | 0.00321125 | 0.00341260 | 0.00662385 |

Run total cost usd = runtime total cost usd + judge total cost usd

Run total cost usd = 0.00114105 + 0.00662385 = 0.00776490

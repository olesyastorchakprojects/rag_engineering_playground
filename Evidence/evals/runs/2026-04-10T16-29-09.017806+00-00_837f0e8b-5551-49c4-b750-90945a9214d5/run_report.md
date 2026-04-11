# Eval Run Report

## Run Metadata
- eval_run_id: `837f0e8b-5551-49c4-b750-90945a9214d5`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-10T16:29:09.017806+00:00`
- runtime_run_id: `776301a0-a5da-4ae5-8f4a-4cddfc1ef98b`
- completed_at: `2026-04-10T16:40:13.742388+00:00`
- request_count: `20`
- requests_evaluated: `20`
- generation_suite_versions: `{"answer_completeness": "v1", "answer_relevance": "v1", "correct_refusal": "v1", "groundedness": "v1"}`
- retrieval_suite_versions: `{"retrieval_relevance": "v1"}`

### Retriever
- kind: `Dense`
- embedding_model: `qwen3-embedding:0.6b`
- collection: `chunks_dense_qwen3`
- corpus_version: `v1`
- chunking_strategy: `structural`
- top_k: `12`
- actual_chunks_returned: `mean=12.00, min=12, max=12`

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
| answer_completeness_mean | 0.9000 | 1.0000 | 1.0000 | 20 |
| groundedness_mean | 0.8250 | 1.0000 | 1.0000 | 20 |
| answer_relevance_mean | 0.9000 | 1.0000 | 1.0000 | 20 |
| correct_refusal_rate | 0.0000 | 0.0000 | 0.0000 | 20 |
| retrieval_relevance_mean | 0.2229 | 0.0000 | 0.5000 | 240 |
| retrieval_relevance_selected_mean | 0.4938 | 0.5000 | 1.0000 | 80 |
| retrieval_relevance_weighted_topk_mean | 0.4395 | 0.4309 | 0.5604 | 20 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 18 | 90.0% |
| answer_completeness | partial | 0 | 0.0% |
| answer_completeness | incomplete | 2 | 10.0% |
| groundedness | grounded | 15 | 75.0% |
| groundedness | partially_grounded | 3 | 15.0% |
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
| retrieval@12 | 0.7700 | 1.0000 | 1.0000 | 0.9625 | 0.8258 |
| generation_context@4 | 0.5800 | 0.9750 | 1.0000 | 0.9750 | 0.8371 |

- retrieval_context_loss_soft: 0.1900
- retrieval_context_loss_strict: 0.0250
- avg_num_relevant_in_retrieval@12_soft: 3.8500
- avg_num_relevant_in_retrieval@12_strict: 1.4500
- avg_num_relevant_in_generation_context@4_soft: 2.9000
- avg_num_relevant_in_generation_context@4_strict: 1.4000

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for retrieval@12/generation_context@4 and soft/strict relevance.

| metric | retrieval@12_soft | retrieval@12_strict | generation_context@4_soft | generation_context@4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.8250 | 0.8250 | 0.8250 | 0.8250 |
| answer_completeness_given_relevant_context | 0.9000 | 0.9000 | 0.9000 | 0.9000 |
| answer_relevance_given_relevant_context | 0.9000 | 0.9000 | 0.9000 | 0.9000 |
| hallucination_rate_when_top1_irrelevant | n/a | 0.0000 | n/a | 0.0000 |
| success_rate_when_at_least_one_relevant_in_topk | 0.7500 | 0.7500 | 0.7500 | 0.7500 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0_

_Definitions: hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`10649001-db7b-46d7-8d88-b8fe685e38a4` score=`0.0000` trace_id=`1338833e73ebf6a8230b9fa4be5db29c`
- request_id=`31126de1-2a0d-4a2c-aaac-58806ff1b63b` score=`0.0000` trace_id=`49b35abe4ec6031d3ab61c1272db1c63`
- request_id=`8aa15429-5d00-4190-9f8d-45850625535e` score=`0.5000` trace_id=`e517a21344524b66a42abfff2c8c9958`
- request_id=`df190088-0437-4af4-a8de-0716f8fe286a` score=`0.5000` trace_id=`bc37c0c10db4f7bc69b65be2eb4c48c2`
- request_id=`fbb5656b-95d9-43eb-9131-36a45461e8f9` score=`0.5000` trace_id=`20055c789e9491b4edc782ace4bb1c44`

### Lowest answer_completeness requests
- request_id=`10649001-db7b-46d7-8d88-b8fe685e38a4` score=`0.0000` trace_id=`1338833e73ebf6a8230b9fa4be5db29c`
- request_id=`31126de1-2a0d-4a2c-aaac-58806ff1b63b` score=`0.0000` trace_id=`49b35abe4ec6031d3ab61c1272db1c63`
- request_id=`0208912f-0639-43ba-8fac-7a0c3a814c5d` score=`1.0000` trace_id=`e38550ac6f342f88eacc83bab8e5a161`
- request_id=`0eaeedb3-d143-4a24-a975-f514960b0c0e` score=`1.0000` trace_id=`f38dfec2bca926b3923be01089bca467`
- request_id=`4e414792-3898-4173-9948-6b042938c6c6` score=`1.0000` trace_id=`eb067fc7fc737c9b69e7ba25f4d5d69a`

## Token Usage

### Runtime
| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| runtime | 20 | 49,243 | 11,450 | 60,693 | 0.00246215 | 0.00229000 | 0.00475215 |

### Judge
| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| judge_generation | 80 | 92,335 | 25,665 | 118,000 | 0.00461675 | 0.00513300 | 0.00974975 |
| judge_retrieval | 240 | 185,923 | 48,551 | 234,474 | 0.00929615 | 0.00971020 | 0.01900635 |
| judge_total | 320 | 278,258 | 74,216 | 352,474 | 0.01391290 | 0.01484320 | 0.02875610 |

Run total cost usd = runtime total cost usd + judge total cost usd

Run total cost usd = 0.00475215 + 0.02875610 = 0.03350825

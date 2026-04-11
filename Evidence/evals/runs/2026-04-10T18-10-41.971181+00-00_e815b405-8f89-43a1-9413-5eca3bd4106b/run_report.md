# Eval Run Report

## Run Metadata
- eval_run_id: `e815b405-8f89-43a1-9413-5eca3bd4106b`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-10T18:10:41.971181+00:00`
- runtime_run_id: `cd4a89d3-6d4a-417c-b13e-8dda399e5077`
- completed_at: `2026-04-10T18:25:49.573719+00:00`
- request_count: `20`
- requests_evaluated: `20`
- generation_suite_versions: `{"answer_completeness": "v1", "answer_relevance": "v1", "correct_refusal": "v1", "groundedness": "v1"}`
- retrieval_suite_versions: `{"retrieval_relevance": "v1"}`

### Retriever
- kind: `Dense`
- embedding_model: `qwen3-embedding:0.6b`
- collection: `chunks_dense_qwen3_fixed`
- corpus_version: `v2`
- chunking_strategy: `fixed`
- top_k: `12`
- actual_chunks_returned: `mean=12.00, min=12, max=12`

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
| answer_completeness_mean | 0.7500 | 1.0000 | 1.0000 | 20 |
| groundedness_mean | 0.7500 | 1.0000 | 1.0000 | 20 |
| answer_relevance_mean | 0.7500 | 1.0000 | 1.0000 | 20 |
| correct_refusal_rate | 0.0000 | 0.0000 | 0.0000 | 20 |
| retrieval_relevance_mean | 0.3000 | 0.0000 | 1.0000 | 240 |
| retrieval_relevance_selected_mean | 0.5625 | 0.5000 | 1.0000 | 80 |
| retrieval_relevance_weighted_topk_mean | 0.5044 | 0.4968 | 0.6527 | 20 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 15 | 75.0% |
| answer_completeness | partial | 0 | 0.0% |
| answer_completeness | incomplete | 5 | 25.0% |
| groundedness | grounded | 14 | 70.0% |
| groundedness | partially_grounded | 2 | 10.0% |
| groundedness | ungrounded | 4 | 20.0% |
| answer_relevance | relevant | 15 | 75.0% |
| answer_relevance | partially_relevant | 0 | 0.0% |
| answer_relevance | irrelevant | 5 | 25.0% |
| correct_refusal | correct_refusal | 0 | 0.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 20 | 100.0% |

## Retrieval Quality

| set | Recall soft | Recall strict | MRR soft | MRR strict | nDCG |
|---|---:|---:|---:|---:|---:|
| retrieval@12 | 0.7697 | 0.9042 | 1.0000 | 1.0000 | 0.8201 |
| generation_context@4 | 0.5012 | 0.7958 | 1.0000 | 1.0000 | 0.8243 |

- retrieval_context_loss_soft: 0.2685
- retrieval_context_loss_strict: 0.1083
- avg_num_relevant_in_retrieval@12_soft: 4.7500
- avg_num_relevant_in_retrieval@12_strict: 2.6000
- avg_num_relevant_in_generation_context@4_soft: 3.0500
- avg_num_relevant_in_generation_context@4_strict: 2.2500

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for retrieval@12/generation_context@4 and soft/strict relevance.

| metric | retrieval@12_soft | retrieval@12_strict | generation_context@4_soft | generation_context@4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.7500 | 0.7500 | 0.7500 | 0.7500 |
| answer_completeness_given_relevant_context | 0.7500 | 0.7500 | 0.7500 | 0.7500 |
| answer_relevance_given_relevant_context | 0.7500 | 0.7500 | 0.7500 | 0.7500 |
| hallucination_rate_when_top1_irrelevant | n/a | n/a | n/a | n/a |
| success_rate_when_at_least_one_relevant_in_topk | 0.6500 | 0.6500 | 0.6500 | 0.6500 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0_

_Definitions: hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`21c5eb65-a99b-45d5-90ee-7169075c823d` score=`0.0000` trace_id=`a16ad4e1fb3333df58cfe5409d84721d`
- request_id=`35831186-d5e3-4495-9158-e40cde7ea7a2` score=`0.0000` trace_id=`741d196d54d4581be1d6c31a7184d431`
- request_id=`80b4b85a-6ce3-4b19-a78f-900fdaf1015b` score=`0.0000` trace_id=`beefb5ecac63a886c09ec0cf07f9939f`
- request_id=`ac0503bf-9265-4376-9dba-1d34c8a39045` score=`0.0000` trace_id=`0d08977068e3784834d8b5d8cddfb158`
- request_id=`b6dacdc3-cfba-4852-86fc-ef89e26d108b` score=`0.5000` trace_id=`d16c219c904df6116835595797b82f7c`

### Lowest answer_completeness requests
- request_id=`21c5eb65-a99b-45d5-90ee-7169075c823d` score=`0.0000` trace_id=`a16ad4e1fb3333df58cfe5409d84721d`
- request_id=`22c8536b-e693-443e-9f25-95be208c78b2` score=`0.0000` trace_id=`938b8183836f1c703b04747d24aa90d6`
- request_id=`35831186-d5e3-4495-9158-e40cde7ea7a2` score=`0.0000` trace_id=`741d196d54d4581be1d6c31a7184d431`
- request_id=`80b4b85a-6ce3-4b19-a78f-900fdaf1015b` score=`0.0000` trace_id=`beefb5ecac63a886c09ec0cf07f9939f`
- request_id=`ac0503bf-9265-4376-9dba-1d34c8a39045` score=`0.0000` trace_id=`0d08977068e3784834d8b5d8cddfb158`

## Token Usage

### Runtime
| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| runtime | 20 | 35,567 | 9,532 | 45,099 | 0.00177835 | 0.00190640 | 0.00368475 |

### Judge
| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| judge_generation | 80 | 75,851 | 24,294 | 100,145 | 0.00379255 | 0.00485880 | 0.00865135 |
| judge_retrieval | 240 | 152,952 | 53,674 | 206,626 | 0.00764760 | 0.01073480 | 0.01838240 |
| judge_total | 320 | 228,803 | 77,968 | 306,771 | 0.01144015 | 0.01559360 | 0.02703375 |

Run total cost usd = runtime total cost usd + judge total cost usd

Run total cost usd = 0.00368475 + 0.02703375 = 0.03071850

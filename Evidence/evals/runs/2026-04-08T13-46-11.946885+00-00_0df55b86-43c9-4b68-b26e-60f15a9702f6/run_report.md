# Eval Run Report

## Run Metadata
- run_id: `0df55b86-43c9-4b68-b26e-60f15a9702f6`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-08T13:46:11.946885+00:00`
- completed_at: `2026-04-08T13:48:50.222129+00:00`
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

## Aggregated Metrics
| metric | mean/rate | p50 | p90 | count |
|---|---:|---:|---:|---:|
| answer_completeness_mean | 0.8000 | 1.0000 | 1.0000 | 5 |
| groundedness_mean | 0.8000 | 1.0000 | 1.0000 | 5 |
| answer_relevance_mean | 0.8000 | 1.0000 | 1.0000 | 5 |
| correct_refusal_rate | 0.0000 | 0.0000 | 0.0000 | 5 |
| retrieval_relevance_mean | 0.2083 | 0.0000 | 0.5000 | 60 |
| retrieval_relevance_selected_mean | 0.3500 | 0.0000 | 1.0000 | 20 |
| retrieval_relevance_weighted_topk_mean | 0.4031 | 0.4175 | 0.5832 | 5 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 4 | 80.0% |
| answer_completeness | partial | 0 | 0.0% |
| answer_completeness | incomplete | 1 | 20.0% |
| groundedness | grounded | 4 | 80.0% |
| groundedness | partially_grounded | 0 | 0.0% |
| groundedness | ungrounded | 1 | 20.0% |
| answer_relevance | relevant | 4 | 80.0% |
| answer_relevance | partially_relevant | 0 | 0.0% |
| answer_relevance | irrelevant | 1 | 20.0% |
| correct_refusal | correct_refusal | 0 | 0.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 5 | 100.0% |

## Retrieval Quality

| set | Recall soft | Recall strict | MRR soft | MRR strict | nDCG |
|---|---:|---:|---:|---:|---:|
| top12 | 0.5100 | 0.7533 | 1.0000 | 1.0000 | 0.6169 |
| top4 | 0.2067 | 0.4200 | 1.0000 | 1.0000 | 0.6249 |

- retrieval_context_loss_soft: 0.3033
- retrieval_context_loss_strict: 0.3333
- avg_num_relevant_in_top12_soft: 6.0000
- avg_num_relevant_in_top12_strict: 2.8000
- avg_num_relevant_in_top4_soft: 2.4000
- avg_num_relevant_in_top4_strict: 1.4000

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for top12/top4 and soft/strict relevance.

| metric | top12_soft | top12_strict | top4_soft | top4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| answer_completeness_given_relevant_context | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| answer_relevance_given_relevant_context | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| hallucination_rate_when_top1_irrelevant | n/a | n/a | n/a | n/a |
| success_rate_when_at_least_one_relevant_in_topk | 0.8000 | 0.8000 | 0.8000 | 0.8000 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0_

_Definitions: hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`20fc5926-7ac4-46ec-b9d0-76b79c993907` score=`0.0000` trace_id=`b21f1154ecaf9d1cf8e3a01e64c4d476`
- request_id=`1f27a268-2b43-43b5-9bdf-5dec6c80b7a6` score=`1.0000` trace_id=`fde7d4023d044662afb5352a6ba0cf37`
- request_id=`78760315-2a5a-4735-830a-4973d189a6d7` score=`1.0000` trace_id=`00272b63944518f0e9544bd6926647a1`
- request_id=`ddc2c937-dcfb-4240-bc66-d5aa638e793e` score=`1.0000` trace_id=`0831e741a8f630dadac5068257057936`
- request_id=`eb543719-1fb8-41f4-9684-5eeb8f36d7e1` score=`1.0000` trace_id=`7826cc529f0f3253dcd6c8b6e46618fc`

### Lowest answer_completeness requests
- request_id=`20fc5926-7ac4-46ec-b9d0-76b79c993907` score=`0.0000` trace_id=`b21f1154ecaf9d1cf8e3a01e64c4d476`
- request_id=`1f27a268-2b43-43b5-9bdf-5dec6c80b7a6` score=`1.0000` trace_id=`fde7d4023d044662afb5352a6ba0cf37`
- request_id=`78760315-2a5a-4735-830a-4973d189a6d7` score=`1.0000` trace_id=`00272b63944518f0e9544bd6926647a1`
- request_id=`ddc2c937-dcfb-4240-bc66-d5aa638e793e` score=`1.0000` trace_id=`0831e741a8f630dadac5068257057936`
- request_id=`eb543719-1fb8-41f4-9684-5eeb8f36d7e1` score=`1.0000` trace_id=`7826cc529f0f3253dcd6c8b6e46618fc`

## Token Usage

### Runtime
| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| runtime | 5 | 11,313 | 2,270 | 13,583 | 0.00056565 | 0.00045400 | 0.00101965 |

### Judge
| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| judge_generation | 20 | 20,504 | 5,685 | 26,189 | 0.00102520 | 0.00113700 | 0.00216220 |
| judge_retrieval | 60 | 42,087 | 11,381 | 53,468 | 0.00210435 | 0.00227620 | 0.00438055 |
| judge_total | 80 | 62,591 | 17,066 | 79,657 | 0.00312955 | 0.00341320 | 0.00654275 |

Run total cost usd = runtime total cost usd + judge total cost usd

Run total cost usd = 0.00101965 + 0.00654275 = 0.00756240

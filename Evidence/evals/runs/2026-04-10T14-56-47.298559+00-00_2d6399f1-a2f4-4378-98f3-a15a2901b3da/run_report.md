# Eval Run Report

## Run Metadata
- eval_run_id: `2d6399f1-a2f4-4378-98f3-a15a2901b3da`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-10T14:56:47.298559+00:00`
- runtime_run_id: `f19c9cb8-44ff-4bb2-9467-e3674fd04fb4`
- completed_at: `2026-04-10T15:07:52.272454+00:00`
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
| answer_completeness_mean | 0.8000 | 1.0000 | 1.0000 | 20 |
| groundedness_mean | 0.8000 | 1.0000 | 1.0000 | 20 |
| answer_relevance_mean | 0.8000 | 1.0000 | 1.0000 | 20 |
| correct_refusal_rate | 0.0000 | 0.0000 | 0.0000 | 20 |
| retrieval_relevance_mean | 0.3333 | 0.5000 | 1.0000 | 150 |
| retrieval_relevance_selected_mean | 0.4688 | 0.5000 | 1.0000 | 80 |
| retrieval_relevance_weighted_topk_mean | 0.4786 | 0.4660 | 0.6171 | 20 |

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
| correct_refusal | unnecessary_refusal | 1 | 5.0% |
| correct_refusal | non_refusal | 19 | 95.0% |

## Retrieval Quality

| set | Recall soft | Recall strict | MRR soft | MRR strict | nDCG |
|---|---:|---:|---:|---:|---:|
| retrieval@12 | 0.5582 | 0.7833 | 0.9167 | 0.9167 | 0.6586 |
| generation_context@4 | 0.3789 | 0.7042 | 0.9167 | 0.9167 | 0.6694 |

- retrieval_context_loss_soft: 0.1794
- retrieval_context_loss_strict: 0.0792
- avg_num_relevant_in_retrieval@12_soft: 3.4500
- avg_num_relevant_in_retrieval@12_strict: 2.2500
- avg_num_relevant_in_generation_context@4_soft: 2.3500
- avg_num_relevant_in_generation_context@4_strict: 2.0000

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for retrieval@12/generation_context@4 and soft/strict relevance.

| metric | retrieval@12_soft | retrieval@12_strict | generation_context@4_soft | generation_context@4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| answer_completeness_given_relevant_context | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| answer_relevance_given_relevant_context | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| hallucination_rate_when_top1_irrelevant | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| success_rate_when_at_least_one_relevant_in_topk | 0.8000 | 0.8000 | 0.8000 | 0.8000 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0_

_Definitions: hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`48b51a33-d06b-4323-b401-14dd5652ea0c` score=`0.0000` trace_id=`9ccc37088c963b4477f38881a1e14e52`
- request_id=`4984adbd-187e-41bc-92ec-4f66e8b26b9b` score=`0.0000` trace_id=`65874d455227db3937d5ada0703dcaf9`
- request_id=`7227400a-6dd0-407c-bc21-72a21db8defe` score=`0.0000` trace_id=`81e0e9d43d270f064e7108ffccec0d72`
- request_id=`d5e14976-6613-4f5e-a10a-d1ff21ab3a1e` score=`0.0000` trace_id=`c07d945c73f0f3d82e873579f77a66c5`
- request_id=`26a08482-0bb8-4aee-bbff-307dbb33389a` score=`1.0000` trace_id=`324ec2c627cad6e31adb22240d0c06e4`

### Lowest answer_completeness requests
- request_id=`48b51a33-d06b-4323-b401-14dd5652ea0c` score=`0.0000` trace_id=`9ccc37088c963b4477f38881a1e14e52`
- request_id=`4984adbd-187e-41bc-92ec-4f66e8b26b9b` score=`0.0000` trace_id=`65874d455227db3937d5ada0703dcaf9`
- request_id=`7227400a-6dd0-407c-bc21-72a21db8defe` score=`0.0000` trace_id=`81e0e9d43d270f064e7108ffccec0d72`
- request_id=`d5e14976-6613-4f5e-a10a-d1ff21ab3a1e` score=`0.0000` trace_id=`c07d945c73f0f3d82e873579f77a66c5`
- request_id=`26a08482-0bb8-4aee-bbff-307dbb33389a` score=`1.0000` trace_id=`324ec2c627cad6e31adb22240d0c06e4`

## Token Usage

### Runtime
| scope | requests | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| runtime | 20 | 36,083 | 9,896 | 45,979 | 0.00180415 | 0.00197920 | 0.00378335 |

### Judge
| scope | eval calls | prompt tokens | completion tokens | total tokens | prompt cost usd | completion cost usd | total cost usd |
|---|---:|---:|---:|---:|---:|---:|---:|
| judge_generation | 80 | 76,413 | 23,402 | 99,815 | 0.00382065 | 0.00468040 | 0.00850105 |
| judge_retrieval | 150 | 96,558 | 31,833 | 128,391 | 0.00482790 | 0.00636660 | 0.01119450 |
| judge_total | 230 | 172,971 | 55,235 | 228,206 | 0.00864855 | 0.01104700 | 0.01969555 |

Run total cost usd = runtime total cost usd + judge total cost usd

Run total cost usd = 0.00378335 + 0.01969555 = 0.02347890

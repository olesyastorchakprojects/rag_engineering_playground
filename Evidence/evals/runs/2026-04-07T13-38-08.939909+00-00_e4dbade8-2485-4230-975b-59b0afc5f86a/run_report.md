# Eval Run Report

## Run Metadata
- run_id: `e4dbade8-2485-4230-975b-59b0afc5f86a`
- run_type: `experiment`
- status: `completed`
- started_at: `2026-04-07T13:38:08.939909+00:00`
- completed_at: `2026-04-07T14:02:37.335938+00:00`
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
| answer_completeness_mean | 0.9000 | 1.0000 | 1.0000 | 5 |
| groundedness_mean | 0.5000 | 0.5000 | 1.0000 | 5 |
| answer_relevance_mean | 1.0000 | 1.0000 | 1.0000 | 5 |
| correct_refusal_rate | 1.0000 | 1.0000 | 1.0000 | 5 |
| retrieval_relevance_mean | 0.2833 | 0.0000 | 1.0000 | 60 |
| retrieval_relevance_selected_mean | 0.3500 | 0.0000 | 1.0000 | 20 |
| retrieval_relevance_weighted_topk_mean | 0.3292 | 0.3357 | 0.5965 | 5 |

## Label Distributions
| suite | label | count | percent |
|---|---|---:|---:|
| answer_completeness | complete | 4 | 80.0% |
| answer_completeness | partial | 1 | 20.0% |
| answer_completeness | incomplete | 0 | 0.0% |
| groundedness | grounded | 2 | 40.0% |
| groundedness | partially_grounded | 1 | 20.0% |
| groundedness | ungrounded | 2 | 40.0% |
| answer_relevance | relevant | 5 | 100.0% |
| answer_relevance | partially_relevant | 0 | 0.0% |
| answer_relevance | irrelevant | 0 | 0.0% |
| correct_refusal | correct_refusal | 5 | 100.0% |
| correct_refusal | unnecessary_refusal | 0 | 0.0% |
| correct_refusal | non_refusal | 0 | 0.0% |

## Retrieval Quality

| set | Recall soft | Recall strict | MRR soft | MRR strict | nDCG |
|---|---:|---:|---:|---:|---:|
| top12 | 0.5100 | 0.7533 | 1.0000 | 1.0000 | 0.6169 |
| top4 | 0.2733 | 0.5933 | 1.0000 | 1.0000 | 0.7875 |

- retrieval_context_loss_soft: 0.2367
- retrieval_context_loss_strict: 0.1600
- avg_num_relevant_in_top12_soft: 6.0000
- avg_num_relevant_in_top12_strict: 2.8000
- avg_num_relevant_in_top4_soft: 3.2000
- avg_num_relevant_in_top4_strict: 2.0000

## Conditional Retrieval→Generation Aggregates

These aggregates show generation quality conditioned on whether retrieval supplied relevant context, separately for top12/top4 and soft/strict relevance.

| metric | top12_soft | top12_strict | top4_soft | top4_strict |
|---|---:|---:|---:|---:|
| groundedness_given_relevant_context | 0.5000 | 0.5000 | 0.5000 | 0.5000 |
| answer_completeness_given_relevant_context | 0.9000 | 0.9000 | 0.9000 | 0.9000 |
| answer_relevance_given_relevant_context | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| hallucination_rate_when_top1_irrelevant | n/a | n/a | n/a | n/a |
| success_rate_when_at_least_one_relevant_in_topk | 0.4000 | 0.4000 | 0.4000 | 0.4000 |

_Definitions: success = groundedness == 1.0 AND answer\_completeness == 1.0; hallucinated = groundedness < 1.0_

## Worst-Case Preview
### Lowest groundedness requests
- request_id=`4f036c4a-3b77-48a7-91e0-7135b6733551` score=`0.0000` trace_id=`691f80901d45e9e05cafc6384c4f6a23`
- request_id=`7ef20247-840c-4c9c-813d-cc7abab14eaf` score=`0.0000` trace_id=`133f43a700a645ebc7c1472c4ac2b27e`
- request_id=`fd13ac14-926d-4393-8efe-fe178ede1169` score=`0.5000` trace_id=`ecc8758dc3bd6ae966991e47031de782`
- request_id=`5b1896ff-872b-4a49-a609-63d2dd3ec799` score=`1.0000` trace_id=`9165325b0cbadc97c28791a1cbc9f70c`
- request_id=`65f65ff3-363e-42c3-af18-e6079f6192a6` score=`1.0000` trace_id=`7d023bf0202237c1e90dbb9e063a61da`

### Lowest answer_completeness requests
- request_id=`4f036c4a-3b77-48a7-91e0-7135b6733551` score=`0.5000` trace_id=`691f80901d45e9e05cafc6384c4f6a23`
- request_id=`5b1896ff-872b-4a49-a609-63d2dd3ec799` score=`1.0000` trace_id=`9165325b0cbadc97c28791a1cbc9f70c`
- request_id=`65f65ff3-363e-42c3-af18-e6079f6192a6` score=`1.0000` trace_id=`7d023bf0202237c1e90dbb9e063a61da`
- request_id=`7ef20247-840c-4c9c-813d-cc7abab14eaf` score=`1.0000` trace_id=`133f43a700a645ebc7c1472c4ac2b27e`
- request_id=`fd13ac14-926d-4393-8efe-fe178ede1169` score=`1.0000` trace_id=`ecc8758dc3bd6ae966991e47031de782`

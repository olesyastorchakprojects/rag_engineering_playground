create table if not exists request_summaries (
    request_id text primary key,
    trace_id text not null,
    source_received_at timestamptz not null,
    summarized_at timestamptz not null default now(),

    raw_query text not null,
    normalized_query text not null,
    input_token_count integer not null,
    pipeline_config_version text not null,
    corpus_version text not null,
    retriever_version text not null,
    retriever_kind text not null,
    embedding_model text not null,
    reranker_kind text not null,
    prompt_template_id text not null,
    prompt_template_version text not null,
    generation_model text not null,
    top_k_requested integer not null,
    final_answer text not null,
    prompt_tokens integer not null,
    completion_tokens integer not null,
    total_tokens integer not null,

    answer_completeness_score numeric(6,4),
    answer_completeness_label text,
    groundedness_score numeric(6,4),
    groundedness_label text,
    answer_relevance_score numeric(6,4),
    answer_relevance_label text,
    correct_refusal_score numeric(6,4),
    correct_refusal_label text,

    retrieval_relevance_mean numeric(6,4),
    retrieval_relevance_selected_mean numeric(6,4),
    retrieval_relevance_topk_mean numeric(6,4),
    retrieval_relevance_weighted_topk numeric(6,4),
    retrieval_relevance_relevant_count integer,
    retrieval_relevance_selected_count integer,
    retrieval_chunk_count integer,

    retrieval_evaluated_k integer,
    retrieval_recall_soft numeric(6,4),
    retrieval_recall_strict numeric(6,4),
    retrieval_rr_soft numeric(6,4),
    retrieval_rr_strict numeric(6,4),
    retrieval_ndcg numeric(6,4),
    retrieval_first_relevant_rank_soft integer,
    retrieval_first_relevant_rank_strict integer,
    retrieval_num_relevant_soft integer,
    retrieval_num_relevant_strict integer,

    reranking_evaluated_k integer,
    reranking_recall_soft numeric(6,4),
    reranking_recall_strict numeric(6,4),
    reranking_rr_soft numeric(6,4),
    reranking_rr_strict numeric(6,4),
    reranking_ndcg numeric(6,4),
    reranking_first_relevant_rank_soft integer,
    reranking_first_relevant_rank_strict integer,
    reranking_num_relevant_soft integer,
    reranking_num_relevant_strict integer,

    retrieval_context_loss_soft numeric(6,4),
    retrieval_context_loss_strict numeric(6,4),

    constraint request_summaries_request_id_nonempty_check
        check (length(btrim(request_id)) > 0),
    constraint request_summaries_trace_id_nonempty_check
        check (length(btrim(trace_id)) > 0),
    constraint request_summaries_raw_query_nonempty_check
        check (length(btrim(raw_query)) > 0),
    constraint request_summaries_normalized_query_nonempty_check
        check (length(btrim(normalized_query)) > 0),
    constraint request_summaries_pipeline_config_version_nonempty_check
        check (length(btrim(pipeline_config_version)) > 0),
    constraint request_summaries_corpus_version_nonempty_check
        check (length(btrim(corpus_version)) > 0),
    constraint request_summaries_retriever_version_nonempty_check
        check (length(btrim(retriever_version)) > 0),
    constraint request_summaries_retriever_kind_check
        check (retriever_kind in ('Dense', 'Hybrid')),
    constraint request_summaries_embedding_model_nonempty_check
        check (length(btrim(embedding_model)) > 0),
    constraint request_summaries_reranker_kind_nonempty_check
        check (length(btrim(reranker_kind)) > 0),
    constraint request_summaries_prompt_template_id_nonempty_check
        check (length(btrim(prompt_template_id)) > 0),
    constraint request_summaries_prompt_template_version_nonempty_check
        check (length(btrim(prompt_template_version)) > 0),
    constraint request_summaries_generation_model_nonempty_check
        check (length(btrim(generation_model)) > 0),
    constraint request_summaries_final_answer_nonempty_check
        check (length(btrim(final_answer)) > 0),
    constraint request_summaries_answer_completeness_label_nonempty_check
        check (answer_completeness_label is null or length(btrim(answer_completeness_label)) > 0),
    constraint request_summaries_groundedness_label_nonempty_check
        check (groundedness_label is null or length(btrim(groundedness_label)) > 0),
    constraint request_summaries_answer_relevance_label_nonempty_check
        check (answer_relevance_label is null or length(btrim(answer_relevance_label)) > 0),
    constraint request_summaries_correct_refusal_label_nonempty_check
        check (correct_refusal_label is null or length(btrim(correct_refusal_label)) > 0),
    constraint request_summaries_input_token_count_check
        check (input_token_count >= 1),
    constraint request_summaries_top_k_requested_check
        check (top_k_requested >= 1),
    constraint request_summaries_prompt_tokens_check
        check (prompt_tokens >= 0),
    constraint request_summaries_completion_tokens_check
        check (completion_tokens >= 0),
    constraint request_summaries_total_tokens_nonnegative_check
        check (total_tokens >= 0),
    constraint request_summaries_total_tokens_sum_check
        check (total_tokens = prompt_tokens + completion_tokens),
    constraint request_summaries_retrieval_relevant_count_check
        check (retrieval_relevance_relevant_count is null or retrieval_relevance_relevant_count >= 0),
    constraint request_summaries_retrieval_selected_count_check
        check (retrieval_relevance_selected_count is null or retrieval_relevance_selected_count >= 0),
    constraint request_summaries_retrieval_chunk_count_check
        check (retrieval_chunk_count is null or retrieval_chunk_count >= 0),
    constraint request_summaries_retrieval_selected_le_chunk_count_check
        check (
            retrieval_relevance_selected_count is null
            or retrieval_chunk_count is null
            or retrieval_relevance_selected_count <= retrieval_chunk_count
        ),
    constraint request_summaries_retrieval_relevant_le_chunk_count_check
        check (
            retrieval_relevance_relevant_count is null
            or retrieval_chunk_count is null
            or retrieval_relevance_relevant_count <= retrieval_chunk_count
        )
);

create index if not exists idx_request_summaries_source_received_at
    on request_summaries (source_received_at);

create index if not exists idx_request_summaries_trace_id
    on request_summaries (trace_id);

create index if not exists idx_request_summaries_pipeline_config_version
    on request_summaries (pipeline_config_version);

create index if not exists idx_request_summaries_retriever_version
    on request_summaries (retriever_version);

create index if not exists idx_request_summaries_reranker_kind
    on request_summaries (reranker_kind);

create index if not exists idx_request_summaries_prompt_template_version
    on request_summaries (prompt_template_version);

create index if not exists idx_request_summaries_generation_model
    on request_summaries (generation_model);

alter table request_summaries
    add column if not exists retriever_kind text;

update request_summaries
set retriever_kind = 'Dense'
where retriever_kind is null;

alter table request_summaries
    alter column retriever_kind set not null;

alter table request_summaries
    drop constraint if exists request_summaries_retriever_kind_check;

alter table request_summaries
    add constraint request_summaries_retriever_kind_check
        check (retriever_kind in ('Dense', 'Hybrid'));

create index if not exists idx_request_summaries_retriever_kind
    on request_summaries (retriever_kind);

alter table request_summaries
    add column if not exists retrieval_evaluated_k integer;

alter table request_summaries
    add column if not exists retrieval_recall_soft numeric(6,4);

alter table request_summaries
    add column if not exists retrieval_recall_strict numeric(6,4);

alter table request_summaries
    add column if not exists retrieval_rr_soft numeric(6,4);

alter table request_summaries
    add column if not exists retrieval_rr_strict numeric(6,4);

alter table request_summaries
    add column if not exists retrieval_ndcg numeric(6,4);

alter table request_summaries
    add column if not exists retrieval_first_relevant_rank_soft integer;

alter table request_summaries
    add column if not exists retrieval_first_relevant_rank_strict integer;

alter table request_summaries
    add column if not exists retrieval_num_relevant_soft integer;

alter table request_summaries
    add column if not exists retrieval_num_relevant_strict integer;

alter table request_summaries
    add column if not exists reranking_evaluated_k integer;

alter table request_summaries
    add column if not exists reranking_recall_soft numeric(6,4);

alter table request_summaries
    add column if not exists reranking_recall_strict numeric(6,4);

alter table request_summaries
    add column if not exists reranking_rr_soft numeric(6,4);

alter table request_summaries
    add column if not exists reranking_rr_strict numeric(6,4);

alter table request_summaries
    add column if not exists reranking_ndcg numeric(6,4);

alter table request_summaries
    add column if not exists reranking_first_relevant_rank_soft integer;

alter table request_summaries
    add column if not exists reranking_first_relevant_rank_strict integer;

alter table request_summaries
    add column if not exists reranking_num_relevant_soft integer;

alter table request_summaries
    add column if not exists reranking_num_relevant_strict integer;

alter table request_summaries
    add column if not exists retrieval_context_loss_soft numeric(6,4);

alter table request_summaries
    add column if not exists retrieval_context_loss_strict numeric(6,4);

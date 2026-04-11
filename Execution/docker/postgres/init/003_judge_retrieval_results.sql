do $$
begin
    if not exists (
        select 1
        from pg_type
        where typname = 'judge_retrieval_suite'
    ) then
        create type judge_retrieval_suite as enum (
            'retrieval_relevance'
        );
    end if;
end
$$;

create table if not exists judge_retrieval_results (
    request_id text not null,
    run_id text not null,
    trace_id text not null,
    chunk_id text not null,
    created_at timestamptz not null default now(),

    document_id text not null,
    retrieval_rank integer not null,
    retrieval_score numeric(12,6) not null,
    selected_for_generation boolean not null,

    suite_name judge_retrieval_suite not null,
    judge_model text not null,
    judge_prompt_version text not null,

    score numeric(6,4),
    label text,
    explanation text,
    raw_response jsonb not null,

    primary key (request_id, run_id, suite_name, chunk_id),

    constraint judge_retrieval_results_request_id_nonempty_check
        check (length(btrim(request_id)) > 0),
    constraint judge_retrieval_results_run_id_nonempty_check
        check (length(btrim(run_id)) > 0),
    constraint judge_retrieval_results_trace_id_nonempty_check
        check (length(btrim(trace_id)) > 0),
    constraint judge_retrieval_results_chunk_id_nonempty_check
        check (length(btrim(chunk_id)) > 0),
    constraint judge_retrieval_results_document_id_nonempty_check
        check (length(btrim(document_id)) > 0),
    constraint judge_retrieval_results_judge_model_nonempty_check
        check (length(btrim(judge_model)) > 0),
    constraint judge_retrieval_results_judge_prompt_version_nonempty_check
        check (length(btrim(judge_prompt_version)) > 0),
    constraint judge_retrieval_results_label_nonempty_check
        check (label is null or length(btrim(label)) > 0),
    constraint judge_retrieval_results_explanation_nonempty_check
        check (explanation is null or length(btrim(explanation)) > 0),
    constraint judge_retrieval_results_retrieval_rank_check
        check (retrieval_rank >= 1),
    constraint judge_retrieval_results_raw_response_object_check
        check (jsonb_typeof(raw_response) = 'object')
);

create index if not exists idx_judge_retrieval_results_run_id
    on judge_retrieval_results (run_id);

create index if not exists idx_judge_retrieval_results_suite_name
    on judge_retrieval_results (suite_name);

create index if not exists idx_judge_retrieval_results_request_id
    on judge_retrieval_results (request_id);

create index if not exists idx_judge_retrieval_results_chunk_id
    on judge_retrieval_results (chunk_id);

create index if not exists idx_judge_retrieval_results_created_at
    on judge_retrieval_results (created_at);

create index if not exists idx_judge_retrieval_results_request_rank
    on judge_retrieval_results (request_id, retrieval_rank);

create index if not exists idx_judge_retrieval_results_request_selected
    on judge_retrieval_results (request_id, selected_for_generation);

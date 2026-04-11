do $$
begin
    if not exists (
        select 1
        from pg_type
        where typname = 'judge_generation_suite'
    ) then
        create type judge_generation_suite as enum (
            'answer_completeness',
            'groundedness',
            'answer_relevance',
            'correct_refusal'
        );
    end if;
end
$$;

create table if not exists judge_generation_results (
    request_id text not null,
    run_id text not null,
    trace_id text not null,
    created_at timestamptz not null default now(),

    suite_name judge_generation_suite not null,
    judge_model text not null,
    judge_prompt_version text not null,

    score numeric(6,4),
    label text,
    explanation text,
    raw_response jsonb not null,

    primary key (request_id, run_id, suite_name),

    constraint judge_generation_results_request_id_nonempty_check
        check (length(btrim(request_id)) > 0),
    constraint judge_generation_results_run_id_nonempty_check
        check (length(btrim(run_id)) > 0),
    constraint judge_generation_results_trace_id_nonempty_check
        check (length(btrim(trace_id)) > 0),
    constraint judge_generation_results_judge_model_nonempty_check
        check (length(btrim(judge_model)) > 0),
    constraint judge_generation_results_judge_prompt_version_nonempty_check
        check (length(btrim(judge_prompt_version)) > 0),
    constraint judge_generation_results_label_nonempty_check
        check (label is null or length(btrim(label)) > 0),
    constraint judge_generation_results_explanation_nonempty_check
        check (explanation is null or length(btrim(explanation)) > 0),
    constraint judge_generation_results_raw_response_object_check
        check (jsonb_typeof(raw_response) = 'object')
);

create index if not exists idx_judge_generation_results_run_id
    on judge_generation_results (run_id);

create index if not exists idx_judge_generation_results_suite_name
    on judge_generation_results (suite_name);

create index if not exists idx_judge_generation_results_request_id
    on judge_generation_results (request_id);

create index if not exists idx_judge_generation_results_created_at
    on judge_generation_results (created_at);

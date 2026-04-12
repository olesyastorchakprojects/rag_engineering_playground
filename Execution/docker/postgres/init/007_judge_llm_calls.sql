create table if not exists judge_llm_calls (
    call_id text primary key,
    request_id text not null,
    run_id text not null,
    trace_id text not null,
    created_at timestamptz not null default now(),

    stage_name text not null,
    suite_name text,
    chunk_id text,
    judge_provider text not null,
    judge_model text not null,
    judge_prompt_version text not null,
    token_count_source text not null,
    raw_response jsonb null,

    prompt_tokens integer not null,
    completion_tokens integer not null,
    total_tokens integer not null,

    input_cost_per_million_tokens numeric(12, 6) not null,
    output_cost_per_million_tokens numeric(12, 6) not null,
    total_cost_usd numeric(12, 8) not null,

    constraint judge_llm_calls_call_id_nonempty_check
        check (length(btrim(call_id)) > 0),
    constraint judge_llm_calls_request_id_nonempty_check
        check (length(btrim(request_id)) > 0),
    constraint judge_llm_calls_run_id_nonempty_check
        check (length(btrim(run_id)) > 0),
    constraint judge_llm_calls_trace_id_nonempty_check
        check (length(btrim(trace_id)) > 0),
    constraint judge_llm_calls_stage_name_nonempty_check
        check (length(btrim(stage_name)) > 0),
    constraint judge_llm_calls_suite_name_nonempty_check
        check (suite_name is null or length(btrim(suite_name)) > 0),
    constraint judge_llm_calls_chunk_id_nonempty_check
        check (chunk_id is null or length(btrim(chunk_id)) > 0),
    constraint judge_llm_calls_judge_provider_nonempty_check
        check (length(btrim(judge_provider)) > 0),
    constraint judge_llm_calls_judge_model_nonempty_check
        check (length(btrim(judge_model)) > 0),
    constraint judge_llm_calls_judge_prompt_version_nonempty_check
        check (length(btrim(judge_prompt_version)) > 0),
    constraint judge_llm_calls_token_count_source_nonempty_check
        check (length(btrim(token_count_source)) > 0),
    constraint judge_llm_calls_raw_response_object_check
        check (raw_response is null or jsonb_typeof(raw_response) = 'object'),
    constraint judge_llm_calls_stage_name_check
        check (stage_name in ('judge_generation', 'judge_retrieval')),
    constraint judge_llm_calls_token_count_source_check
        check (token_count_source in ('provider_usage', 'ollama_native_usage', 'local_estimate')),
    constraint judge_llm_calls_prompt_tokens_check
        check (prompt_tokens >= 0),
    constraint judge_llm_calls_completion_tokens_check
        check (completion_tokens >= 0),
    constraint judge_llm_calls_total_tokens_check
        check (total_tokens = prompt_tokens + completion_tokens),
    constraint judge_llm_calls_input_cost_check
        check (input_cost_per_million_tokens >= 0),
    constraint judge_llm_calls_output_cost_check
        check (output_cost_per_million_tokens >= 0),
    constraint judge_llm_calls_total_cost_check
        check (total_cost_usd >= 0)
);

create index if not exists idx_judge_llm_calls_run_id
    on judge_llm_calls (run_id);

create index if not exists idx_judge_llm_calls_request_id
    on judge_llm_calls (request_id);

create index if not exists idx_judge_llm_calls_run_stage
    on judge_llm_calls (run_id, stage_name);

create index if not exists idx_judge_llm_calls_created_at
    on judge_llm_calls (created_at);

alter table judge_llm_calls
    add column if not exists raw_response jsonb;

update judge_llm_calls
set raw_response = '{}'::jsonb
where raw_response is null;

alter table judge_llm_calls
    drop constraint if exists judge_llm_calls_raw_response_object_check;

alter table judge_llm_calls
    add constraint judge_llm_calls_raw_response_object_check
        check (raw_response is null or jsonb_typeof(raw_response) = 'object');

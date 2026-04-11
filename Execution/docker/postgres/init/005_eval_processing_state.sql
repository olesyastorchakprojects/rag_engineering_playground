do $$
begin
    if not exists (
        select 1
        from pg_type
        where typname = 'eval_processing_stage'
    ) then
        create type eval_processing_stage as enum (
            'judge_generation',
            'judge_retrieval',
            'build_request_summary'
        );
    end if;
end
$$;

do $$
begin
    if not exists (
        select 1
        from pg_type
        where typname = 'eval_processing_status'
    ) then
        create type eval_processing_status as enum (
            'pending',
            'running',
            'completed',
            'failed'
        );
    end if;
end
$$;

create table if not exists eval_processing_state (
    request_id text primary key,
    request_received_at timestamptz not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    current_stage eval_processing_stage not null,
    status eval_processing_status not null,

    attempt_count integer not null default 0,
    started_at timestamptz,
    completed_at timestamptz,
    last_error text,

    constraint eval_processing_state_request_id_nonempty_check
        check (length(btrim(request_id)) > 0),
    constraint eval_processing_state_attempt_count_check
        check (attempt_count >= 0),
    constraint eval_processing_state_last_error_nonempty_check
        check (last_error is null or length(btrim(last_error)) > 0)
);

create index if not exists idx_eval_processing_state_status_received_request
    on eval_processing_state (status, request_received_at, request_id);

create index if not exists idx_eval_processing_state_current_stage
    on eval_processing_state (current_stage);

create index if not exists idx_eval_processing_state_updated_at
    on eval_processing_state (updated_at);

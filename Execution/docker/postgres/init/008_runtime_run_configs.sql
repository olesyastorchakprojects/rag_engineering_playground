create table if not exists runtime_run_configs (
    runtime_run_id text primary key,
    created_at timestamptz not null default now(),
    config_version text not null,
    runtime_config_json jsonb not null,

    constraint runtime_run_configs_runtime_run_id_nonempty_check
        check (length(btrim(runtime_run_id)) > 0),
    constraint runtime_run_configs_config_version_nonempty_check
        check (length(btrim(config_version)) > 0),
    constraint runtime_run_configs_runtime_config_json_object_check
        check (jsonb_typeof(runtime_config_json) = 'object')
);

create index if not exists idx_runtime_run_configs_created_at
    on runtime_run_configs (created_at);

alter table request_captures
    add column if not exists runtime_run_id text null;

alter table request_captures
    drop constraint if exists request_captures_runtime_run_id_fkey;

alter table request_captures
    add constraint request_captures_runtime_run_id_fkey
        foreign key (runtime_run_id) references runtime_run_configs (runtime_run_id);

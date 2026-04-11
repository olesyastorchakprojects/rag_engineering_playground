create table if not exists eval_run_configs (
    eval_run_id text primary key,
    created_at timestamptz not null default now(),
    config_version text not null,
    eval_config_json jsonb not null,

    constraint eval_run_configs_eval_run_id_nonempty_check
        check (length(btrim(eval_run_id)) > 0),
    constraint eval_run_configs_config_version_nonempty_check
        check (length(btrim(config_version)) > 0),
    constraint eval_run_configs_eval_config_json_object_check
        check (jsonb_typeof(eval_config_json) = 'object')
);

create index if not exists idx_eval_run_configs_created_at
    on eval_run_configs (created_at);

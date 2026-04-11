create or replace function request_capture_retrieval_results_items_are_valid(data jsonb)
returns boolean
language sql
immutable
as $$
    select case
        when jsonb_typeof(data) <> 'array' then false
        else not exists (
            select 1
            from jsonb_array_elements(data) as item
            where case
                when jsonb_typeof(item) <> 'object' then true
                when exists (
                    select 1
                    from jsonb_object_keys(item) as key_name
                    where key_name not in (
                        'chunk_id',
                        'document_id',
                        'locator',
                        'retrieval_score',
                        'rerank_score',
                        'selected_for_generation'
                    )
                ) then true
                when not (
                    item ? 'chunk_id'
                    and item ? 'document_id'
                    and item ? 'locator'
                    and item ? 'retrieval_score'
                    and item ? 'rerank_score'
                    and item ? 'selected_for_generation'
                ) then true
                when jsonb_typeof(item->'chunk_id') <> 'string' then true
                when jsonb_typeof(item->'document_id') <> 'string' then true
                when jsonb_typeof(item->'locator') <> 'string' then true
                when jsonb_typeof(item->'retrieval_score') <> 'number' then true
                when jsonb_typeof(item->'rerank_score') <> 'number' then true
                when jsonb_typeof(item->'selected_for_generation') <> 'boolean' then true
                when length(btrim(item->>'chunk_id')) = 0 then true
                when length(btrim(item->>'document_id')) = 0 then true
                when length(btrim(item->>'locator')) = 0 then true
                else false
            end
        )
    end
$$;

create or replace function request_capture_generation_config_is_valid(data jsonb)
returns boolean
language sql
immutable
as $$
    select
        jsonb_typeof(data) = 'object'
        and not exists (
            select 1
            from jsonb_object_keys(data) as key_name
            where key_name not in (
                'model',
                'model_endpoint',
                'temperature',
                'max_context_chunks',
                'input_cost_per_million_tokens',
                'output_cost_per_million_tokens'
            )
        )
        and data ? 'model'
        and data ? 'model_endpoint'
        and data ? 'temperature'
        and data ? 'max_context_chunks'
        and data ? 'input_cost_per_million_tokens'
        and data ? 'output_cost_per_million_tokens'
        and jsonb_typeof(data->'model') = 'string'
        and jsonb_typeof(data->'model_endpoint') = 'string'
        and jsonb_typeof(data->'temperature') = 'number'
        and jsonb_typeof(data->'max_context_chunks') = 'number'
        and jsonb_typeof(data->'input_cost_per_million_tokens') = 'number'
        and jsonb_typeof(data->'output_cost_per_million_tokens') = 'number'
        and length(btrim(data->>'model')) > 0
        and length(btrim(data->>'model_endpoint')) > 0
$$;

create or replace function request_capture_reranker_config_is_valid(data jsonb)
returns boolean
language sql
immutable
as $$
    select case
        when jsonb_typeof(data) <> 'object' then false
        when not (data ? 'kind') then false
        when data->>'kind' = 'Heuristic' then case
            when exists (
                select 1
                from jsonb_object_keys(data) as key_name
                where key_name not in (
                    'kind',
                    'final_k',
                    'weights'
                )
            ) then false
            when not (data ? 'weights') then false
            when jsonb_typeof(data->'weights') <> 'object' then false
            when exists (
                select 1
                from jsonb_object_keys(data->'weights') as key_name
                where key_name not in (
                    'retrieval_score',
                    'query_term_coverage',
                    'phrase_match_bonus',
                    'title_section_match_bonus'
                )
            ) then false
            when not (
                data->'weights' ? 'retrieval_score'
                and data->'weights' ? 'query_term_coverage'
                and data->'weights' ? 'phrase_match_bonus'
                and data->'weights' ? 'title_section_match_bonus'
            ) then false
            when jsonb_typeof(data->'weights'->'retrieval_score') <> 'number' then false
            when jsonb_typeof(data->'weights'->'query_term_coverage') <> 'number' then false
            when jsonb_typeof(data->'weights'->'phrase_match_bonus') <> 'number' then false
            when jsonb_typeof(data->'weights'->'title_section_match_bonus') <> 'number' then false
            else true
        end
        when data->>'kind' = 'CrossEncoder' then case
            when exists (
                select 1
                from jsonb_object_keys(data) as key_name
                where key_name not in (
                    'kind',
                    'final_k',
                    'cross_encoder'
                )
            ) then false
            when not (data ? 'cross_encoder') then false
            when jsonb_typeof(data->'cross_encoder') <> 'object' then false
            when exists (
                select 1
                from jsonb_object_keys(data->'cross_encoder') as key_name
                where key_name not in (
                    'model_name',
                    'url',
                    'total_tokens',
                    'cost_per_million_tokens'
                )
            ) then false
            when not (
                data->'cross_encoder' ? 'model_name'
                and data->'cross_encoder' ? 'url'
                and data->'cross_encoder' ? 'total_tokens'
                and data->'cross_encoder' ? 'cost_per_million_tokens'
            ) then false
            when jsonb_typeof(data->'cross_encoder'->'model_name') <> 'string' then false
            when jsonb_typeof(data->'cross_encoder'->'url') <> 'string' then false
            when jsonb_typeof(data->'cross_encoder'->'total_tokens') <> 'number' then false
            when jsonb_typeof(data->'cross_encoder'->'cost_per_million_tokens') <> 'number' then false
            when length(btrim(data->'cross_encoder'->>'model_name')) = 0 then false
            when length(btrim(data->'cross_encoder'->>'url')) = 0 then false
            else true
        end
        else false
    end
$$;

create table if not exists request_captures (
    runtime_run_id text null,
    request_id text primary key,
    trace_id text not null,
    received_at timestamptz not null,

    raw_query text not null,
    normalized_query text not null,
    input_token_count integer not null,

    pipeline_config_version text not null,
    corpus_version text not null,
    retriever_version text not null,
    retriever_kind text not null,
    retriever_config jsonb not null,
    embedding_model text not null,
    prompt_template_id text not null,
    prompt_template_version text not null,
    generation_model text not null,
    generation_config jsonb not null,
    reranker_kind text not null,
    reranker_config jsonb null,

    top_k_requested integer not null,
    retrieval_results jsonb not null,

    final_answer text not null,
    prompt_tokens integer not null,
    completion_tokens integer not null,
    total_tokens integer not null,

    retrieval_stage_metrics jsonb null,
    reranking_stage_metrics jsonb null,

    stored_at timestamptz not null default now(),

    constraint request_captures_runtime_run_id_nonempty_check
        check (runtime_run_id is null or length(btrim(runtime_run_id)) > 0),
    constraint request_captures_request_id_nonempty_check
        check (length(btrim(request_id)) > 0),
    constraint request_captures_trace_id_nonempty_check
        check (length(btrim(trace_id)) > 0),
    constraint request_captures_raw_query_nonempty_check
        check (length(btrim(raw_query)) > 0),
    constraint request_captures_normalized_query_nonempty_check
        check (length(btrim(normalized_query)) > 0),
    constraint request_captures_pipeline_config_version_nonempty_check
        check (length(btrim(pipeline_config_version)) > 0),
    constraint request_captures_corpus_version_nonempty_check
        check (length(btrim(corpus_version)) > 0),
    constraint request_captures_retriever_version_nonempty_check
        check (length(btrim(retriever_version)) > 0),
    constraint request_captures_retriever_kind_check
        check (retriever_kind in ('Dense', 'Hybrid')),
    constraint request_captures_retriever_config_check
        check (
            jsonb_typeof(retriever_config) = 'object'
            and retriever_config ? 'kind'
            and retriever_config->>'kind' = retriever_kind
        ),
    constraint request_captures_embedding_model_nonempty_check
        check (length(btrim(embedding_model)) > 0),
    constraint request_captures_prompt_template_id_nonempty_check
        check (length(btrim(prompt_template_id)) > 0),
    constraint request_captures_prompt_template_version_nonempty_check
        check (length(btrim(prompt_template_version)) > 0),
    constraint request_captures_generation_model_nonempty_check
        check (length(btrim(generation_model)) > 0),
    constraint request_captures_generation_config_check
        check (request_capture_generation_config_is_valid(generation_config)),
    constraint request_captures_reranker_kind_check
        check (reranker_kind in ('PassThrough', 'Heuristic', 'CrossEncoder')),
    constraint request_captures_reranker_config_check
        check (
            (
                reranker_kind = 'PassThrough'
                and reranker_config is null
            )
            or (
                reranker_kind = 'Heuristic'
                and reranker_config is not null
                and request_capture_reranker_config_is_valid(reranker_config)
            )
            or (
                reranker_kind = 'CrossEncoder'
                and reranker_config is not null
                and request_capture_reranker_config_is_valid(reranker_config)
            )
        ),
    constraint request_captures_final_answer_nonempty_check
        check (length(btrim(final_answer)) > 0),
    constraint request_captures_input_token_count_check
        check (input_token_count >= 1),
    constraint request_captures_top_k_requested_check
        check (top_k_requested >= 1),
    constraint request_captures_prompt_tokens_check
        check (prompt_tokens >= 0),
    constraint request_captures_completion_tokens_check
        check (completion_tokens >= 0),
    constraint request_captures_total_tokens_nonnegative_check
        check (total_tokens >= 0),
    constraint request_captures_total_tokens_sum_check
        check (total_tokens = prompt_tokens + completion_tokens),
    constraint request_captures_retrieval_results_array_check
        check (jsonb_typeof(retrieval_results) = 'array'),
    constraint request_captures_retrieval_results_nonempty_check
        check (jsonb_array_length(retrieval_results) >= 1),
    constraint request_captures_retrieval_results_exact_keys_check
        check (request_capture_retrieval_results_items_are_valid(retrieval_results)),
    constraint request_captures_retrieval_results_selected_check
        check (
            jsonb_path_exists(
                retrieval_results,
                '$[*] ? (@.selected_for_generation == true)'
            )
        )
);

create index if not exists idx_request_captures_received_at
    on request_captures (received_at);

create index if not exists idx_request_captures_trace_id
    on request_captures (trace_id);

alter table request_captures
    add column if not exists runtime_run_id text null;

alter table request_captures
    drop constraint if exists request_captures_runtime_run_id_nonempty_check;

alter table request_captures
    add constraint request_captures_runtime_run_id_nonempty_check
        check (runtime_run_id is null or length(btrim(runtime_run_id)) > 0);

create index if not exists idx_request_captures_runtime_run_id
    on request_captures (runtime_run_id);

alter table request_captures
    add column if not exists retriever_kind text;

alter table request_captures
    add column if not exists retriever_config jsonb;

update request_captures
set retriever_kind = 'Dense'
where retriever_kind is null;

update request_captures
set retriever_config = jsonb_build_object(
    'kind', 'Dense',
    'embedding_model_name', embedding_model,
    'embedding_dimension', 1024,
    'qdrant_collection_name', 'chunks_dense_qwen3',
    'qdrant_vector_name', 'default',
    'corpus_version', corpus_version
)
where retriever_config is null;

alter table request_captures
    alter column retriever_kind set not null;

alter table request_captures
    alter column retriever_config set not null;

alter table request_captures
    drop constraint if exists request_captures_retriever_kind_check;

alter table request_captures
    add constraint request_captures_retriever_kind_check
        check (retriever_kind in ('Dense', 'Hybrid'));

alter table request_captures
    drop constraint if exists request_captures_retriever_config_check;

alter table request_captures
    add constraint request_captures_retriever_config_check
        check (
            jsonb_typeof(retriever_config) = 'object'
            and retriever_config ? 'kind'
            and retriever_config->>'kind' = retriever_kind
        );

create index if not exists idx_request_captures_retriever_kind
    on request_captures (retriever_kind);

alter table request_captures
    drop constraint if exists request_captures_reranker_kind_check;

alter table request_captures
    add constraint request_captures_reranker_kind_check
        check (reranker_kind in ('PassThrough', 'Heuristic', 'CrossEncoder'));

alter table request_captures
    drop constraint if exists request_captures_reranker_config_check;

alter table request_captures
    add constraint request_captures_reranker_config_check
        check (
            (
                reranker_kind = 'PassThrough'
                and reranker_config is null
            )
            or (
                reranker_kind = 'Heuristic'
                and reranker_config is not null
                and request_capture_reranker_config_is_valid(reranker_config)
            )
            or (
                reranker_kind = 'CrossEncoder'
                and reranker_config is not null
                and request_capture_reranker_config_is_valid(reranker_config)
            )
        );

alter table request_captures
    add column if not exists retrieval_stage_metrics jsonb null;

alter table request_captures
    add column if not exists reranking_stage_metrics jsonb null;

alter table request_captures
    add column if not exists generation_config jsonb null;

update request_captures
set generation_config = jsonb_build_object(
    'model',              generation_model,
    'model_endpoint',     'http://ollama:11434',
    'temperature',        0.0,
    'max_context_chunks', 4,
    'input_cost_per_million_tokens', 0.0,
    'output_cost_per_million_tokens', 0.0
)
where generation_config is null;

alter table request_captures
    alter column generation_config set not null;

alter table request_captures
    drop constraint if exists request_captures_generation_config_check;

alter table request_captures
    add constraint request_captures_generation_config_check
        check (request_capture_generation_config_is_valid(generation_config));

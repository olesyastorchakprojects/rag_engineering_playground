use serde_json::{Value, json};
use sqlx::postgres::PgPoolOptions;
use sqlx::types::Json;

use crate::config::{
    CrossEncoderTransportSettings, DenseRetrievalIngest, GenerationSettings, HybridRetrievalIngest,
    OllamaTransportSettings, OpenAiTransportSettings, RerankerSettings, RerankingSettings,
    RetrievalIngest, RetrievalSettings, RetrievalStrategy, Settings, TransportSettings,
};
use crate::errors::RagRuntimeError;

pub struct RuntimeRunConfigStore;

impl RuntimeRunConfigStore {
    pub async fn store(runtime_run_id: &str, settings: &Settings) -> Result<(), RagRuntimeError> {
        let pool = PgPoolOptions::new()
            .max_connections(1)
            .connect(&settings.request_capture.postgres_url)
            .await
            .map_err(|error| {
                RagRuntimeError::startup(format!("runtime_run_config connection failed: {error}"))
            })?;

        let config_json = build_runtime_config_snapshot(settings);

        sqlx::query(
            r#"
            insert into runtime_run_configs (
                runtime_run_id,
                config_version,
                runtime_config_json
            ) values ($1, $2, $3)
            on conflict (runtime_run_id) do update
            set config_version = excluded.config_version,
                runtime_config_json = excluded.runtime_config_json
            "#,
        )
        .bind(runtime_run_id)
        .bind(&settings.pipeline.config_version)
        .bind(Json(config_json))
        .execute(&pool)
        .await
        .map_err(|error| {
            RagRuntimeError::startup(format!("runtime_run_config insert failed: {error}"))
        })?;

        Ok(())
    }
}

fn build_runtime_config_snapshot(settings: &Settings) -> Value {
    json!({
        "pipeline": {
            "config_version": settings.pipeline.config_version,
        },
        "input_validation": {
            "max_query_tokens": settings.input_validation.max_query_tokens,
            "tokenizer_source": settings.input_validation.tokenizer_source,
            "reject_empty_query": settings.input_validation.reject_empty_query,
            "trim_whitespace": settings.input_validation.trim_whitespace,
            "collapse_internal_whitespace": settings.input_validation.collapse_internal_whitespace,
        },
        "retrieval": snapshot_retrieval_settings(&settings.retrieval),
        "generation": snapshot_generation_settings(&settings.generation),
        "reranking": snapshot_reranking_settings(&settings.reranking),
        "observability": {
            "tracing_enabled": settings.observability.tracing_enabled,
            "metrics_enabled": settings.observability.metrics_enabled,
            "tracing_endpoint": settings.observability.tracing_endpoint,
            "metrics_endpoint": settings.observability.metrics_endpoint,
            "trace_batch_scheduled_delay_ms": settings.observability.trace_batch_scheduled_delay_ms,
            "metrics_export_interval_ms": settings.observability.metrics_export_interval_ms,
        },
    })
}

fn snapshot_retrieval_settings(settings: &RetrievalSettings) -> Value {
    json!({
        "kind": match settings.kind {
            crate::config::RetrievalKind::Dense => "dense",
            crate::config::RetrievalKind::Hybrid => "hybrid",
        },
        "ollama_url": settings.ollama_url,
        "qdrant_url": settings.qdrant_url,
        "retriever_version": settings.retriever_version,
        "top_k": settings.top_k,
        "score_threshold": settings.score_threshold,
        "embedding_retry": {
            "max_attempts": settings.embedding_retry.max_attempts,
            "backoff": match settings.embedding_retry.backoff {
                crate::config::RetryBackoff::Exponential => "exponential",
            },
        },
        "qdrant_retry": {
            "max_attempts": settings.qdrant_retry.max_attempts,
            "backoff": match settings.qdrant_retry.backoff {
                crate::config::RetryBackoff::Exponential => "exponential",
            },
        },
        "ingest": snapshot_retrieval_ingest(&settings.ingest),
    })
}

fn snapshot_retrieval_ingest(ingest: &RetrievalIngest) -> Value {
    match ingest {
        RetrievalIngest::Dense(settings) => snapshot_dense_retrieval_ingest(settings),
        RetrievalIngest::Hybrid(settings) => snapshot_hybrid_retrieval_ingest(settings),
    }
}

fn snapshot_dense_retrieval_ingest(settings: &DenseRetrievalIngest) -> Value {
    json!({
        "kind": "dense",
        "embedding_model_name": settings.embedding_model_name,
        "embedding_dimension": settings.embedding_dimension,
        "qdrant_collection_name": settings.qdrant_collection_name,
        "qdrant_vector_name": settings.qdrant_vector_name,
        "corpus_version": settings.corpus_version,
    })
}

fn snapshot_hybrid_retrieval_ingest(settings: &HybridRetrievalIngest) -> Value {
    json!({
        "kind": "hybrid",
        "embedding_model_name": settings.embedding_model_name,
        "embedding_dimension": settings.embedding_dimension,
        "qdrant_collection_name": settings.qdrant_collection_name,
        "dense_vector_name": settings.dense_vector_name,
        "sparse_vector_name": settings.sparse_vector_name,
        "corpus_version": settings.corpus_version,
        "tokenizer_library": settings.tokenizer_library,
        "tokenizer_source": settings.tokenizer_source,
        "tokenizer_revision": settings.tokenizer_revision,
        "preprocessing_kind": settings.preprocessing_kind,
        "lowercase": settings.lowercase,
        "min_token_length": settings.min_token_length,
        "vocabulary_path": settings.vocabulary_path,
        "strategy": snapshot_retrieval_strategy(&settings.strategy),
    })
}

fn snapshot_retrieval_strategy(strategy: &RetrievalStrategy) -> Value {
    match strategy {
        RetrievalStrategy::BagOfWords(settings) => json!({
            "kind": "bag_of_words",
            "version": settings.version,
            "query_weighting": settings.query_weighting,
        }),
        RetrievalStrategy::Bm25Like(settings) => json!({
            "kind": "bm25_like",
            "version": settings.version,
            "query_weighting": settings.query_weighting,
            "k1": settings.k1,
            "b": settings.b,
            "idf_smoothing": settings.idf_smoothing,
            "term_stats_path": settings.term_stats_path,
        }),
    }
}

fn snapshot_generation_settings(settings: &GenerationSettings) -> Value {
    json!({
        "tokenizer_source": settings.tokenizer_source,
        "temperature": settings.temperature,
        "max_context_chunks": settings.max_context_chunks,
        "max_prompt_tokens": settings.max_prompt_tokens,
        "retry": {
            "max_attempts": settings.retry.max_attempts,
            "backoff": match settings.retry.backoff {
                crate::config::RetryBackoff::Exponential => "exponential",
            },
        },
        "transport": snapshot_transport_settings(&settings.transport),
    })
}

fn snapshot_transport_settings(settings: &TransportSettings) -> Value {
    match settings {
        TransportSettings::Ollama(transport) => snapshot_ollama_transport_settings(transport),
        TransportSettings::OpenAi(transport) => snapshot_openai_transport_settings(transport),
    }
}

fn snapshot_ollama_transport_settings(settings: &OllamaTransportSettings) -> Value {
    json!({
        "kind": "ollama",
        "url": settings.url,
        "model_name": settings.model_name,
        "timeout_sec": settings.timeout_sec,
        "input_cost_per_million_tokens": settings.input_cost_per_million_tokens,
        "output_cost_per_million_tokens": settings.output_cost_per_million_tokens,
    })
}

fn snapshot_openai_transport_settings(settings: &OpenAiTransportSettings) -> Value {
    json!({
        "kind": "openai",
        "url": settings.url,
        "model_name": settings.model_name,
        "timeout_sec": settings.timeout_sec,
        "input_cost_per_million_tokens": settings.input_cost_per_million_tokens,
        "output_cost_per_million_tokens": settings.output_cost_per_million_tokens,
    })
}

fn snapshot_reranking_settings(settings: &RerankingSettings) -> Value {
    let (kind, heuristic, cross_encoder) = match &settings.reranker {
        RerankerSettings::PassThrough => ("pass_through", None, None),
        RerankerSettings::Heuristic(heuristic) => (
            "heuristic",
            Some(json!({
                "retrieval_score": heuristic.weights.retrieval_score,
                "query_term_coverage": heuristic.weights.query_term_coverage,
                "phrase_match_bonus": heuristic.weights.phrase_match_bonus,
                "title_section_match_bonus": heuristic.weights.title_section_match_bonus,
            })),
            None,
        ),
        RerankerSettings::CrossEncoder(cross_encoder) => (
            "cross_encoder",
            None,
            Some(snapshot_cross_encoder_settings(&cross_encoder.transport)),
        ),
    };
    json!({
        "kind": kind,
        "weights": heuristic,
        "candidate_k": settings.candidate_k,
        "final_k": settings.final_k,
        "cross_encoder": cross_encoder,
    })
}

fn snapshot_cross_encoder_settings(settings: &CrossEncoderTransportSettings) -> Value {
    match settings {
        CrossEncoderTransportSettings::MixedbreadAi(settings) => json!({
            "transport_kind": "mixedbread-ai",
            "mixedbread-ai": {
                "url": settings.url,
                "model_name": settings.model_name,
                "batch_size": settings.batch_size,
                "timeout_sec": settings.timeout_sec,
                "cost_per_million_tokens": settings.cost_per_million_tokens,
                "tokenizer_source": settings.tokenizer_source,
                "max_attempts": settings.max_attempts,
                "backoff": match settings.backoff {
                    crate::config::RetryBackoff::Exponential => "exponential",
                },
            }
        }),
        CrossEncoderTransportSettings::VoyageAi(settings) => json!({
            "transport_kind": "voyageai",
            "voyageai": {
                "url": settings.url,
                "model_name": settings.model_name,
                "batch_size": settings.batch_size,
                "timeout_sec": settings.timeout_sec,
                "cost_per_million_tokens": settings.cost_per_million_tokens,
                "max_attempts": settings.max_attempts,
                "backoff": match settings.backoff {
                    crate::config::RetryBackoff::Exponential => "exponential",
                },
            }
        }),
    }
}

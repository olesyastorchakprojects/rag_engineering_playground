use jsonschema::draft202012;
use serde::Serialize;
use serde_json::Value;
use sqlx::postgres::PgPoolOptions;
use sqlx::types::Json;

use crate::config::{RequestCaptureSettings, default_request_capture_schema_path};
use crate::errors::{RagRuntimeError, RequestCaptureStoreError};
use crate::models::{RequestCapture, RerankerKind, RetrievalQualityMetrics, RetrieverKind};

pub struct RequestCaptureStore;

#[derive(Debug, Serialize)]
struct RequestCaptureStorageRowPayload {
    runtime_run_id: String,
    request_id: String,
    trace_id: String,
    received_at: chrono::DateTime<chrono::Utc>,
    raw_query: String,
    normalized_query: String,
    input_token_count: i32,
    pipeline_config_version: String,
    corpus_version: String,
    retriever_version: String,
    retriever_kind: String,
    retriever_config: Value,
    embedding_model: String,
    prompt_template_id: String,
    prompt_template_version: String,
    generation_model: String,
    generation_config: Value,
    reranker_kind: String,
    reranker_config: Option<Value>,
    top_k_requested: i32,
    retrieval_results: Value,
    final_answer: String,
    prompt_tokens: i32,
    completion_tokens: i32,
    total_tokens: i32,
    retrieval_stage_metrics: Option<Value>,
    reranking_stage_metrics: Option<Value>,
}

struct RequestCaptureStorageRowMapper;

impl RequestCaptureStore {
    pub async fn store(
        capture: RequestCapture,
        settings: &RequestCaptureSettings,
    ) -> Result<(), RagRuntimeError> {
        validate_capture(&capture).await?;
        let payload = RequestCaptureStorageRowMapper::map(capture)?;

        let pool = PgPoolOptions::new()
            .max_connections(1)
            .connect(&settings.postgres_url)
            .await
            .map_err(|error| RequestCaptureStoreError::Connection {
                message: error.to_string(),
            })?;

        let query = sqlx::query(
            r#"
            insert into request_captures (
                runtime_run_id,
                request_id,
                trace_id,
                received_at,
                raw_query,
                normalized_query,
                input_token_count,
                pipeline_config_version,
                corpus_version,
                retriever_version,
                retriever_kind,
                retriever_config,
                embedding_model,
                prompt_template_id,
                prompt_template_version,
                generation_model,
                generation_config,
                reranker_kind,
                reranker_config,
                top_k_requested,
                retrieval_results,
                final_answer,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                retrieval_stage_metrics,
                reranking_stage_metrics
            ) values (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
                $21, $22, $23, $24, $25, $26, $27
            )
            "#,
        )
        .bind(&payload.runtime_run_id)
        .bind(&payload.request_id)
        .bind(&payload.trace_id)
        .bind(payload.received_at)
        .bind(&payload.raw_query)
        .bind(&payload.normalized_query)
        .bind(payload.input_token_count)
        .bind(&payload.pipeline_config_version)
        .bind(&payload.corpus_version)
        .bind(&payload.retriever_version)
        .bind(&payload.retriever_kind)
        .bind(Json(payload.retriever_config.clone()))
        .bind(&payload.embedding_model)
        .bind(&payload.prompt_template_id)
        .bind(&payload.prompt_template_version)
        .bind(&payload.generation_model)
        .bind(Json(payload.generation_config))
        .bind(&payload.reranker_kind)
        .bind(payload.reranker_config.clone().map(Json))
        .bind(payload.top_k_requested)
        .bind(Json(payload.retrieval_results))
        .bind(&payload.final_answer)
        .bind(payload.prompt_tokens)
        .bind(payload.completion_tokens)
        .bind(payload.total_tokens)
        .bind(payload.retrieval_stage_metrics.map(Json))
        .bind(payload.reranking_stage_metrics.map(Json));

        query
            .execute(&pool)
            .await
            .map_err(|error| {
                if let Some(database_error) = error.as_database_error()
                    && database_error.code().as_deref() == Some("23505")
                {
                    return RequestCaptureStoreError::DuplicateRequestId {
                        request_id: payload.request_id.clone(),
                    }
                    .into();
                }
                RequestCaptureStoreError::InsertExecution {
                    message: error.to_string(),
                }
                .into()
            })
            .map(|_| ())
    }
}

impl RequestCaptureStorageRowMapper {
    fn map(
        capture: RequestCapture,
    ) -> Result<RequestCaptureStorageRowPayload, RequestCaptureStoreError> {
        let retrieval_results =
            serde_json::to_value(&capture.retrieval_results).map_err(|error| {
                RequestCaptureStoreError::Serialization {
                    message: error.to_string(),
                }
            })?;
        let retrieval_stage_metrics = serialize_optional_metrics(capture.retrieval_stage_metrics)?;
        let reranking_stage_metrics = serialize_optional_metrics(capture.reranking_stage_metrics)?;

        Ok(RequestCaptureStorageRowPayload {
            runtime_run_id: capture.runtime_run_id,
            request_id: capture.request_id,
            trace_id: capture.trace_id,
            received_at: capture.received_at,
            raw_query: capture.raw_query,
            normalized_query: capture.normalized_query,
            input_token_count: usize_to_i32("input_token_count", capture.input_token_count)?,
            pipeline_config_version: capture.pipeline_config_version,
            corpus_version: capture.corpus_version,
            retriever_version: capture.retriever_version,
            retriever_kind: retriever_kind_to_storage_text(&capture.retriever_kind).to_string(),
            retriever_config: serde_json::to_value(&capture.retriever_config).map_err(|error| {
                RequestCaptureStoreError::Serialization {
                    message: error.to_string(),
                }
            })?,
            embedding_model: capture.embedding_model,
            prompt_template_id: capture.prompt_template_id,
            prompt_template_version: capture.prompt_template_version,
            generation_model: capture.generation_model,
            generation_config: serde_json::to_value(&capture.generation_config).map_err(
                |error| RequestCaptureStoreError::Serialization {
                    message: error.to_string(),
                },
            )?,
            reranker_kind: reranker_kind_to_storage_text(&capture.reranker_kind).to_string(),
            reranker_config: match &capture.reranker_config {
                Some(config) => Some(serde_json::to_value(config).map_err(|error| {
                    RequestCaptureStoreError::Serialization {
                        message: error.to_string(),
                    }
                })?),
                None => None,
            },
            top_k_requested: usize_to_i32("top_k_requested", capture.top_k_requested)?,
            retrieval_results,
            final_answer: capture.final_answer,
            prompt_tokens: usize_to_i32("prompt_tokens", capture.prompt_tokens)?,
            completion_tokens: usize_to_i32("completion_tokens", capture.completion_tokens)?,
            total_tokens: usize_to_i32("total_tokens", capture.total_tokens)?,
            retrieval_stage_metrics,
            reranking_stage_metrics,
        })
    }
}

fn reranker_kind_to_storage_text(kind: &RerankerKind) -> &'static str {
    match kind {
        RerankerKind::PassThrough => "PassThrough",
        RerankerKind::Heuristic => "Heuristic",
        RerankerKind::CrossEncoder => "CrossEncoder",
    }
}

fn retriever_kind_to_storage_text(kind: &RetrieverKind) -> &'static str {
    match kind {
        RetrieverKind::Dense => "Dense",
        RetrieverKind::Hybrid => "Hybrid",
    }
}

async fn validate_capture(capture: &RequestCapture) -> Result<(), RequestCaptureStoreError> {
    if capture.total_tokens != capture.prompt_tokens + capture.completion_tokens {
        return Err(RequestCaptureStoreError::Validation {
            message: "total_tokens must equal prompt_tokens + completion_tokens".to_string(),
        });
    }

    let schema_path = default_request_capture_schema_path();
    let schema_text = tokio::fs::read_to_string(&schema_path)
        .await
        .map_err(|error| RequestCaptureStoreError::Internal {
            message: format!(
                "failed to read request-capture schema {}: {error}",
                schema_path.display()
            ),
        })?;
    let schema_json: Value =
        serde_json::from_str(&schema_text).map_err(|error| RequestCaptureStoreError::Internal {
            message: format!(
                "failed to parse request-capture schema {}: {error}",
                schema_path.display()
            ),
        })?;
    let validator =
        draft202012::new(&schema_json).map_err(|error| RequestCaptureStoreError::Internal {
            message: format!(
                "failed to compile request-capture schema {}: {error}",
                schema_path.display()
            ),
        })?;

    let capture_json =
        serde_json::to_value(capture).map_err(|error| RequestCaptureStoreError::Serialization {
            message: error.to_string(),
        })?;
    validator
        .validate(&capture_json)
        .map_err(|error| RequestCaptureStoreError::Validation {
            message: error.to_string(),
        })
}

fn serialize_optional_metrics(
    metrics: Option<RetrievalQualityMetrics>,
) -> Result<Option<Value>, RequestCaptureStoreError> {
    match metrics {
        Some(m) => serde_json::to_value(&m).map(Some).map_err(|error| {
            RequestCaptureStoreError::Serialization {
                message: error.to_string(),
            }
        }),
        None => Ok(None),
    }
}

fn usize_to_i32(field_name: &str, value: usize) -> Result<i32, RequestCaptureStoreError> {
    i32::try_from(value).map_err(|_| RequestCaptureStoreError::Serialization {
        message: format!("{field_name} value {value} exceeds i32 range"),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;
    use serde_json::json;

    use crate::models::{
        GenerationConfig, HeuristicWeights, RequestCapture, RerankerConfig, RerankerKind,
        RetrievalQualityMetrics, RetrievalResultItem, RetrieverConfig, RetrieverKind,
        RetrieverStrategyConfig,
    };

    fn sample_capture() -> RequestCapture {
        RequestCapture {
            runtime_run_id: "runtime-run-123".to_string(),
            request_id: "req-123".to_string(),
            trace_id: "trace-123".to_string(),
            received_at: Utc::now(),
            raw_query: "raw query".to_string(),
            normalized_query: "normalized query".to_string(),
            input_token_count: 3,
            pipeline_config_version: "pipeline-v1".to_string(),
            corpus_version: "corpus-v1".to_string(),
            retriever_version: "retriever-v1".to_string(),
            retriever_kind: RetrieverKind::Dense,
            retriever_config: RetrieverConfig::Dense {
                embedding_model_name: "embedding-model".to_string(),
                embedding_endpoint: "http://127.0.0.1:11434".to_string(),
                embedding_dimension: 1024,
                qdrant_collection_name: "chunks_dense_qwen3".to_string(),
                qdrant_vector_name: "default".to_string(),
                score_threshold: 0.2,
                corpus_version: "corpus-v1".to_string(),
                chunking_strategy: "structural".to_string(),
            },
            embedding_model: "embedding-model".to_string(),
            prompt_template_id: "prompt-id".to_string(),
            prompt_template_version: "prompt-v1".to_string(),
            generation_model: "generation-model".to_string(),
            generation_config: GenerationConfig {
                model: "generation-model".to_string(),
                model_endpoint: "http://127.0.0.1:11434".to_string(),
                temperature: 0.0,
                max_context_chunks: 5,
                input_cost_per_million_tokens: 0.0,
                output_cost_per_million_tokens: 0.0,
            },
            reranker_kind: RerankerKind::PassThrough,
            reranker_config: None,
            top_k_requested: 2,
            retrieval_results: vec![
                RetrievalResultItem {
                    chunk_id: "chunk-1".to_string(),
                    document_id: "doc-1".to_string(),
                    locator: "page:1".to_string(),
                    retrieval_score: 0.95,
                    rerank_score: 0.95,
                    selected_for_generation: true,
                },
                RetrievalResultItem {
                    chunk_id: "chunk-2".to_string(),
                    document_id: "doc-2".to_string(),
                    locator: "page:2".to_string(),
                    retrieval_score: 0.75,
                    rerank_score: 0.75,
                    selected_for_generation: false,
                },
            ],
            final_answer: "final answer".to_string(),
            prompt_tokens: 10,
            completion_tokens: 4,
            total_tokens: 14,
            retrieval_stage_metrics: None,
            reranking_stage_metrics: None,
        }
    }

    fn sample_hybrid_capture() -> RequestCapture {
        let mut capture = sample_capture();
        capture.retriever_kind = RetrieverKind::Hybrid;
        capture.retriever_config = RetrieverConfig::Hybrid {
            embedding_model_name: "qwen3-embedding:0.6b".to_string(),
            embedding_endpoint: "http://127.0.0.1:11434".to_string(),
            embedding_dimension: 1024,
            chunking_strategy: "structural".to_string(),
            qdrant_collection_name: "chunks_hybrid_structural_qwen3".to_string(),
            dense_vector_name: "dense".to_string(),
            sparse_vector_name: "sparse".to_string(),
            score_threshold: 0.2,
            corpus_version: "corpus-v1".to_string(),
            tokenizer_library: "tokenizers".to_string(),
            tokenizer_source: "Qwen/Qwen3-Embedding-0.6B".to_string(),
            tokenizer_revision: Some("main".to_string()),
            preprocessing_kind: "basic_word_v1".to_string(),
            lowercase: true,
            min_token_length: 2,
            vocabulary_path: "Execution/ingest/hybrid/artifacts/vocabularies".to_string(),
            strategy: RetrieverStrategyConfig::BagOfWords {
                version: "v1".to_string(),
                query_weighting: "binary_presence".to_string(),
            },
        };
        capture
    }

    #[tokio::test]
    async fn valid_request_capture_passes_schema_validation_before_write() {
        let result = validate_capture(&sample_capture()).await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn valid_hybrid_request_capture_passes_schema_validation_before_write() {
        let result = validate_capture(&sample_hybrid_capture()).await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn empty_required_string_field_fails_with_validation_variant_before_write() {
        let mut capture = sample_capture();
        capture.raw_query.clear();

        let error = validate_capture(&capture).await.unwrap_err();
        match error {
            RequestCaptureStoreError::Validation { message } => {
                assert!(!message.is_empty());
            }
            other => panic!("expected validation error, got {other:?}"),
        }
    }

    #[tokio::test]
    async fn mismatched_total_tokens_fail_with_validation_variant_before_write() {
        let mut capture = sample_capture();
        capture.total_tokens = 999;

        let error = validate_capture(&capture).await.unwrap_err();
        match error {
            RequestCaptureStoreError::Validation { message } => {
                assert!(message.contains("total_tokens must equal"));
            }
            other => panic!("expected validation error, got {other:?}"),
        }
    }

    #[tokio::test]
    async fn empty_retrieval_results_fail_with_validation_variant_before_write() {
        let mut capture = sample_capture();
        capture.retrieval_results.clear();

        let error = validate_capture(&capture).await.unwrap_err();
        match error {
            RequestCaptureStoreError::Validation { message } => {
                assert!(!message.is_empty());
            }
            other => panic!("expected validation error, got {other:?}"),
        }
    }

    #[tokio::test]
    async fn missing_selected_for_generation_item_fails_with_validation_variant_before_write() {
        let mut capture = sample_capture();
        for item in &mut capture.retrieval_results {
            item.selected_for_generation = false;
        }

        let error = validate_capture(&capture).await.unwrap_err();
        match error {
            RequestCaptureStoreError::Validation { message } => {
                assert!(!message.is_empty());
            }
            other => panic!("expected validation error, got {other:?}"),
        }
    }

    #[test]
    fn storage_row_mapper_constructs_exact_storage_facing_payload_shape() {
        let payload = RequestCaptureStorageRowMapper::map(sample_capture()).unwrap();
        let payload_json = serde_json::to_value(&payload).unwrap();
        let payload_object = payload_json.as_object().unwrap();

        assert_eq!(payload_object.len(), 27);
        assert_eq!(payload_object["request_id"], "req-123");
        assert_eq!(payload_object["trace_id"], "trace-123");
        assert_eq!(payload_object["raw_query"], "raw query");
        assert_eq!(payload_object["normalized_query"], "normalized query");
        assert_eq!(payload_object["input_token_count"], 3);
        assert_eq!(payload_object["pipeline_config_version"], "pipeline-v1");
        assert_eq!(payload_object["corpus_version"], "corpus-v1");
        assert_eq!(payload_object["retriever_version"], "retriever-v1");
        assert_eq!(payload_object["retriever_kind"], "Dense");
        assert_eq!(payload_object["retriever_config"]["kind"], "Dense");
        assert_eq!(payload_object["embedding_model"], "embedding-model");
        assert_eq!(payload_object["prompt_template_id"], "prompt-id");
        assert_eq!(payload_object["prompt_template_version"], "prompt-v1");
        assert_eq!(payload_object["generation_model"], "generation-model");
        assert_eq!(
            payload_object["generation_config"]["model"],
            "generation-model"
        );
        assert_eq!(
            payload_object["generation_config"]["model_endpoint"],
            "http://127.0.0.1:11434"
        );
        assert_eq!(payload_object["generation_config"]["temperature"], 0.0);
        assert_eq!(payload_object["generation_config"]["max_context_chunks"], 5);
        assert_eq!(payload_object["reranker_kind"], "PassThrough");
        assert!(payload_object["reranker_config"].is_null());
        assert_eq!(payload_object["top_k_requested"], 2);
        assert_eq!(payload_object["final_answer"], "final answer");
        assert_eq!(payload_object["prompt_tokens"], 10);
        assert_eq!(payload_object["completion_tokens"], 4);
        assert_eq!(payload_object["total_tokens"], 14);
        assert!(payload_object["received_at"].is_string());
        assert!(payload_object["retrieval_stage_metrics"].is_null());
        assert!(payload_object["reranking_stage_metrics"].is_null());
    }

    #[test]
    fn storage_row_mapper_preserves_hybrid_retriever_snapshot_shape() {
        let payload = RequestCaptureStorageRowMapper::map(sample_hybrid_capture()).unwrap();
        let payload_json = serde_json::to_value(&payload).unwrap();
        let payload_object = payload_json.as_object().unwrap();

        assert_eq!(payload_object["retriever_kind"], "Hybrid");
        let retriever_config = payload_object["retriever_config"].as_object().unwrap();
        assert_eq!(retriever_config["kind"], "Hybrid");
        assert_eq!(
            retriever_config["qdrant_collection_name"],
            "chunks_hybrid_structural_qwen3"
        );
        assert_eq!(retriever_config["dense_vector_name"], "dense");
        assert_eq!(retriever_config["sparse_vector_name"], "sparse");
        assert_eq!(
            retriever_config["vocabulary_path"],
            "Execution/ingest/hybrid/artifacts/vocabularies"
        );
        assert_eq!(retriever_config["strategy"]["kind"], "bag_of_words");
    }

    #[test]
    fn storage_row_mapper_serializes_heuristic_reranker_snapshot() {
        let mut capture = sample_capture();
        capture.reranker_kind = RerankerKind::Heuristic;
        capture.reranker_config = Some(RerankerConfig::Heuristic {
            final_k: 5,
            weights: HeuristicWeights {
                retrieval_score: 0.7,
                query_term_coverage: 0.15,
                phrase_match_bonus: 0.1,
                title_section_match_bonus: 0.05,
            },
        });

        let payload = RequestCaptureStorageRowMapper::map(capture).unwrap();
        let payload_json = serde_json::to_value(&payload).unwrap();
        let payload_object = payload_json.as_object().unwrap();

        assert_eq!(payload_object["reranker_kind"], "Heuristic");
        let reranker_config = payload_object["reranker_config"].as_object().unwrap();
        assert_eq!(reranker_config["kind"], "Heuristic");
        let weights = reranker_config["weights"].as_object().unwrap();
        assert!((weights["retrieval_score"].as_f64().unwrap() - 0.7).abs() < 1e-6);
        assert!((weights["query_term_coverage"].as_f64().unwrap() - 0.15).abs() < 1e-6);
        assert!((weights["phrase_match_bonus"].as_f64().unwrap() - 0.1).abs() < 1e-6);
        assert!((weights["title_section_match_bonus"].as_f64().unwrap() - 0.05).abs() < 1e-6);
    }

    #[test]
    fn storage_row_mapper_serializes_cross_encoder_reranker_snapshot() {
        let mut capture = sample_capture();
        capture.reranker_kind = RerankerKind::CrossEncoder;
        capture.reranker_config = Some(RerankerConfig::CrossEncoder {
            final_k: 5,
            cross_encoder: crate::models::CrossEncoderConfig {
                model_name: "mixedbread-ai/mxbai-rerank-base-v2".to_string(),
                url: "http://127.0.0.1:8081".to_string(),
                total_tokens: Some(321),
                cost_per_million_tokens: 0.0,
            },
        });

        let payload = RequestCaptureStorageRowMapper::map(capture).unwrap();
        let payload_json = serde_json::to_value(&payload).unwrap();
        let payload_object = payload_json.as_object().unwrap();

        assert_eq!(payload_object["reranker_kind"], "CrossEncoder");
        let reranker_config = payload_object["reranker_config"].as_object().unwrap();
        assert_eq!(reranker_config["kind"], "CrossEncoder");
        assert_eq!(
            reranker_config["cross_encoder"]["model_name"],
            "mixedbread-ai/mxbai-rerank-base-v2"
        );
        assert_eq!(
            reranker_config["cross_encoder"]["url"],
            "http://127.0.0.1:8081"
        );
        assert_eq!(reranker_config["cross_encoder"]["total_tokens"], 321);
    }

    #[test]
    fn storage_row_mapper_serializes_retrieval_results_in_exact_json_array_shape() {
        let payload = RequestCaptureStorageRowMapper::map(sample_capture()).unwrap();
        let retrieval_results = payload.retrieval_results.as_array().unwrap();

        assert_eq!(retrieval_results.len(), 2);
        assert_eq!(
            retrieval_results[0],
            json!({
                "chunk_id": "chunk-1",
                "document_id": "doc-1",
                "locator": "page:1",
                "retrieval_score": retrieval_results[0]["retrieval_score"],
                "rerank_score": retrieval_results[0]["rerank_score"],
                "selected_for_generation": true
            })
        );
        assert_eq!(
            retrieval_results[1],
            json!({
                "chunk_id": "chunk-2",
                "document_id": "doc-2",
                "locator": "page:2",
                "retrieval_score": retrieval_results[1]["retrieval_score"],
                "rerank_score": retrieval_results[1]["rerank_score"],
                "selected_for_generation": false
            })
        );
    }

    #[test]
    fn storage_row_mapper_preserves_retrieval_item_order() {
        let payload = RequestCaptureStorageRowMapper::map(sample_capture()).unwrap();
        let retrieval_results = payload.retrieval_results.as_array().unwrap();

        assert_eq!(retrieval_results[0]["chunk_id"], "chunk-1");
        assert_eq!(retrieval_results[1]["chunk_id"], "chunk-2");
    }

    #[test]
    fn storage_row_mapper_excludes_storage_only_fields() {
        let payload = RequestCaptureStorageRowMapper::map(sample_capture()).unwrap();
        let payload_json = serde_json::to_value(&payload).unwrap();
        let payload_object = payload_json.as_object().unwrap();

        assert!(!payload_object.contains_key("stored_at"));
    }

    #[test]
    fn storage_row_mapper_serializes_present_retrieval_quality_metrics() {
        let metrics = RetrievalQualityMetrics {
            evaluated_k: 12,
            recall_soft: 0.75,
            recall_strict: 0.5,
            rr_soft: 0.8,
            rr_strict: 0.6,
            ndcg: 0.7,
            first_relevant_rank_soft: Some(1),
            first_relevant_rank_strict: Some(2),
            num_relevant_soft: 3,
            num_relevant_strict: 2,
        };

        let mut capture = sample_capture();
        capture.retrieval_stage_metrics = Some(metrics.clone());
        capture.reranking_stage_metrics = Some(metrics);

        let payload = RequestCaptureStorageRowMapper::map(capture).unwrap();
        let payload_json = serde_json::to_value(&payload).unwrap();
        let payload_object = payload_json.as_object().unwrap();

        let retrieval_m = payload_object["retrieval_stage_metrics"]
            .as_object()
            .unwrap();
        assert_eq!(retrieval_m["evaluated_k"], 12);
        assert!((retrieval_m["recall_soft"].as_f64().unwrap() - 0.75).abs() < 1e-5);
        assert!(retrieval_m["first_relevant_rank_soft"].as_i64().unwrap() == 1);

        let reranking_m = payload_object["reranking_stage_metrics"]
            .as_object()
            .unwrap();
        assert_eq!(reranking_m["evaluated_k"], 12);
        assert!((reranking_m["ndcg"].as_f64().unwrap() - 0.7).abs() < 1e-5);
    }

    #[test]
    fn storage_row_mapper_maps_none_metrics_to_null() {
        let payload = RequestCaptureStorageRowMapper::map(sample_capture()).unwrap();
        assert!(payload.retrieval_stage_metrics.is_none());
        assert!(payload.reranking_stage_metrics.is_none());
    }
}

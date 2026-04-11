use std::collections::{BTreeMap, HashMap};
use std::env;
use std::path::PathBuf;
use std::sync::{
    Arc, OnceLock,
    atomic::{AtomicUsize, Ordering},
};
use std::time::Duration;

use async_trait::async_trait;
use backon::{ExponentialBuilder, Retryable};
use bm25::{
    EmbedderBuilder, Embedding as Bm25Embedding, Scorer as Bm25Scorer,
    TokenEmbedder as Bm25TokenEmbedder, TokenEmbedding as Bm25TokenEmbedding,
    Tokenizer as Bm25Tokenizer,
};
use reqwest::Client;
use serde_json::{Value, json};
use tokenizers::Tokenizer;
use tracing::{Instrument, field, info_span};

use crate::config::{
    Bm25LikeRetrievalStrategy, DenseRetrievalIngest, HybridRetrievalIngest, RetrievalIngest,
    RetrievalSettings, RetrievalStrategy, RetrySettings,
};
use crate::errors::{RagRuntimeError, RetrievalError};
use crate::models::{
    Chunk, GoldenRetrievalTargets, RetrievalOutput, RetrievedChunk, ValidatedUserRequest,
};
use crate::observability::{
    StatusLabel, mark_span_ok, ordered_page_locator, record_dependency_close,
    record_retrieval_quality_attributes, record_retrieved_chunk_count,
    record_retriever_semantic_metrics, record_retry_attempts, record_stage_close,
};
use crate::retrieval_metrics::RetrievalMetricsHelper;

#[derive(Debug)]
pub struct DenseRetriever {
    runtime: RetrievalRuntime,
    chunking_strategy_cache: OnceLock<String>,
}

#[derive(Debug)]
pub struct HybridRetriever {
    runtime: RetrievalRuntime,
    chunking_strategy_cache: OnceLock<String>,
}

#[async_trait]
pub trait Retriever {
    async fn retrieve(
        &self,
        request: &ValidatedUserRequest,
        golden_targets: Option<&GoldenRetrievalTargets>,
        settings: &RetrievalSettings,
    ) -> Result<RetrievalOutput, RagRuntimeError>;
}

#[derive(Debug, Clone)]
pub(crate) struct RetrievalRuntime {
    client: Client,
    #[cfg(test)]
    ollama_url_override: Option<String>,
    #[cfg(test)]
    qdrant_url_override: Option<String>,
}

impl RetrievalRuntime {
    pub(crate) fn new() -> Self {
        Self {
            client: Client::new(),
            #[cfg(test)]
            ollama_url_override: None,
            #[cfg(test)]
            qdrant_url_override: None,
        }
    }

    pub(crate) async fn retrieve_dense(
        &self,
        request: &ValidatedUserRequest,
        golden_targets: Option<&GoldenRetrievalTargets>,
        settings: &RetrievalSettings,
        ingest: &DenseRetrievalIngest,
    ) -> Result<RetrievalOutput, RagRuntimeError> {
        let embedding = self.embed_query(settings, &request.query).await?;
        let (mut output, search_span) = self
            .vector_search_response_text_dense(settings, request, &embedding, ingest)
            .await?;
        if let Some(golden) = golden_targets {
            let ranked_ids: Vec<String> = output
                .chunks
                .iter()
                .map(|c| c.chunk.chunk_id.clone())
                .collect();
            let metrics = RetrievalMetricsHelper::compute(golden, &ranked_ids, settings.top_k)
                .map_err(|error| RetrievalError::MetricsComputation {
                    message: error.to_string(),
                })?;
            record_retrieval_quality_attributes(&search_span, &metrics);
            {
                let _guard = search_span.enter();
                tracing::info!(
                    retrieval_recall_soft = metrics.recall_soft as f64,
                    retrieval_recall_strict = metrics.recall_strict as f64,
                    retrieval_rr_soft = metrics.rr_soft as f64,
                    retrieval_rr_strict = metrics.rr_strict as f64,
                    retrieval_ndcg = metrics.ndcg as f64,
                    retrieval_first_relevant_rank_soft =
                        field::debug(metrics.first_relevant_rank_soft),
                    retrieval_first_relevant_rank_strict =
                        field::debug(metrics.first_relevant_rank_strict),
                    retrieval_num_relevant_soft = metrics.num_relevant_soft as i64,
                    retrieval_num_relevant_strict = metrics.num_relevant_strict as i64,
                    "retrieval_quality_metrics"
                );
            }
            output.metrics = Some(metrics);
        }
        Ok(output)
    }

    pub(crate) async fn retrieve_hybrid(
        &self,
        request: &ValidatedUserRequest,
        golden_targets: Option<&GoldenRetrievalTargets>,
        settings: &RetrievalSettings,
        ingest: &HybridRetrievalIngest,
    ) -> Result<RetrievalOutput, RagRuntimeError> {
        let embedding = self.embed_query(settings, &request.query).await?;
        let (mut output, search_span) = self
            .vector_search_response_text_hybrid(settings, request, &embedding, ingest)
            .await?;
        if let Some(golden) = golden_targets {
            let ranked_ids: Vec<String> = output
                .chunks
                .iter()
                .map(|c| c.chunk.chunk_id.clone())
                .collect();
            let metrics = RetrievalMetricsHelper::compute(golden, &ranked_ids, settings.top_k)
                .map_err(|error| RetrievalError::MetricsComputation {
                    message: error.to_string(),
                })?;
            record_retrieval_quality_attributes(&search_span, &metrics);
            {
                let _guard = search_span.enter();
                tracing::info!(
                    retrieval_recall_soft = metrics.recall_soft as f64,
                    retrieval_recall_strict = metrics.recall_strict as f64,
                    retrieval_rr_soft = metrics.rr_soft as f64,
                    retrieval_rr_strict = metrics.rr_strict as f64,
                    retrieval_ndcg = metrics.ndcg as f64,
                    retrieval_first_relevant_rank_soft =
                        field::debug(metrics.first_relevant_rank_soft),
                    retrieval_first_relevant_rank_strict =
                        field::debug(metrics.first_relevant_rank_strict),
                    retrieval_num_relevant_soft = metrics.num_relevant_soft as i64,
                    retrieval_num_relevant_strict = metrics.num_relevant_strict as i64,
                    "retrieval_quality_metrics"
                );
            }
            output.metrics = Some(metrics);
        }
        Ok(output)
    }

    async fn embed_query(
        &self,
        settings: &RetrievalSettings,
        query: &str,
    ) -> Result<Vec<f32>, RagRuntimeError> {
        let span = info_span!(
            "retrieval.embedding",
            "span.module" = "retrieval",
            "span.stage" = "embedding",
            status = field::Empty,
            "error.type" = field::Empty,
            "error.message" = field::Empty,
            "openinference.span.kind" = "EMBEDDING",
            "input.value" = %query,
            "input.mime_type" = "text/plain",
            "embedding.model_name" = %settings.embedding_model_name(),
            "embedding.model_provider" = "ollama",
            "embedding.input.count" = 1_i64,
            "embedding.input_role" = "query",
            "embedding.vector_dim" = settings.embedding_dimension() as i64
        );
        let started = std::time::Instant::now();
        let url = format!("{}/api/embed", self.ollama_url(settings));
        let body = json!({
            "model": settings.embedding_model_name(),
            "input": [query],
        });

        let result: Result<Vec<f32>, RagRuntimeError> = async {
            tracing::info!(
                "embedding.model_name" = %settings.embedding_model_name(),
                "embedding.model_provider" = "ollama",
                "embedding.vector_dim" = settings.embedding_dimension() as i64,
                "embedding_metadata"
            );
            let (response_text, retry_attempt_count) =
                retry_with_policy(&settings.embedding_retry, "embedding", || async {
                    let response =
                        self.client
                            .post(&url)
                            .json(&body)
                            .send()
                            .await
                            .map_err(|error| RetrievalError::EmbeddingRequest {
                                message: error.to_string(),
                            })?;
                    if !response.status().is_success() {
                        let status = response.status();
                        let body = response.text().await.unwrap_or_default();
                        return Err(RetrievalError::EmbeddingRequest {
                            message: format!("status {status}: {body}"),
                        });
                    }
                    response
                        .text()
                        .await
                        .map_err(|error| RetrievalError::EmbeddingRequest {
                            message: error.to_string(),
                        })
                })
                .await?;

            let parsed: Value = serde_json::from_str(&response_text).map_err(|error| {
                RetrievalError::EmbeddingResponseValidation {
                    message: format!("invalid json: {error}"),
                }
            })?;
            let embeddings = parsed.get("embeddings").ok_or_else(|| {
                RetrievalError::EmbeddingResponseValidation {
                    message: "missing embeddings".to_string(),
                }
            })?;
            let embeddings_array = embeddings.as_array().ok_or_else(|| {
                RetrievalError::EmbeddingResponseValidation {
                    message: "embeddings is not an array".to_string(),
                }
            })?;
            if embeddings_array.len() != 1 {
                return Err(RetrievalError::EmbeddingResponseValidation {
                    message: format!(
                        "expected exactly one embedding, got {}",
                        embeddings_array.len()
                    ),
                }
                .into());
            }
            let embedding = embeddings_array[0]
                .as_array()
                .ok_or_else(|| RetrievalError::EmbeddingResponseValidation {
                    message: "embedding item is not an array".to_string(),
                })?
                .iter()
                .map(|value| {
                    value.as_f64().map(|number| number as f32).ok_or_else(|| {
                        RetrievalError::EmbeddingResponseValidation {
                            message: "embedding vector item is not numeric".to_string(),
                        }
                    })
                })
                .collect::<Result<Vec<_>, _>>()?;
            if embedding.len() != settings.embedding_dimension() {
                return Err(RetrievalError::EmbeddingDimensionMismatch {
                    expected: settings.embedding_dimension(),
                    actual: embedding.len(),
                }
                .into());
            }
            tracing::info!(
                "embedding.model_name" = %settings.embedding_model_name(),
                embedding_length = embedding.len() as i64,
                retry_attempt_count,
                "embedding_returned"
            );
            mark_span_ok();
            Ok(embedding)
        }
        .instrument(span.clone())
        .await;
        match &result {
            Ok(_) => {
                span.record("status", "ok");
            }
            Err(error) => {
                tracing::info!(
                    "embedding.model_name" = %settings.embedding_model_name(),
                    expected_dimension = settings.embedding_dimension(),
                    error_type = error.error_type(),
                    error_message = %error,
                    "embedding_failed"
                );
                span.record("status", "error");
                span.record("error.type", error.error_type());
                span.record("error.message", field::display(error.to_string()));
            }
        }
        record_dependency_close(
            "retrieval",
            "retrieval",
            "embedding",
            started.elapsed().as_secs_f64() * 1000.0,
            if result.is_ok() {
                StatusLabel::Ok
            } else {
                StatusLabel::Error
            },
        );
        result
    }

    async fn vector_search_response_text_dense(
        &self,
        settings: &RetrievalSettings,
        request: &ValidatedUserRequest,
        embedding: &[f32],
        ingest: &DenseRetrievalIngest,
    ) -> Result<(RetrievalOutput, tracing::Span), RagRuntimeError> {
        let span = info_span!(
            "retrieval.search",
            "span.module" = "retrieval",
            "span.stage" = "vector_search",
            status = field::Empty,
            "error.type" = field::Empty,
            "error.message" = field::Empty,
            "openinference.span.kind" = "RETRIEVER",
            "input.value" = %request.query,
            "input.mime_type" = "text/plain",
            retriever_system = "qdrant",
            retriever_strategy = "dense",
            retriever_collection_name = %ingest.qdrant_collection_name,
            retriever_vector_name = %ingest.qdrant_vector_name,
            retriever_top_k_requested = settings.top_k as i64,
            retriever_score_threshold = settings.score_threshold,
            "corpus.version" = %ingest.corpus_version,
            retriever_top_k_returned = field::Empty,
            retriever_empty = field::Empty,
            retrieval_recall_soft = field::Empty,
            retrieval_recall_strict = field::Empty,
            retrieval_rr_soft = field::Empty,
            retrieval_rr_strict = field::Empty,
            retrieval_ndcg = field::Empty,
            retrieval_num_relevant_soft = field::Empty,
            retrieval_num_relevant_strict = field::Empty,
            retrieval_first_relevant_rank_soft = field::Empty,
            retrieval_first_relevant_rank_strict = field::Empty
        );
        let started = std::time::Instant::now();
        let url = format!(
            "{}/collections/{}/points/query",
            self.qdrant_url(settings),
            ingest.qdrant_collection_name
        );
        let mut body = json!({
            "query": embedding,
            "limit": settings.top_k,
            "score_threshold": settings.score_threshold,
            "with_payload": true,
            "with_vector": false,
        });
        if ingest.qdrant_vector_name != "default" {
            body["using"] = Value::String(ingest.qdrant_vector_name.clone());
        }

        let result: Result<RetrievalOutput, RagRuntimeError> = async {
            tracing::info!(
                trim_whitespace = request.trim_whitespace_applied,
                collapse_internal_whitespace = request.collapse_internal_whitespace_applied,
                normalized_query_length = request.normalized_query_length as i64,
                "input_validation.normalize"
            );
            tracing::info!(
                input_token_count = request.input_token_count as i64,
                tokenizer_source = %request.tokenizer_source,
                "input_validation.token_count"
            );
            tracing::info!(
                retriever_system = "qdrant",
                retriever_strategy = "dense",
                retriever_collection_name = %ingest.qdrant_collection_name,
                retriever_vector_name = %ingest.qdrant_vector_name,
                retriever_top_k_requested = settings.top_k as i64,
                retriever_score_threshold = settings.score_threshold,
                "retriever_metadata"
            );
            let (response_text, retry_attempt_count) =
                retry_with_policy(&settings.qdrant_retry, "vector_search", || async {
                    let response =
                        self.client
                            .post(&url)
                            .json(&body)
                            .send()
                            .await
                            .map_err(|error| RetrievalError::QdrantRequest {
                                message: error.to_string(),
                            })?;
                    if !response.status().is_success() {
                        let status = response.status();
                        let body = response.text().await.unwrap_or_default();
                        return Err(RetrievalError::QdrantRequest {
                            message: format!("status {status}: {body}"),
                        });
                    }
                    response
                        .text()
                        .await
                        .map_err(|error| RetrievalError::QdrantRequest {
                            message: error.to_string(),
                        })
                })
                .await?;
            let output = parse_qdrant_response(&response_text).map_err(|error| {
                tracing::info!(
                    error_type = error.error_type(),
                    error_message = %error,
                    "payload_mapping_failed"
                );
                error
            })?;
            let chunk_ids = output
                .chunks
                .iter()
                .map(|hit| hit.chunk.chunk_id.clone())
                .collect::<Vec<_>>();
            let doc_ids = output
                .chunks
                .iter()
                .map(|hit| hit.chunk.doc_id.clone())
                .collect::<Vec<_>>();
            let locators = output
                .chunks
                .iter()
                .map(|hit| ordered_page_locator(hit.chunk.page_start, hit.chunk.page_end))
                .collect::<Vec<_>>();
            let scores = output
                .chunks
                .iter()
                .map(|hit| hit.score)
                .collect::<Vec<_>>();
            let current = tracing::Span::current();
            current.record("retriever_top_k_returned", output.chunks.len() as i64);
            current.record("retriever_empty", output.chunks.is_empty());
            tracing::info!(
                "retrieval_results.scores" = field::debug(&scores),
                "retrieval_results.chunk_ids" = field::debug(&chunk_ids),
                "retrieval_results.document_ids" = field::debug(&doc_ids),
                "retrieval_results.locators" = field::debug(&locators),
                retry_attempt_count,
                "vector_search_returned"
            );
            record_retrieved_chunk_count(output.chunks.len());
            record_retriever_semantic_metrics(&scores);
            tracing::info!(
                mapped_chunks = output.chunks.len() as i64,
                "retrieval.payload_mapping"
            );
            mark_span_ok();
            Ok(output)
        }
        .instrument(span.clone())
        .await;
        match &result {
            Ok(_) => {
                span.record("status", "ok");
            }
            Err(error) => {
                tracing::info!(
                    collection_name = %ingest.qdrant_collection_name,
                    vector_name = %ingest.qdrant_vector_name,
                    top_k = settings.top_k,
                    score_threshold = settings.score_threshold,
                    error_type = error.error_type(),
                    error_message = %error,
                    "vector_search_failed"
                );
                span.record("status", "error");
                span.record("error.type", error.error_type());
                span.record("error.message", field::display(error.to_string()));
            }
        }
        record_dependency_close(
            "retrieval",
            "retrieval",
            "vector_search",
            started.elapsed().as_secs_f64() * 1000.0,
            if result.is_ok() {
                StatusLabel::Ok
            } else {
                StatusLabel::Error
            },
        );
        result.map(|output| (output, span))
    }

    async fn vector_search_response_text_hybrid(
        &self,
        settings: &RetrievalSettings,
        request: &ValidatedUserRequest,
        embedding: &[f32],
        ingest: &HybridRetrievalIngest,
    ) -> Result<(RetrievalOutput, tracing::Span), RagRuntimeError> {
        let tokenizer = self.load_sparse_tokenizer(ingest).await?;
        let vocabulary = self.load_vocabulary(ingest).await?;
        let sparse_vector = self
            .build_sparse_query_vector(&request.query, ingest, &tokenizer, &vocabulary)
            .await?;
        let effective_collection_name =
            derive_effective_collection_name(&ingest.qdrant_collection_name, &ingest.strategy)?;
        let span = info_span!(
            "retrieval.search",
            "span.module" = "retrieval",
            "span.stage" = "vector_search",
            status = field::Empty,
            "error.type" = field::Empty,
            "error.message" = field::Empty,
            "openinference.span.kind" = "RETRIEVER",
            "input.value" = %request.query,
            "input.mime_type" = "text/plain",
            retriever_system = "qdrant",
            retriever_strategy = "hybrid",
            retriever_collection_name = %effective_collection_name,
            retriever_dense_vector_name = %ingest.dense_vector_name,
            retriever_sparse_vector_name = %ingest.sparse_vector_name,
            retriever_fusion = "rrf",
            retriever_sparse_strategy_kind = %strategy_kind_name(&ingest.strategy),
            retriever_sparse_strategy_version = %strategy_version(&ingest.strategy),
            retriever_top_k_requested = settings.top_k as i64,
            retriever_score_threshold = settings.score_threshold,
            "corpus.version" = %ingest.corpus_version,
            retriever_top_k_returned = field::Empty,
            retriever_empty = field::Empty,
            retrieval_recall_soft = field::Empty,
            retrieval_recall_strict = field::Empty,
            retrieval_rr_soft = field::Empty,
            retrieval_rr_strict = field::Empty,
            retrieval_ndcg = field::Empty,
            retrieval_num_relevant_soft = field::Empty,
            retrieval_num_relevant_strict = field::Empty,
            retrieval_first_relevant_rank_soft = field::Empty,
            retrieval_first_relevant_rank_strict = field::Empty
        );
        let started = std::time::Instant::now();
        let url = format!(
            "{}/collections/{}/points/query",
            self.qdrant_url(settings),
            effective_collection_name
        );
        let body = json!({
            "prefetch": [
                {
                    "query": embedding,
                    "using": ingest.dense_vector_name,
                    "limit": settings.top_k,
                },
                {
                    "query": sparse_vector,
                    "using": ingest.sparse_vector_name,
                    "limit": settings.top_k,
                }
            ],
            "query": { "fusion": "rrf" },
            "limit": settings.top_k,
            "score_threshold": settings.score_threshold,
            "with_payload": true,
            "with_vector": false,
        });

        let result: Result<RetrievalOutput, RagRuntimeError> = async {
            tracing::info!(
                trim_whitespace = request.trim_whitespace_applied,
                collapse_internal_whitespace = request.collapse_internal_whitespace_applied,
                normalized_query_length = request.normalized_query_length as i64,
                "input_validation.normalize"
            );
            tracing::info!(
                input_token_count = request.input_token_count as i64,
                tokenizer_source = %request.tokenizer_source,
                "input_validation.token_count"
            );
            tracing::info!(
                retriever_system = "qdrant",
                retriever_strategy = "hybrid",
                retriever_collection_name = %effective_collection_name,
                retriever_dense_vector_name = %ingest.dense_vector_name,
                retriever_sparse_vector_name = %ingest.sparse_vector_name,
                retriever_fusion = "rrf",
                retriever_sparse_strategy_kind = %strategy_kind_name(&ingest.strategy),
                retriever_sparse_strategy_version = %strategy_version(&ingest.strategy),
                retriever_top_k_requested = settings.top_k as i64,
                retriever_score_threshold = settings.score_threshold,
                "retriever_metadata"
            );
            let (response_text, retry_attempt_count) =
                retry_with_policy(&settings.qdrant_retry, "vector_search", || async {
                    let response =
                        self.client
                            .post(&url)
                            .json(&body)
                            .send()
                            .await
                            .map_err(|error| RetrievalError::QdrantRequest {
                                message: error.to_string(),
                            })?;
                    if !response.status().is_success() {
                        let status = response.status();
                        let body = response.text().await.unwrap_or_default();
                        return Err(RetrievalError::QdrantRequest {
                            message: format!("status {status}: {body}"),
                        });
                    }
                    response
                        .text()
                        .await
                        .map_err(|error| RetrievalError::QdrantRequest {
                            message: error.to_string(),
                        })
                })
                .await?;
            let output = parse_qdrant_response(&response_text).map_err(|error| {
                tracing::info!(
                    error_type = error.error_type(),
                    error_message = %error,
                    "payload_mapping_failed"
                );
                error
            })?;
            let chunk_ids = output
                .chunks
                .iter()
                .map(|hit| hit.chunk.chunk_id.clone())
                .collect::<Vec<_>>();
            let doc_ids = output
                .chunks
                .iter()
                .map(|hit| hit.chunk.doc_id.clone())
                .collect::<Vec<_>>();
            let locators = output
                .chunks
                .iter()
                .map(|hit| ordered_page_locator(hit.chunk.page_start, hit.chunk.page_end))
                .collect::<Vec<_>>();
            let scores = output
                .chunks
                .iter()
                .map(|hit| hit.score)
                .collect::<Vec<_>>();
            let current = tracing::Span::current();
            current.record("retriever_top_k_returned", output.chunks.len() as i64);
            current.record("retriever_empty", output.chunks.is_empty());
            tracing::info!(
                "retrieval_results.scores" = field::debug(&scores),
                "retrieval_results.chunk_ids" = field::debug(&chunk_ids),
                "retrieval_results.document_ids" = field::debug(&doc_ids),
                "retrieval_results.locators" = field::debug(&locators),
                retry_attempt_count,
                "vector_search_returned"
            );
            record_retrieved_chunk_count(output.chunks.len());
            record_retriever_semantic_metrics(&scores);
            tracing::info!(
                mapped_chunks = output.chunks.len() as i64,
                "retrieval.payload_mapping"
            );
            mark_span_ok();
            Ok(output)
        }
        .instrument(span.clone())
        .await;
        match &result {
            Ok(_) => {
                span.record("status", "ok");
            }
            Err(error) => {
                tracing::info!(
                    collection_name = %effective_collection_name,
                    dense_vector_name = %ingest.dense_vector_name,
                    sparse_vector_name = %ingest.sparse_vector_name,
                    top_k = settings.top_k,
                    score_threshold = settings.score_threshold,
                    error_type = error.error_type(),
                    error_message = %error,
                    "hybrid_vector_search_failed"
                );
                span.record("status", "error");
                span.record("error.type", error.error_type());
                span.record("error.message", field::display(error.to_string()));
            }
        }
        record_dependency_close(
            "retrieval",
            "retrieval",
            "vector_search",
            started.elapsed().as_secs_f64() * 1000.0,
            if result.is_ok() {
                StatusLabel::Ok
            } else {
                StatusLabel::Error
            },
        );
        result.map(|output| (output, span))
    }

    #[cfg(test)]
    pub(crate) fn with_base_urls(mut self, ollama_url: String, qdrant_url: String) -> Self {
        self.ollama_url_override = Some(ollama_url);
        self.qdrant_url_override = Some(qdrant_url);
        self
    }

    fn ollama_url(&self, settings: &RetrievalSettings) -> String {
        #[cfg(test)]
        if let Some(url) = self.ollama_url_override.as_deref() {
            return url.to_string();
        }
        settings.ollama_url.clone()
    }

    fn qdrant_url(&self, settings: &RetrievalSettings) -> String {
        #[cfg(test)]
        if let Some(url) = self.qdrant_url_override.as_deref() {
            return url.to_string();
        }
        settings.qdrant_url.clone()
    }

    async fn load_sparse_tokenizer(
        &self,
        ingest: &HybridRetrievalIngest,
    ) -> Result<Tokenizer, RagRuntimeError> {
        let url = tokenizer_url(
            &ingest.tokenizer_source,
            ingest.tokenizer_revision.as_deref(),
        );
        let response = self.client.get(&url).send().await.map_err(|error| {
            RetrievalError::SparseTokenizerInitialization {
                message: format!("request to tokenizer artifact failed: {error}"),
            }
        })?;
        if !response.status().is_success() {
            return Err(RetrievalError::SparseTokenizerInitialization {
                message: format!(
                    "tokenizer artifact returned non-2xx status {}",
                    response.status()
                ),
            }
            .into());
        }
        let bytes = response.bytes().await.map_err(|error| {
            RetrievalError::SparseTokenizerInitialization {
                message: format!("failed to read tokenizer artifact bytes: {error}"),
            }
        })?;
        let json: Value = serde_json::from_slice(&bytes).map_err(|error| {
            RetrievalError::SparseTokenizerInitialization {
                message: format!("tokenizer artifact is not valid json: {error}"),
            }
        })?;
        if !json.is_object() || json.get("model").is_none() {
            return Err(RetrievalError::SparseTokenizerInitialization {
                message: "tokenizer artifact does not look like a tokenizer.json payload"
                    .to_string(),
            }
            .into());
        }
        Tokenizer::from_bytes(bytes.as_ref()).map_err(|error| {
            RetrievalError::SparseTokenizerInitialization {
                message: format!("failed to construct tokenizer from artifact bytes: {error}"),
            }
            .into()
        })
    }

    async fn load_vocabulary(
        &self,
        ingest: &HybridRetrievalIngest,
    ) -> Result<SparseVocabulary, RagRuntimeError> {
        let path = vocabulary_artifact_path(ingest);
        let text = tokio::fs::read_to_string(&path).await.map_err(|error| {
            RetrievalError::ArtifactLoad {
                message: format!(
                    "failed to read sparse vocabulary {}: {error}",
                    path.display()
                ),
            }
        })?;
        let artifact: Value =
            serde_json::from_str(&text).map_err(|error| RetrievalError::ArtifactValidation {
                message: format!("sparse vocabulary is not valid json: {error}"),
            })?;
        parse_sparse_vocabulary(ingest, &artifact)
    }

    async fn load_bm25_term_stats(
        &self,
        ingest: &HybridRetrievalIngest,
        effective_collection_name: &str,
    ) -> Result<Bm25TermStats, RagRuntimeError> {
        let path = bm25_term_stats_artifact_path(ingest, effective_collection_name);
        let text = tokio::fs::read_to_string(&path).await.map_err(|error| {
            RetrievalError::ArtifactLoad {
                message: format!("failed to read bm25 term stats {}: {error}", path.display()),
            }
        })?;
        let artifact: Value =
            serde_json::from_str(&text).map_err(|error| RetrievalError::ArtifactValidation {
                message: format!("bm25 term stats is not valid json: {error}"),
            })?;
        parse_bm25_term_stats(ingest, effective_collection_name, &artifact)
    }

    async fn build_sparse_query_vector(
        &self,
        query: &str,
        ingest: &HybridRetrievalIngest,
        tokenizer: &Tokenizer,
        vocabulary: &SparseVocabulary,
    ) -> Result<Value, RagRuntimeError> {
        let canonical_tokens = tokenize_canonical(ingest, tokenizer, query)?;
        let mut retained_ids = Vec::new();
        for token in canonical_tokens {
            if let Some(token_id) = vocabulary.token_to_id.get(&token) {
                retained_ids.push(*token_id);
            }
        }
        if !query.trim().is_empty() && retained_ids.is_empty() {
            return Err(RetrievalError::EmptySparseQueryVector.into());
        }

        let vector = match &ingest.strategy {
            RetrievalStrategy::BagOfWords(strategy) => {
                validate_bag_of_words_strategy(strategy)?;
                build_sparse_query_vector_bag_of_words(&retained_ids)
            }
            RetrievalStrategy::Bm25Like(strategy) => {
                let effective_collection_name = derive_effective_collection_name(
                    &ingest.qdrant_collection_name,
                    &ingest.strategy,
                )?;
                let term_stats = self
                    .load_bm25_term_stats(ingest, &effective_collection_name)
                    .await?;
                build_sparse_query_vector_bm25_like(
                    strategy,
                    &retained_ids,
                    vocabulary,
                    &term_stats,
                )?
            }
        };
        Ok(json!(vector))
    }

    pub(crate) async fn fetch_chunking_strategy(
        &self,
        qdrant_url: &str,
        collection_name: &str,
    ) -> Result<String, RagRuntimeError> {
        let url = format!(
            "{}/collections/{}",
            qdrant_url.trim_end_matches('/'),
            collection_name
        );
        let response =
            self.client
                .get(&url)
                .send()
                .await
                .map_err(|error| RetrievalError::QdrantRequest {
                    message: format!("collection metadata fetch failed: {}", error),
                })?;
        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(RetrievalError::QdrantRequest {
                message: format!("collection metadata fetch status {status}: {body}"),
            }
            .into());
        }
        let body: Value =
            response
                .json()
                .await
                .map_err(|error| RetrievalError::QdrantResponseValidation {
                    message: format!("collection metadata response parse failed: {}", error),
                })?;
        let strategy = body
            .pointer("/result/config/metadata/chunking_strategy")
            .and_then(|v| v.as_str())
            .ok_or_else(|| RetrievalError::QdrantResponseValidation {
                message: "collection metadata missing chunking_strategy".to_string(),
            })?
            .to_string();
        Ok(strategy)
    }
}
impl DenseRetriever {
    pub fn new() -> Self {
        Self {
            runtime: RetrievalRuntime::new(),
            chunking_strategy_cache: OnceLock::new(),
        }
    }

    #[cfg(test)]
    pub fn with_base_urls(mut self, ollama_url: String, qdrant_url: String) -> Self {
        self.runtime = self.runtime.with_base_urls(ollama_url, qdrant_url);
        self
    }

    #[cfg(test)]
    pub fn with_cached_chunking_strategy(self, strategy: impl Into<String>) -> Self {
        let _ = self.chunking_strategy_cache.set(strategy.into());
        self
    }
}

impl HybridRetriever {
    pub fn new() -> Self {
        Self {
            runtime: RetrievalRuntime::new(),
            chunking_strategy_cache: OnceLock::new(),
        }
    }

    #[cfg(test)]
    pub fn with_base_urls(mut self, ollama_url: String, qdrant_url: String) -> Self {
        self.runtime = self.runtime.with_base_urls(ollama_url, qdrant_url);
        self
    }

    #[cfg(test)]
    pub fn with_cached_chunking_strategy(self, strategy: impl Into<String>) -> Self {
        let _ = self.chunking_strategy_cache.set(strategy.into());
        self
    }
}

async fn run_retrieval_stage<Fut>(future: Fut) -> Result<RetrievalOutput, RagRuntimeError>
where
    Fut: std::future::Future<Output = Result<RetrievalOutput, RagRuntimeError>> + Send,
{
    let started = std::time::Instant::now();
    let result = future.await;
    let status = match &result {
        Ok(_) => StatusLabel::Ok,
        Err(_) => StatusLabel::Error,
    };
    record_stage_close(
        "retrieval",
        "retrieval",
        started.elapsed().as_secs_f64() * 1000.0,
        status,
    );
    result
}

#[async_trait]
impl Retriever for DenseRetriever {
    async fn retrieve(
        &self,
        request: &ValidatedUserRequest,
        golden_targets: Option<&GoldenRetrievalTargets>,
        settings: &RetrievalSettings,
    ) -> Result<RetrievalOutput, RagRuntimeError> {
        run_retrieval_stage(async {
            match &settings.ingest {
                RetrievalIngest::Dense(ingest) => {
                    let chunking_strategy = if let Some(cached) = self.chunking_strategy_cache.get()
                    {
                        cached.clone()
                    } else {
                        let strategy = self
                            .runtime
                            .fetch_chunking_strategy(
                                &settings.qdrant_url,
                                &ingest.qdrant_collection_name,
                            )
                            .await?;
                        let _ = self.chunking_strategy_cache.set(strategy.clone());
                        strategy
                    };
                    let mut output = self
                        .runtime
                        .retrieve_dense(request, golden_targets, settings, ingest)
                        .await?;
                    output.chunking_strategy = chunking_strategy;
                    Ok(output)
                }
                RetrievalIngest::Hybrid(_) => Err(RetrievalError::InvalidConfiguration {
                    message: "dense retriever received non-dense retrieval settings".to_string(),
                }
                .into()),
            }
        })
        .await
    }
}

#[async_trait]
impl Retriever for HybridRetriever {
    async fn retrieve(
        &self,
        request: &ValidatedUserRequest,
        golden_targets: Option<&GoldenRetrievalTargets>,
        settings: &RetrievalSettings,
    ) -> Result<RetrievalOutput, RagRuntimeError> {
        run_retrieval_stage(async {
            match &settings.ingest {
                RetrievalIngest::Hybrid(ingest) => {
                    let effective_collection_name = derive_effective_collection_name(
                        &ingest.qdrant_collection_name,
                        &ingest.strategy,
                    )?;
                    let chunking_strategy = if let Some(cached) = self.chunking_strategy_cache.get()
                    {
                        cached.clone()
                    } else {
                        let strategy = self
                            .runtime
                            .fetch_chunking_strategy(
                                &settings.qdrant_url,
                                &effective_collection_name,
                            )
                            .await?;
                        let _ = self.chunking_strategy_cache.set(strategy.clone());
                        strategy
                    };
                    let mut output = self
                        .runtime
                        .retrieve_hybrid(request, golden_targets, settings, ingest)
                        .await?;
                    output.chunking_strategy = chunking_strategy;
                    Ok(output)
                }
                RetrievalIngest::Dense(_) => Err(RetrievalError::InvalidConfiguration {
                    message: "hybrid retriever received non-hybrid retrieval settings".to_string(),
                }
                .into()),
            }
        })
        .await
    }
}

#[derive(Debug, Clone)]
struct SparseVocabulary {
    token_to_id: HashMap<String, usize>,
}

#[derive(Debug, Clone)]
struct Bm25TermStats {
    document_count: usize,
    average_document_length: f32,
    document_frequency_by_token_id: BTreeMap<usize, usize>,
}

fn tokenizer_url(repo_id: &str, revision: Option<&str>) -> String {
    let revision = revision.unwrap_or("main");
    format!(
        "{}/{repo_id}/resolve/{revision}/tokenizer.json",
        huggingface_base_url()
    )
}

fn huggingface_base_url() -> String {
    #[cfg(test)]
    if let Ok(value) = std::env::var("RAG_RUNTIME_TEST_HF_BASE_URL") {
        return value.trim_end_matches('/').to_string();
    }
    "https://huggingface.co".to_string()
}

fn strategy_kind_name(strategy: &RetrievalStrategy) -> &'static str {
    match strategy {
        RetrievalStrategy::BagOfWords(_) => "bag_of_words",
        RetrievalStrategy::Bm25Like(_) => "bm25_like",
    }
}

fn strategy_version(strategy: &RetrievalStrategy) -> &str {
    match strategy {
        RetrievalStrategy::BagOfWords(strategy) => &strategy.version,
        RetrievalStrategy::Bm25Like(strategy) => &strategy.version,
    }
}

fn derive_effective_collection_name(
    base_name: &str,
    strategy: &RetrievalStrategy,
) -> Result<String, RagRuntimeError> {
    if base_name.ends_with("_bow") || base_name.ends_with("_bm25") || base_name.ends_with('_') {
        return Err(RetrievalError::InvalidConfiguration {
            message: "hybrid qdrant.collection.name must be an unsuffixed base collection name"
                .to_string(),
        }
        .into());
    }
    let suffix = match strategy {
        RetrievalStrategy::BagOfWords(_) => "bow",
        RetrievalStrategy::Bm25Like(_) => "bm25",
    };
    Ok(format!("{base_name}_{suffix}"))
}

fn vocabulary_artifact_path(ingest: &HybridRetrievalIngest) -> PathBuf {
    resolve_repo_relative_path(&ingest.vocabulary_path).join(format!(
        "{}__sparse_vocabulary.json",
        ingest.qdrant_collection_name
    ))
}

fn bm25_term_stats_artifact_path(
    ingest: &HybridRetrievalIngest,
    effective_collection_name: &str,
) -> PathBuf {
    let directory = match &ingest.strategy {
        RetrievalStrategy::Bm25Like(strategy) => {
            resolve_repo_relative_path(&strategy.term_stats_path)
        }
        RetrievalStrategy::BagOfWords(_) => PathBuf::new(),
    };
    directory.join(format!("{effective_collection_name}__term_stats.json"))
}

fn resolve_repo_relative_path(path: &str) -> PathBuf {
    let candidate = PathBuf::from(path);
    if candidate.is_absolute() {
        candidate
    } else {
        repo_root_from_cwd().join(candidate)
    }
}

fn repo_root_from_cwd() -> PathBuf {
    let mut current = env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    loop {
        if current.join("Specification").is_dir() && current.join("Execution").is_dir() {
            return current;
        }
        if !current.pop() {
            return env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
        }
    }
}

fn normalize_sparse_token(token: &str, lowercase: bool, min_token_length: usize) -> Option<String> {
    let mut candidate = if lowercase {
        token.to_lowercase()
    } else {
        token.to_string()
    };
    if candidate.starts_with("##") {
        candidate = candidate[2..].to_string();
    }
    candidate = candidate.trim().to_string();
    while !candidate.is_empty()
        && !candidate
            .chars()
            .next()
            .map(|ch| ch.is_alphanumeric())
            .unwrap_or(false)
    {
        candidate.remove(0);
    }
    while !candidate.is_empty()
        && !candidate
            .chars()
            .last()
            .map(|ch| ch.is_alphanumeric())
            .unwrap_or(false)
    {
        candidate.pop();
    }
    if candidate.len() < min_token_length {
        return None;
    }
    if !candidate.chars().any(|ch| ch.is_alphanumeric()) {
        return None;
    }
    Some(candidate)
}

fn tokenize_canonical(
    ingest: &HybridRetrievalIngest,
    tokenizer: &Tokenizer,
    text: &str,
) -> Result<Vec<String>, RagRuntimeError> {
    let encoding =
        tokenizer
            .encode(text, true)
            .map_err(|error| RetrievalError::SparseQueryConstruction {
                message: format!("failed to encode query with tokenizer: {error}"),
            })?;
    let mut normalized = Vec::new();
    for token in encoding.get_tokens() {
        if let Some(canonical) =
            normalize_sparse_token(token, ingest.lowercase, ingest.min_token_length)
        {
            normalized.push(canonical);
        }
    }
    Ok(normalized)
}

fn parse_sparse_vocabulary(
    ingest: &HybridRetrievalIngest,
    artifact: &Value,
) -> Result<SparseVocabulary, RagRuntimeError> {
    let obj = artifact
        .as_object()
        .ok_or_else(|| RetrievalError::ArtifactValidation {
            message: "sparse vocabulary artifact must be an object".to_string(),
        })?;
    let vocabulary_name = obj
        .get("vocabulary_name")
        .and_then(Value::as_str)
        .ok_or_else(|| RetrievalError::ArtifactValidation {
            message: "sparse vocabulary missing vocabulary_name".to_string(),
        })?;
    let expected_vocabulary_name = format!("{}__sparse_vocabulary", ingest.qdrant_collection_name);
    if vocabulary_name != expected_vocabulary_name {
        return Err(RetrievalError::ArtifactValidation {
            message: "sparse vocabulary vocabulary_name mismatch".to_string(),
        }
        .into());
    }
    let collection_name = obj
        .get("collection_name")
        .and_then(Value::as_str)
        .ok_or_else(|| RetrievalError::ArtifactValidation {
            message: "sparse vocabulary missing collection_name".to_string(),
        })?;
    if collection_name != ingest.qdrant_collection_name {
        return Err(RetrievalError::ArtifactValidation {
            message: "sparse vocabulary collection_name mismatch".to_string(),
        }
        .into());
    }
    let text_processing = obj
        .get("text_processing")
        .and_then(Value::as_object)
        .ok_or_else(|| RetrievalError::ArtifactValidation {
            message: "sparse vocabulary missing text_processing".to_string(),
        })?;
    if text_processing
        .get("preprocessing_kind")
        .and_then(Value::as_str)
        != Some(ingest.preprocessing_kind.as_str())
    {
        return Err(RetrievalError::ArtifactValidation {
            message: "sparse vocabulary preprocessing_kind mismatch".to_string(),
        }
        .into());
    }
    if text_processing.get("lowercase").and_then(Value::as_bool) != Some(ingest.lowercase) {
        return Err(RetrievalError::ArtifactValidation {
            message: "sparse vocabulary lowercase mismatch".to_string(),
        }
        .into());
    }
    if text_processing
        .get("min_token_length")
        .and_then(Value::as_u64)
        != Some(ingest.min_token_length as u64)
    {
        return Err(RetrievalError::ArtifactValidation {
            message: "sparse vocabulary min_token_length mismatch".to_string(),
        }
        .into());
    }
    let tokenizer = obj
        .get("tokenizer")
        .and_then(Value::as_object)
        .ok_or_else(|| RetrievalError::ArtifactValidation {
            message: "sparse vocabulary missing tokenizer".to_string(),
        })?;
    if tokenizer.get("library").and_then(Value::as_str) != Some(ingest.tokenizer_library.as_str()) {
        return Err(RetrievalError::ArtifactValidation {
            message: "sparse vocabulary tokenizer.library mismatch".to_string(),
        }
        .into());
    }
    if tokenizer.get("source").and_then(Value::as_str) != Some(ingest.tokenizer_source.as_str()) {
        return Err(RetrievalError::ArtifactValidation {
            message: "sparse vocabulary tokenizer.source mismatch".to_string(),
        }
        .into());
    }
    if tokenizer.get("revision").and_then(Value::as_str) != ingest.tokenizer_revision.as_deref() {
        return Err(RetrievalError::ArtifactValidation {
            message: "sparse vocabulary tokenizer.revision mismatch".to_string(),
        }
        .into());
    }
    let tokens = obj.get("tokens").and_then(Value::as_array).ok_or_else(|| {
        RetrievalError::ArtifactValidation {
            message: "sparse vocabulary tokens must be an array".to_string(),
        }
    })?;
    let mut token_to_id = HashMap::new();
    for (index, entry) in tokens.iter().enumerate() {
        let entry_obj = entry
            .as_object()
            .ok_or_else(|| RetrievalError::ArtifactValidation {
                message: "sparse vocabulary token entry must be an object".to_string(),
            })?;
        let token = entry_obj
            .get("token")
            .and_then(Value::as_str)
            .ok_or_else(|| RetrievalError::ArtifactValidation {
                message: "sparse vocabulary token entry missing token".to_string(),
            })?;
        let token_id = entry_obj
            .get("token_id")
            .and_then(Value::as_u64)
            .ok_or_else(|| RetrievalError::ArtifactValidation {
                message: "sparse vocabulary token entry missing token_id".to_string(),
            })? as usize;
        if token_id != index {
            return Err(RetrievalError::ArtifactValidation {
                message: "sparse vocabulary token_id must equal zero-based array position"
                    .to_string(),
            }
            .into());
        }
        if token_to_id.insert(token.to_string(), token_id).is_some() {
            return Err(RetrievalError::ArtifactValidation {
                message: "sparse vocabulary token must be unique".to_string(),
            }
            .into());
        }
    }
    Ok(SparseVocabulary { token_to_id })
}

fn parse_bm25_term_stats(
    ingest: &HybridRetrievalIngest,
    effective_collection_name: &str,
    artifact: &Value,
) -> Result<Bm25TermStats, RagRuntimeError> {
    let obj = artifact
        .as_object()
        .ok_or_else(|| RetrievalError::ArtifactValidation {
            message: "bm25 term stats artifact must be an object".to_string(),
        })?;
    if obj.get("collection_name").and_then(Value::as_str) != Some(effective_collection_name) {
        return Err(RetrievalError::ArtifactValidation {
            message: "bm25 term stats collection_name mismatch".to_string(),
        }
        .into());
    }
    let sparse_strategy = obj
        .get("sparse_strategy")
        .and_then(Value::as_object)
        .ok_or_else(|| RetrievalError::ArtifactValidation {
            message: "bm25 term stats missing sparse_strategy".to_string(),
        })?;
    if sparse_strategy.get("kind").and_then(Value::as_str) != Some("bm25_like") {
        return Err(RetrievalError::ArtifactValidation {
            message: "bm25 term stats sparse_strategy.kind mismatch".to_string(),
        }
        .into());
    }
    if sparse_strategy.get("version").and_then(Value::as_str)
        != Some(strategy_version(&ingest.strategy))
    {
        return Err(RetrievalError::ArtifactValidation {
            message: "bm25 term stats sparse_strategy.version mismatch".to_string(),
        }
        .into());
    }
    let expected_vocabulary_name = format!("{}__sparse_vocabulary", ingest.qdrant_collection_name);
    if obj.get("vocabulary_name").and_then(Value::as_str) != Some(expected_vocabulary_name.as_str())
    {
        return Err(RetrievalError::ArtifactValidation {
            message: "bm25 term stats vocabulary_name mismatch".to_string(),
        }
        .into());
    }
    if obj
        .get("vocabulary_identity")
        .and_then(Value::as_object)
        .and_then(|identity| identity.get("collection_name"))
        .and_then(Value::as_str)
        != Some(ingest.qdrant_collection_name.as_str())
    {
        return Err(RetrievalError::ArtifactValidation {
            message: "bm25 term stats vocabulary_identity.collection_name mismatch".to_string(),
        }
        .into());
    }
    let document_count = obj
        .get("document_count")
        .and_then(Value::as_u64)
        .ok_or_else(|| RetrievalError::ArtifactValidation {
            message: "bm25 term stats missing document_count".to_string(),
        })? as usize;
    let average_document_length = obj
        .get("average_document_length")
        .and_then(Value::as_f64)
        .ok_or_else(|| RetrievalError::ArtifactValidation {
            message: "bm25 term stats missing average_document_length".to_string(),
        })? as f32;
    if average_document_length <= 0.0 {
        return Err(RetrievalError::ArtifactValidation {
            message: "bm25 term stats average_document_length must be > 0".to_string(),
        }
        .into());
    }
    let df_obj = obj
        .get("document_frequency_by_token_id")
        .and_then(Value::as_object)
        .ok_or_else(|| RetrievalError::ArtifactValidation {
            message: "bm25 term stats missing document_frequency_by_token_id".to_string(),
        })?;
    let mut document_frequency_by_token_id = BTreeMap::new();
    for (key, value) in df_obj {
        let token_id = key
            .parse::<usize>()
            .map_err(|_| RetrievalError::ArtifactValidation {
                message: "bm25 term stats token id key must be an integer string".to_string(),
            })?;
        let frequency = value
            .as_u64()
            .ok_or_else(|| RetrievalError::ArtifactValidation {
                message: "bm25 term stats frequency must be an integer".to_string(),
            })? as usize;
        if frequency > document_count {
            return Err(RetrievalError::ArtifactValidation {
                message: "bm25 term stats frequency must be <= document_count".to_string(),
            }
            .into());
        }
        document_frequency_by_token_id.insert(token_id, frequency);
    }
    if document_frequency_by_token_id.is_empty() {
        return Err(RetrievalError::ArtifactValidation {
            message: "bm25 term stats document_frequency_by_token_id must not be empty".to_string(),
        }
        .into());
    }
    Ok(Bm25TermStats {
        document_count,
        average_document_length,
        document_frequency_by_token_id,
    })
}

fn build_sparse_query_vector_bag_of_words(token_ids: &[usize]) -> SparseVectorPayload {
    let mut counts = BTreeMap::<usize, usize>::new();
    for token_id in token_ids {
        *counts.entry(*token_id).or_default() += 1;
    }
    SparseVectorPayload {
        indices: counts.keys().copied().collect(),
        values: counts.keys().map(|_| 1.0).collect(),
    }
}

fn validate_bag_of_words_strategy(
    strategy: &crate::config::BagOfWordsRetrievalStrategy,
) -> Result<(), RagRuntimeError> {
    if strategy.version != "v1" {
        return Err(RetrievalError::InvalidConfiguration {
            message: format!(
                "unsupported bag_of_words strategy version {}",
                strategy.version
            ),
        }
        .into());
    }
    if strategy.query_weighting != "binary_presence" {
        return Err(RetrievalError::InvalidConfiguration {
            message: format!(
                "unsupported bag_of_words query_weighting {}",
                strategy.query_weighting
            ),
        }
        .into());
    }
    Ok(())
}

fn build_sparse_query_vector_bm25_like(
    strategy: &Bm25LikeRetrievalStrategy,
    token_ids: &[usize],
    _vocabulary: &SparseVocabulary,
    term_stats: &Bm25TermStats,
) -> Result<SparseVectorPayload, RagRuntimeError> {
    if strategy.version != "v1" {
        return Err(RetrievalError::InvalidConfiguration {
            message: format!(
                "unsupported bm25_like strategy version {}",
                strategy.version
            ),
        }
        .into());
    }
    if strategy.idf_smoothing != "standard" {
        return Err(RetrievalError::SparseQueryConstruction {
            message: format!(
                "unsupported bm25_like idf_smoothing {}; current runtime supports standard with the bm25 crate",
                strategy.idf_smoothing
            ),
        }
        .into());
    }
    let token_id_text = token_ids
        .iter()
        .map(|token_id| token_id.to_string())
        .collect::<Vec<_>>()
        .join(" ");
    let synthetic_corpus = synthetic_bm25_corpus(term_stats);
    let synthetic_texts = synthetic_corpus
        .iter()
        .map(|document| {
            document
                .iter()
                .map(|token_id| token_id.to_string())
                .collect::<Vec<_>>()
                .join(" ")
        })
        .collect::<Vec<_>>();
    let corpus_refs = synthetic_texts
        .iter()
        .map(String::as_str)
        .collect::<Vec<_>>();
    let embedding = EmbedderBuilder::<SparseTokenIdEmbedder, SparseTokenIdTokenizer>::with_tokenizer_and_fit_to_corpus(
        SparseTokenIdTokenizer,
        &corpus_refs,
    )
    .k1(strategy.k1)
    .b(strategy.b)
    .build();
    let query_embedding = embedding.embed(&token_id_text);
    let mut scorer = Bm25Scorer::<usize, usize>::new();
    let mut document_embeddings = Vec::with_capacity(synthetic_texts.len());
    for (document_id, text) in synthetic_texts.iter().enumerate() {
        let document_embedding = embedding.embed(text);
        scorer.upsert(&document_id, document_embedding.clone());
        document_embeddings.push(document_embedding);
    }

    let mut query_tf_weights = BTreeMap::<usize, f32>::new();
    for token in query_embedding.iter() {
        query_tf_weights.entry(token.index).or_insert(token.value);
    }
    let mut first_document_by_token = HashMap::<usize, usize>::new();
    for (document_id, embedding) in document_embeddings.iter().enumerate() {
        for token in embedding.iter() {
            first_document_by_token
                .entry(token.index)
                .or_insert(document_id);
        }
    }
    let mut deduped = BTreeMap::<usize, f32>::new();
    for (token_id, tf_weight) in query_tf_weights {
        let document_id = *first_document_by_token.get(&token_id).ok_or_else(|| {
            RetrievalError::SparseQueryConstruction {
                message: format!("bm25 synthetic corpus does not contain token_id {token_id}"),
            }
        })?;
        let document_token_weight = document_embeddings[document_id]
            .iter()
            .find(|token| token.index == token_id)
            .map(|token| token.value)
            .ok_or_else(|| RetrievalError::SparseQueryConstruction {
                message: format!("bm25 synthetic document is missing token_id {token_id}"),
            })?;
        let idf_component = scorer
            .score(
                &document_id,
                &Bm25Embedding(vec![Bm25TokenEmbedding {
                    index: token_id,
                    value: tf_weight,
                }]),
            )
            .ok_or_else(|| RetrievalError::SparseQueryConstruction {
                message: format!("bm25 scorer failed to score token_id {token_id}"),
            })?;
        let idf_weight = if document_token_weight == 0.0 {
            0.0
        } else {
            idf_component / document_token_weight
        };
        deduped.insert(token_id, tf_weight * idf_weight);
    }
    Ok(SparseVectorPayload {
        indices: deduped.keys().copied().collect(),
        values: deduped.values().copied().collect(),
    })
}

fn synthetic_bm25_corpus(term_stats: &Bm25TermStats) -> Vec<Vec<usize>> {
    let mut documents = vec![Vec::<usize>::new(); term_stats.document_count];
    let mut doc_cursor = 0usize;
    for (&token_id, &document_frequency) in &term_stats.document_frequency_by_token_id {
        for _ in 0..document_frequency {
            documents[doc_cursor % term_stats.document_count].push(token_id);
            doc_cursor += 1;
        }
    }

    let current_total_tokens = documents.iter().map(Vec::len).sum::<usize>();
    let target_total_tokens =
        (term_stats.average_document_length * term_stats.document_count as f32).round() as usize;
    let mut filler_id = term_stats
        .document_frequency_by_token_id
        .keys()
        .max()
        .copied()
        .unwrap_or(0)
        .saturating_add(1);
    let mut remaining = target_total_tokens.saturating_sub(current_total_tokens);
    let mut doc_index = 0usize;
    while remaining > 0 {
        documents[doc_index % term_stats.document_count].push(filler_id);
        filler_id = filler_id.saturating_add(1);
        doc_index += 1;
        remaining -= 1;
    }
    documents
}

#[derive(Default)]
struct SparseTokenIdTokenizer;

impl Bm25Tokenizer for SparseTokenIdTokenizer {
    fn tokenize(&self, input_text: &str) -> Vec<String> {
        input_text
            .split_whitespace()
            .filter(|token| !token.is_empty())
            .map(str::to_string)
            .collect()
    }
}

struct SparseTokenIdEmbedder;

impl Bm25TokenEmbedder for SparseTokenIdEmbedder {
    type EmbeddingSpace = usize;

    fn embed(token: &str) -> Self::EmbeddingSpace {
        token
            .parse::<usize>()
            .expect("sparse token ids passed into bm25 embedder must be numeric")
    }
}

#[derive(Debug, Clone, serde::Serialize)]
struct SparseVectorPayload {
    indices: Vec<usize>,
    values: Vec<f32>,
}

fn parse_qdrant_response(response_text: &str) -> Result<RetrievalOutput, RagRuntimeError> {
    let parsed: Value = serde_json::from_str(response_text).map_err(|error| {
        RetrievalError::QdrantResponseValidation {
            message: format!("invalid json: {error}"),
        }
    })?;
    let result = parsed
        .get("result")
        .ok_or_else(|| RetrievalError::QdrantResponseValidation {
            message: "missing result".to_string(),
        })?;

    let hits = if let Some(array) = result.as_array() {
        array.clone()
    } else if let Some(points) = result.get("points").and_then(Value::as_array) {
        points.clone()
    } else {
        return Err(RetrievalError::QdrantResponseValidation {
            message: "result is neither array nor object with points".to_string(),
        }
        .into());
    };

    let mut chunks = Vec::with_capacity(hits.len());
    for hit in hits {
        let score = hit.get("score").and_then(Value::as_f64).ok_or_else(|| {
            RetrievalError::QdrantResponseValidation {
                message: "hit missing score".to_string(),
            }
        })? as f32;
        let payload = hit
            .get("payload")
            .ok_or_else(|| RetrievalError::QdrantResponseValidation {
                message: "hit missing payload".to_string(),
            })?
            .clone();
        let chunk: Chunk =
            serde_json::from_value(payload).map_err(|error| RetrievalError::PayloadMapping {
                message: format!("failed to deserialize payload into Chunk: {error}"),
            })?;
        chunk
            .validate()
            .map_err(|message| RetrievalError::PayloadMapping { message })?;
        chunks.push(RetrievedChunk { chunk, score });
    }
    Ok(RetrievalOutput {
        chunks,
        metrics: None,
        chunking_strategy: String::new(),
    })
}

async fn retry_with_policy<F, Fut, T>(
    settings: &RetrySettings,
    dependency: &'static str,
    operation: F,
) -> Result<(T, usize), RagRuntimeError>
where
    F: Fn() -> Fut,
    Fut: std::future::Future<Output = Result<T, RetrievalError>>,
{
    let failure_count = Arc::new(AtomicUsize::new(0));
    let builder = match settings.backoff {
        crate::config::RetryBackoff::Exponential => ExponentialBuilder::default()
            .with_factor(2.0)
            .with_min_delay(Duration::from_millis(10))
            .with_max_delay(Duration::from_millis(250))
            .with_jitter()
            .with_max_times(settings.max_attempts),
    };
    let result = (|| {
        let failure_count = Arc::clone(&failure_count);
        let future = operation();
        async move {
            let value = future.await;
            if value.is_err() {
                failure_count.fetch_add(1, Ordering::Relaxed);
            }
            value
        }
    })
    .retry(builder)
    .await;
    let retry_attempts = failure_count.load(Ordering::Relaxed).saturating_sub(1);
    if retry_attempts > 0 {
        record_retry_attempts(dependency, retry_attempts);
    }
    let result = result?;
    Ok((result, retry_attempts))
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::http::StatusCode;
    use serde_json::json;
    use tempfile::tempdir;

    use crate::models::ValidatedUserRequest;
    use crate::retrieval::{DenseRetriever, HybridRetriever, Retriever};
    use crate::test_support::{
        MockHttpResponse, MockHttpServer, TempEnvVar, env_lock, test_settings,
    };

    struct TestRetriever<R> {
        retriever: R,
        settings: RetrievalSettings,
    }

    impl<R> TestRetriever<R>
    where
        R: Retriever,
    {
        async fn retrieve(
            &self,
            request: &ValidatedUserRequest,
        ) -> Result<RetrievalOutput, RagRuntimeError> {
            self.retriever.retrieve(request, None, &self.settings).await
        }
    }

    const TEST_TOKENIZER_JSON: &str = r#"{
      "version":"1.0",
      "truncation":null,
      "padding":null,
      "added_tokens":[],
      "normalizer":null,
      "pre_tokenizer":{"type":"Whitespace"},
      "post_processor":null,
      "decoder":null,
      "model":{"type":"WordLevel","vocab":{"[UNK]":0,"hello":1,"world":2,"alpha":3,"beta":4},"unk_token":"[UNK]"}
    }"#;

    fn sample_chunk_json() -> Value {
        json!({
            "schema_version": 1,
            "doc_id": "doc-1",
            "chunk_id": "chunk-1",
            "url": "local://doc",
            "document_title": "Doc",
            "section_title": "Section",
            "section_path": ["Section"],
            "chunk_index": 0,
            "page_start": 1,
            "page_end": 1,
            "tags": ["tag"],
            "content_hash": "sha256:abc",
            "chunking_version": "v1",
            "chunk_created_at": "2026-01-01T00:00:00Z",
            "text": "hello"
        })
    }

    fn build_engine(
        embedding_server: &MockHttpServer,
        qdrant_server: &MockHttpServer,
    ) -> TestRetriever<DenseRetriever> {
        TestRetriever {
            retriever: DenseRetriever::new()
                .with_base_urls(embedding_server.endpoint(), qdrant_server.endpoint())
                .with_cached_chunking_strategy("structural"),
            settings: test_settings().retrieval,
        }
    }

    fn build_dense_retriever_with_settings(
        settings: RetrievalSettings,
        ollama_url: String,
        qdrant_url: String,
    ) -> TestRetriever<DenseRetriever> {
        TestRetriever {
            retriever: DenseRetriever::new()
                .with_base_urls(ollama_url, qdrant_url)
                .with_cached_chunking_strategy("structural"),
            settings,
        }
    }

    fn build_hybrid_retriever_with_settings(
        settings: RetrievalSettings,
        ollama_url: String,
        qdrant_url: String,
    ) -> TestRetriever<HybridRetriever> {
        TestRetriever {
            retriever: HybridRetriever::new()
                .with_base_urls(ollama_url, qdrant_url)
                .with_cached_chunking_strategy("structural"),
            settings,
        }
    }

    fn hybrid_bow_settings(vocabulary_dir: &str) -> RetrievalSettings {
        let mut settings = test_settings().retrieval;
        settings.kind = crate::config::RetrievalKind::Hybrid;
        settings.ingest = RetrievalIngest::Hybrid(HybridRetrievalIngest {
            embedding_model_name: "qwen3-embedding:0.6b".to_string(),
            embedding_dimension: 3,
            qdrant_collection_name: "chunks_hybrid_test".to_string(),
            dense_vector_name: "dense".to_string(),
            sparse_vector_name: "sparse".to_string(),
            corpus_version: "v1".to_string(),
            tokenizer_library: "tokenizers".to_string(),
            tokenizer_source: "test/sparse".to_string(),
            tokenizer_revision: None,
            preprocessing_kind: "basic_word_v1".to_string(),
            lowercase: true,
            min_token_length: 2,
            vocabulary_path: vocabulary_dir.to_string(),
            strategy: RetrievalStrategy::BagOfWords(crate::config::BagOfWordsRetrievalStrategy {
                version: "v1".to_string(),
                query_weighting: "binary_presence".to_string(),
            }),
        });
        settings
    }

    fn hybrid_bow_settings_with_revision(
        vocabulary_dir: &str,
        revision: Option<&str>,
    ) -> RetrievalSettings {
        let mut settings = hybrid_bow_settings(vocabulary_dir);
        if let RetrievalIngest::Hybrid(ingest) = &mut settings.ingest {
            ingest.tokenizer_revision = revision.map(str::to_string);
        }
        settings
    }

    fn hybrid_bm25_settings(vocabulary_dir: &str, term_stats_dir: &str) -> RetrievalSettings {
        let mut settings = hybrid_bow_settings(vocabulary_dir);
        settings.ingest = RetrievalIngest::Hybrid(HybridRetrievalIngest {
            embedding_model_name: "qwen3-embedding:0.6b".to_string(),
            embedding_dimension: 3,
            qdrant_collection_name: "chunks_hybrid_test".to_string(),
            dense_vector_name: "dense".to_string(),
            sparse_vector_name: "sparse".to_string(),
            corpus_version: "v1".to_string(),
            tokenizer_library: "tokenizers".to_string(),
            tokenizer_source: "test/sparse".to_string(),
            tokenizer_revision: None,
            preprocessing_kind: "basic_word_v1".to_string(),
            lowercase: true,
            min_token_length: 2,
            vocabulary_path: vocabulary_dir.to_string(),
            strategy: RetrievalStrategy::Bm25Like(Bm25LikeRetrievalStrategy {
                version: "v1".to_string(),
                query_weighting: "bm25_query_weight".to_string(),
                k1: 1.2,
                b: 0.75,
                idf_smoothing: "standard".to_string(),
                term_stats_path: term_stats_dir.to_string(),
            }),
        });
        settings
    }

    fn write_vocabulary_with_revision(
        dir: &std::path::Path,
        collection_name: &str,
        tokens: &[&str],
        revision: Option<&str>,
    ) {
        let token_entries = tokens
            .iter()
            .enumerate()
            .map(|(index, token)| json!({"token": token, "token_id": index}))
            .collect::<Vec<_>>();
        let mut tokenizer = json!({
            "library": "tokenizers",
            "source": "test/sparse"
        });
        if let Some(revision) = revision {
            tokenizer["revision"] = json!(revision);
        }
        std::fs::write(
            dir.join(format!("{collection_name}__sparse_vocabulary.json")),
            json!({
                "vocabulary_name": format!("{collection_name}__sparse_vocabulary"),
                "collection_name": collection_name,
                "text_processing": {
                    "preprocessing_kind": "basic_word_v1",
                    "lowercase": true,
                    "min_token_length": 2
                },
                "tokenizer": tokenizer,
                "created_at": "2026-04-03T00:00:00Z",
                "tokens": token_entries
            })
            .to_string(),
        )
        .unwrap();
    }

    fn write_vocabulary(dir: &std::path::Path, collection_name: &str, tokens: &[&str]) {
        write_vocabulary_with_revision(dir, collection_name, tokens, None);
    }

    fn write_term_stats(
        dir: &std::path::Path,
        effective_collection_name: &str,
        base_collection_name: &str,
    ) {
        std::fs::write(
            dir.join(format!("{effective_collection_name}__term_stats.json")),
            json!({
                "collection_name": effective_collection_name,
                "sparse_strategy": {
                    "kind": "bm25_like",
                    "version": "v1"
                },
                "vocabulary_name": format!("{base_collection_name}__sparse_vocabulary"),
                "vocabulary_identity": {
                    "collection_name": base_collection_name
                },
                "document_count": 10,
                "average_document_length": 5.0,
                "document_frequency_by_token_id": {
                    "0": 2,
                    "1": 3
                },
                "created_at": "2026-04-03T00:00:00Z"
            })
            .to_string(),
        )
        .unwrap();
    }

    fn write_term_stats_with_identity(
        dir: &std::path::Path,
        effective_collection_name: &str,
        base_collection_name: &str,
        identity_collection_name: &str,
    ) {
        std::fs::write(
            dir.join(format!("{effective_collection_name}__term_stats.json")),
            json!({
                "collection_name": effective_collection_name,
                "sparse_strategy": {
                    "kind": "bm25_like",
                    "version": "v1"
                },
                "vocabulary_name": format!("{base_collection_name}__sparse_vocabulary"),
                "vocabulary_identity": {
                    "collection_name": identity_collection_name
                },
                "document_count": 10,
                "average_document_length": 5.0,
                "document_frequency_by_token_id": {
                    "0": 2,
                    "1": 3
                },
                "created_at": "2026-04-03T00:00:00Z"
            })
            .to_string(),
        )
        .unwrap();
    }

    #[tokio::test]
    async fn successful_embedding_and_qdrant_response_preserve_hit_order() {
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let second_chunk = json!({
            "schema_version": 1,
            "doc_id": "doc-2",
            "chunk_id": "chunk-2",
            "url": "local://doc",
            "document_title": "Doc",
            "section_title": "Section",
            "section_path": ["Section"],
            "chunk_index": 1,
            "page_start": 2,
            "page_end": 2,
            "tags": ["tag"],
            "content_hash": "sha256:def",
            "chunking_version": "v1",
            "chunk_created_at": "2026-01-01T00:00:00Z",
            "text": "world"
        });
        let qdrant_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"result":{"points":[
                {"score":0.9,"payload":sample_chunk_json()},
                {"score":0.7,"payload":second_chunk}
            ]}})
            .to_string(),
        }])
        .await;
        let engine = build_engine(&embedding_server, &qdrant_server);
        let output = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello".to_string(),
                input_token_count: 1,
                ..Default::default()
            })
            .await
            .unwrap();
        assert_eq!(output.chunks.len(), 2);
        assert_eq!(output.chunks[0].chunk.chunk_id, "chunk-1");
        assert_eq!(output.chunks[1].chunk.chunk_id, "chunk-2");
    }

    #[tokio::test]
    async fn embedding_request_transport_failure_returns_exact_variant() {
        let embedding_server = MockHttpServer::start(vec![]).await;
        let qdrant_server = MockHttpServer::start(vec![]).await;
        let engine = build_dense_retriever_with_settings(
            test_settings().retrieval,
            "http://127.0.0.1:9".to_string(),
            qdrant_server.endpoint(),
        );
        let error = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello".to_string(),
                input_token_count: 1,
                ..Default::default()
            })
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "retrieval.embedding_request");
        drop(embedding_server);
    }

    #[tokio::test]
    async fn embedding_non_2xx_returns_exact_variant() {
        let embedding_server = MockHttpServer::start(
            (0..10)
                .map(|_| MockHttpResponse {
                    status: StatusCode::BAD_GATEWAY,
                    body: "bad".to_string(),
                })
                .collect(),
        )
        .await;
        let qdrant_server = MockHttpServer::start(vec![]).await;
        let engine = build_engine(&embedding_server, &qdrant_server);
        let error = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello".to_string(),
                input_token_count: 1,
                ..Default::default()
            })
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "retrieval.embedding_request");
    }

    #[tokio::test]
    async fn embedding_invalid_json_shape_returns_validation_variant() {
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: "{".to_string(),
        }])
        .await;
        let qdrant_server = MockHttpServer::start(vec![]).await;
        let engine = build_engine(&embedding_server, &qdrant_server);
        let error = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello".to_string(),
                input_token_count: 1,
                ..Default::default()
            })
            .await
            .unwrap_err();
        assert_eq!(
            error.error_type(),
            "retrieval.embedding_response_validation"
        );
    }

    #[tokio::test]
    async fn embedding_missing_embeddings_returns_validation_variant() {
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"other":[]}).to_string(),
        }])
        .await;
        let qdrant_server = MockHttpServer::start(vec![]).await;
        let engine = build_engine(&embedding_server, &qdrant_server);
        let error = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello".to_string(),
                input_token_count: 1,
                ..Default::default()
            })
            .await
            .unwrap_err();
        assert_eq!(
            error.error_type(),
            "retrieval.embedding_response_validation"
        );
    }

    #[tokio::test]
    async fn embedding_more_than_one_vector_returns_validation_variant() {
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3],[0.4,0.5,0.6]]}).to_string(),
        }])
        .await;
        let qdrant_server = MockHttpServer::start(vec![]).await;
        let engine = build_engine(&embedding_server, &qdrant_server);
        let error = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello".to_string(),
                input_token_count: 1,
                ..Default::default()
            })
            .await
            .unwrap_err();
        assert_eq!(
            error.error_type(),
            "retrieval.embedding_response_validation"
        );
    }

    #[tokio::test]
    async fn embedding_dimension_mismatch_returns_exact_variant() {
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2]]}).to_string(),
        }])
        .await;
        let qdrant_server = MockHttpServer::start(vec![]).await;
        let engine = build_engine(&embedding_server, &qdrant_server);
        let error = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello".to_string(),
                input_token_count: 1,
                ..Default::default()
            })
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "retrieval.embedding_dimension_mismatch");
    }

    #[tokio::test]
    async fn embeddings_field_must_be_array() {
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":{"vector":[0.1,0.2,0.3]}}).to_string(),
        }])
        .await;
        let qdrant_server = MockHttpServer::start(vec![]).await;
        let engine = build_engine(&embedding_server, &qdrant_server);
        let error = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello".to_string(),
                input_token_count: 1,
                ..Default::default()
            })
            .await
            .unwrap_err();
        assert_eq!(
            error.error_type(),
            "retrieval.embedding_response_validation"
        );
    }

    #[tokio::test]
    async fn embedding_item_must_be_array() {
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[{"vector":[0.1,0.2,0.3]}]}).to_string(),
        }])
        .await;
        let qdrant_server = MockHttpServer::start(vec![]).await;
        let engine = build_engine(&embedding_server, &qdrant_server);
        let error = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello".to_string(),
                input_token_count: 1,
                ..Default::default()
            })
            .await
            .unwrap_err();
        assert_eq!(
            error.error_type(),
            "retrieval.embedding_response_validation"
        );
    }

    #[tokio::test]
    async fn zero_embeddings_return_validation_variant() {
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[]}).to_string(),
        }])
        .await;
        let qdrant_server = MockHttpServer::start(vec![]).await;
        let engine = build_engine(&embedding_server, &qdrant_server);
        let error = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello".to_string(),
                input_token_count: 1,
                ..Default::default()
            })
            .await
            .unwrap_err();
        assert_eq!(
            error.error_type(),
            "retrieval.embedding_response_validation"
        );
    }

    #[tokio::test]
    async fn qdrant_non_2xx_returns_exact_variant() {
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let qdrant_server = MockHttpServer::start(
            (0..10)
                .map(|_| MockHttpResponse {
                    status: StatusCode::BAD_GATEWAY,
                    body: "bad".to_string(),
                })
                .collect(),
        )
        .await;
        let engine = build_engine(&embedding_server, &qdrant_server);
        let error = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello".to_string(),
                input_token_count: 1,
                ..Default::default()
            })
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "retrieval.qdrant_request");
    }

    #[test]
    fn missing_result_returns_qdrant_validation_error() {
        let error = parse_qdrant_response(&json!({"status":"ok"}).to_string()).unwrap_err();
        assert_eq!(error.error_type(), "retrieval.qdrant_response_validation");
    }

    #[test]
    fn invalid_result_shape_returns_qdrant_validation_error() {
        let error =
            parse_qdrant_response(&json!({"result":{"foo":"bar"}}).to_string()).unwrap_err();
        assert_eq!(error.error_type(), "retrieval.qdrant_response_validation");
    }

    #[test]
    fn hit_missing_score_returns_qdrant_validation_error() {
        let error =
            parse_qdrant_response(&json!({"result":[{"payload":sample_chunk_json()}]}).to_string())
                .unwrap_err();
        assert_eq!(error.error_type(), "retrieval.qdrant_response_validation");
    }

    #[test]
    fn hit_missing_payload_returns_qdrant_validation_error() {
        let error =
            parse_qdrant_response(&json!({"result":[{"score":0.9}]}).to_string()).unwrap_err();
        assert_eq!(error.error_type(), "retrieval.qdrant_response_validation");
    }

    #[test]
    fn invalid_payload_returns_payload_mapping_error() {
        let error = parse_qdrant_response(
            &json!({"result":[{"score":0.9,"payload":{"schema_version":1}}]}).to_string(),
        )
        .unwrap_err();
        assert_eq!(error.error_type(), "retrieval.payload_mapping");
    }

    #[test]
    fn contract_violating_payload_returns_payload_mapping_error() {
        let mut payload = sample_chunk_json();
        payload["page_end"] = json!(0);
        let error =
            parse_qdrant_response(&json!({"result":[{"score":0.9,"payload":payload}]}).to_string())
                .unwrap_err();
        assert_eq!(error.error_type(), "retrieval.payload_mapping");
    }

    #[test]
    fn empty_qdrant_result_returns_empty_output() {
        let output = parse_qdrant_response(&json!({"result":{"points":[]}}).to_string()).unwrap();
        assert!(output.chunks.is_empty());
    }

    #[test]
    fn qdrant_result_points_array_is_supported() {
        let output = parse_qdrant_response(
            &json!({"result":{"points":[{"score":0.9,"payload":sample_chunk_json()}]}}).to_string(),
        )
        .unwrap();
        assert_eq!(output.chunks.len(), 1);
        assert_eq!(output.chunks[0].chunk.chunk_id, "chunk-1");
    }

    #[tokio::test]
    async fn qdrant_request_body_uses_contract_fields() {
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let qdrant_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"result":[]}).to_string(),
        }])
        .await;
        let engine = build_engine(&embedding_server, &qdrant_server);
        let _ = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello".to_string(),
                input_token_count: 1,
                ..Default::default()
            })
            .await
            .unwrap();
        let request = qdrant_server.recorded_requests().remove(0);
        assert_eq!(request["with_payload"], true);
        assert_eq!(request["with_vector"], false);
        assert!(request.get("using").is_none());
    }

    #[tokio::test]
    async fn transient_embedding_failure_then_success_retries() {
        let embedding_server = MockHttpServer::start(vec![
            MockHttpResponse {
                status: StatusCode::BAD_GATEWAY,
                body: "bad".to_string(),
            },
            MockHttpResponse {
                status: StatusCode::OK,
                body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
            },
        ])
        .await;
        let qdrant_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"result":[]}).to_string(),
        }])
        .await;
        let engine = build_engine(&embedding_server, &qdrant_server);
        let output = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello".to_string(),
                input_token_count: 1,
                ..Default::default()
            })
            .await
            .unwrap();
        assert!(output.chunks.is_empty());
        assert_eq!(embedding_server.recorded_requests().len(), 2);
    }

    #[tokio::test]
    async fn transient_qdrant_failure_then_success_retries() {
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let qdrant_server = MockHttpServer::start(vec![
            MockHttpResponse {
                status: StatusCode::BAD_GATEWAY,
                body: "bad".to_string(),
            },
            MockHttpResponse {
                status: StatusCode::OK,
                body: json!({"result":[]}).to_string(),
            },
        ])
        .await;
        let engine = build_engine(&embedding_server, &qdrant_server);
        let output = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello".to_string(),
                input_token_count: 1,
                ..Default::default()
            })
            .await
            .unwrap();
        assert!(output.chunks.is_empty());
        assert_eq!(qdrant_server.recorded_requests().len(), 2);
    }

    #[tokio::test]
    async fn embedding_retry_exhaustion_returns_request_error() {
        let embedding_server = MockHttpServer::start(vec![
            MockHttpResponse {
                status: StatusCode::BAD_GATEWAY,
                body: "bad".to_string(),
            };
            10
        ])
        .await;
        let qdrant_server = MockHttpServer::start(vec![]).await;
        let engine = build_engine(&embedding_server, &qdrant_server);
        let error = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello".to_string(),
                input_token_count: 1,
                ..Default::default()
            })
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "retrieval.embedding_request");
        assert_eq!(embedding_server.recorded_requests().len(), 4);
    }

    #[tokio::test]
    async fn qdrant_retry_exhaustion_returns_request_error() {
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let qdrant_server = MockHttpServer::start(vec![
            MockHttpResponse {
                status: StatusCode::BAD_GATEWAY,
                body: "bad".to_string(),
            };
            10
        ])
        .await;
        let engine = build_engine(&embedding_server, &qdrant_server);
        let error = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello".to_string(),
                input_token_count: 1,
                ..Default::default()
            })
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "retrieval.qdrant_request");
        assert_eq!(qdrant_server.recorded_requests().len(), 4);
    }

    #[tokio::test]
    async fn hybrid_bow_request_uses_prefetch_and_rrf_fusion() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let tokenizer_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: TEST_TOKENIZER_JSON.to_string(),
        }])
        .await;
        let qdrant_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"result":{"points":[]}}).to_string(),
        }])
        .await;
        let tempdir = tempdir().unwrap();
        write_vocabulary(tempdir.path(), "chunks_hybrid_test", &["hello", "world"]);
        let _hf_base = TempEnvVar::set("RAG_RUNTIME_TEST_HF_BASE_URL", tokenizer_server.endpoint());
        let engine = build_hybrid_retriever_with_settings(
            hybrid_bow_settings(tempdir.path().to_str().unwrap()),
            embedding_server.endpoint(),
            qdrant_server.endpoint(),
        );

        let output = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello world".to_string(),
                input_token_count: 2,
                ..Default::default()
            })
            .await
            .unwrap();
        assert!(output.chunks.is_empty());

        let request = qdrant_server.recorded_requests().remove(0);
        assert_eq!(
            qdrant_server.recorded_paths(),
            vec!["/collections/chunks_hybrid_test_bow/points/query".to_string()]
        );
        assert_eq!(request["query"]["fusion"], "rrf");
        assert_eq!(request["prefetch"][0]["using"], "dense");
        assert_eq!(request["prefetch"][1]["using"], "sparse");
        assert_eq!(request["prefetch"][0]["limit"], 3);
        assert_eq!(request["prefetch"][1]["limit"], 3);
        assert_eq!(request["limit"], 3);
        assert_eq!(request["with_payload"], true);
        assert_eq!(request["with_vector"], false);
        assert_eq!(request["prefetch"][1]["query"]["indices"], json!([0, 1]));
        assert_eq!(request["prefetch"][1]["query"]["values"], json!([1.0, 1.0]));
    }

    #[tokio::test]
    async fn hybrid_tokenizer_url_uses_revision_when_present() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let tokenizer_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: TEST_TOKENIZER_JSON.to_string(),
        }])
        .await;
        let qdrant_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"result":{"points":[]}}).to_string(),
        }])
        .await;
        let tempdir = tempdir().unwrap();
        write_vocabulary_with_revision(
            tempdir.path(),
            "chunks_hybrid_test",
            &["hello", "world"],
            Some("rev-123"),
        );
        let _hf_base = TempEnvVar::set("RAG_RUNTIME_TEST_HF_BASE_URL", tokenizer_server.endpoint());
        let engine = build_hybrid_retriever_with_settings(
            hybrid_bow_settings_with_revision(tempdir.path().to_str().unwrap(), Some("rev-123")),
            embedding_server.endpoint(),
            qdrant_server.endpoint(),
        );

        let _ = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello world".to_string(),
                input_token_count: 2,
                ..Default::default()
            })
            .await
            .unwrap();

        assert_eq!(
            tokenizer_server.recorded_paths(),
            vec!["/test/sparse/resolve/rev-123/tokenizer.json".to_string()]
        );
    }

    #[tokio::test]
    async fn hybrid_sparse_query_ignores_out_of_vocabulary_tokens() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let tokenizer_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: TEST_TOKENIZER_JSON.to_string(),
        }])
        .await;
        let qdrant_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"result":{"points":[]}}).to_string(),
        }])
        .await;
        let tempdir = tempdir().unwrap();
        write_vocabulary(tempdir.path(), "chunks_hybrid_test", &["hello"]);
        let _hf_base = TempEnvVar::set("RAG_RUNTIME_TEST_HF_BASE_URL", tokenizer_server.endpoint());
        let engine = build_hybrid_retriever_with_settings(
            hybrid_bow_settings(tempdir.path().to_str().unwrap()),
            embedding_server.endpoint(),
            qdrant_server.endpoint(),
        );

        let output = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello world".to_string(),
                input_token_count: 2,
                ..Default::default()
            })
            .await
            .unwrap();
        assert!(output.chunks.is_empty());

        let request = qdrant_server.recorded_requests().remove(0);
        assert_eq!(request["prefetch"][1]["query"]["indices"], json!([0]));
        assert_eq!(request["prefetch"][1]["query"]["values"], json!([1.0]));
    }

    #[tokio::test]
    async fn hybrid_empty_sparse_query_vector_returns_exact_variant() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let tokenizer_server = MockHttpServer::start(vec![
            MockHttpResponse {
                status: StatusCode::OK,
                body: TEST_TOKENIZER_JSON.to_string(),
            },
            MockHttpResponse {
                status: StatusCode::OK,
                body: TEST_TOKENIZER_JSON.to_string(),
            },
        ])
        .await;
        let qdrant_server = MockHttpServer::start(vec![]).await;
        let tempdir = tempdir().unwrap();
        write_vocabulary(tempdir.path(), "chunks_hybrid_test", &["alpha"]);
        let _hf_base = TempEnvVar::set("RAG_RUNTIME_TEST_HF_BASE_URL", tokenizer_server.endpoint());
        let engine = build_hybrid_retriever_with_settings(
            hybrid_bow_settings(tempdir.path().to_str().unwrap()),
            embedding_server.endpoint(),
            qdrant_server.endpoint(),
        );

        let error = engine
            .retrieve(&ValidatedUserRequest {
                query: "world".to_string(),
                input_token_count: 1,
                ..Default::default()
            })
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "retrieval.empty_sparse_query_vector");
    }

    #[tokio::test]
    async fn hybrid_bag_of_words_invalid_version_returns_invalid_configuration() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let tokenizer_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: TEST_TOKENIZER_JSON.to_string(),
        }])
        .await;
        let qdrant_server = MockHttpServer::start(vec![]).await;
        let tempdir = tempdir().unwrap();
        write_vocabulary(tempdir.path(), "chunks_hybrid_test", &["hello", "world"]);
        let mut settings = hybrid_bow_settings(tempdir.path().to_str().unwrap());
        if let RetrievalIngest::Hybrid(ingest) = &mut settings.ingest {
            ingest.strategy =
                RetrievalStrategy::BagOfWords(crate::config::BagOfWordsRetrievalStrategy {
                    version: "v2".to_string(),
                    query_weighting: "binary_presence".to_string(),
                });
        }
        let _hf_base = TempEnvVar::set("RAG_RUNTIME_TEST_HF_BASE_URL", tokenizer_server.endpoint());
        let engine = build_hybrid_retriever_with_settings(
            settings,
            embedding_server.endpoint(),
            qdrant_server.endpoint(),
        );

        let error = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello world".to_string(),
                input_token_count: 2,
                ..Default::default()
            })
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "retrieval.invalid_configuration");
    }

    #[tokio::test]
    async fn hybrid_bag_of_words_invalid_query_weighting_returns_invalid_configuration() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let tokenizer_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: TEST_TOKENIZER_JSON.to_string(),
        }])
        .await;
        let qdrant_server = MockHttpServer::start(vec![]).await;
        let tempdir = tempdir().unwrap();
        write_vocabulary(tempdir.path(), "chunks_hybrid_test", &["hello", "world"]);
        let mut settings = hybrid_bow_settings(tempdir.path().to_str().unwrap());
        if let RetrievalIngest::Hybrid(ingest) = &mut settings.ingest {
            ingest.strategy =
                RetrievalStrategy::BagOfWords(crate::config::BagOfWordsRetrievalStrategy {
                    version: "v1".to_string(),
                    query_weighting: "raw_count".to_string(),
                });
        }
        let _hf_base = TempEnvVar::set("RAG_RUNTIME_TEST_HF_BASE_URL", tokenizer_server.endpoint());
        let engine = build_hybrid_retriever_with_settings(
            settings,
            embedding_server.endpoint(),
            qdrant_server.endpoint(),
        );

        let error = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello world".to_string(),
                input_token_count: 2,
                ..Default::default()
            })
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "retrieval.invalid_configuration");
    }

    #[tokio::test]
    async fn hybrid_bm25_request_uses_sparse_branch_with_nonzero_weights() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let tokenizer_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: TEST_TOKENIZER_JSON.to_string(),
        }])
        .await;
        let qdrant_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"result":{"points":[]}}).to_string(),
        }])
        .await;
        let vocab_dir = tempdir().unwrap();
        let term_stats_dir = tempdir().unwrap();
        write_vocabulary(vocab_dir.path(), "chunks_hybrid_test", &["hello", "world"]);
        write_term_stats(
            term_stats_dir.path(),
            "chunks_hybrid_test_bm25",
            "chunks_hybrid_test",
        );
        let _hf_base = TempEnvVar::set("RAG_RUNTIME_TEST_HF_BASE_URL", tokenizer_server.endpoint());
        let engine = build_hybrid_retriever_with_settings(
            hybrid_bm25_settings(
                vocab_dir.path().to_str().unwrap(),
                term_stats_dir.path().to_str().unwrap(),
            ),
            embedding_server.endpoint(),
            qdrant_server.endpoint(),
        );

        let output = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello world".to_string(),
                input_token_count: 2,
                ..Default::default()
            })
            .await
            .unwrap();
        assert!(output.chunks.is_empty());

        let request = qdrant_server.recorded_requests().remove(0);
        assert_eq!(request["query"]["fusion"], "rrf");
        assert_eq!(request["prefetch"][1]["query"]["indices"], json!([0, 1]));
        let values = request["prefetch"][1]["query"]["values"]
            .as_array()
            .unwrap();
        assert_eq!(values.len(), 2);
        assert!((values[0].as_f64().unwrap() as f32 - 1.9635723).abs() < 1e-5);
        assert!((values[1].as_f64().unwrap() as f32 - 1.5176452).abs() < 1e-5);
    }

    #[tokio::test]
    async fn successful_hybrid_retrieval_preserves_fused_hit_order() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let tokenizer_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: TEST_TOKENIZER_JSON.to_string(),
        }])
        .await;
        let second_chunk = json!({
            "schema_version": 1,
            "doc_id": "doc-2",
            "chunk_id": "chunk-2",
            "url": "local://doc",
            "document_title": "Doc",
            "section_title": "Section",
            "section_path": ["Section"],
            "chunk_index": 1,
            "page_start": 2,
            "page_end": 2,
            "tags": ["tag"],
            "content_hash": "sha256:def",
            "chunking_version": "v1",
            "chunk_created_at": "2026-01-01T00:00:00Z",
            "text": "world"
        });
        let qdrant_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"result":{"points":[
                {"score":0.9,"payload":sample_chunk_json()},
                {"score":0.7,"payload":second_chunk}
            ]}})
            .to_string(),
        }])
        .await;
        let tempdir = tempdir().unwrap();
        write_vocabulary(tempdir.path(), "chunks_hybrid_test", &["hello", "world"]);
        let _hf_base = TempEnvVar::set("RAG_RUNTIME_TEST_HF_BASE_URL", tokenizer_server.endpoint());
        let engine = build_hybrid_retriever_with_settings(
            hybrid_bow_settings(tempdir.path().to_str().unwrap()),
            embedding_server.endpoint(),
            qdrant_server.endpoint(),
        );

        let output = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello world".to_string(),
                input_token_count: 2,
                ..Default::default()
            })
            .await
            .unwrap();
        assert_eq!(output.chunks.len(), 2);
        assert_eq!(output.chunks[0].chunk.chunk_id, "chunk-1");
        assert_eq!(output.chunks[1].chunk.chunk_id, "chunk-2");
    }

    #[tokio::test]
    async fn hybrid_missing_vocabulary_file_returns_artifact_load() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let tokenizer_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: TEST_TOKENIZER_JSON.to_string(),
        }])
        .await;
        let qdrant_server = MockHttpServer::start(vec![]).await;
        let tempdir = tempdir().unwrap();
        let _hf_base = TempEnvVar::set("RAG_RUNTIME_TEST_HF_BASE_URL", tokenizer_server.endpoint());
        let engine = build_hybrid_retriever_with_settings(
            hybrid_bow_settings(tempdir.path().to_str().unwrap()),
            embedding_server.endpoint(),
            qdrant_server.endpoint(),
        );

        let error = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello world".to_string(),
                input_token_count: 2,
                ..Default::default()
            })
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "retrieval.artifact_load");
    }

    #[tokio::test]
    async fn hybrid_invalid_vocabulary_file_returns_artifact_validation() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let tokenizer_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: TEST_TOKENIZER_JSON.to_string(),
        }])
        .await;
        let qdrant_server = MockHttpServer::start(vec![]).await;
        let tempdir = tempdir().unwrap();
        std::fs::write(
            tempdir
                .path()
                .join("chunks_hybrid_test__sparse_vocabulary.json"),
            "{\"tokens\":\"bad\"}",
        )
        .unwrap();
        let _hf_base = TempEnvVar::set("RAG_RUNTIME_TEST_HF_BASE_URL", tokenizer_server.endpoint());
        let engine = build_hybrid_retriever_with_settings(
            hybrid_bow_settings(tempdir.path().to_str().unwrap()),
            embedding_server.endpoint(),
            qdrant_server.endpoint(),
        );

        let error = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello world".to_string(),
                input_token_count: 2,
                ..Default::default()
            })
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "retrieval.artifact_validation");
    }

    #[tokio::test]
    async fn hybrid_missing_term_stats_file_returns_artifact_load() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let tokenizer_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: TEST_TOKENIZER_JSON.to_string(),
        }])
        .await;
        let qdrant_server = MockHttpServer::start(vec![]).await;
        let vocab_dir = tempdir().unwrap();
        let term_stats_dir = tempdir().unwrap();
        write_vocabulary(vocab_dir.path(), "chunks_hybrid_test", &["hello", "world"]);
        let _hf_base = TempEnvVar::set("RAG_RUNTIME_TEST_HF_BASE_URL", tokenizer_server.endpoint());
        let engine = build_hybrid_retriever_with_settings(
            hybrid_bm25_settings(
                vocab_dir.path().to_str().unwrap(),
                term_stats_dir.path().to_str().unwrap(),
            ),
            embedding_server.endpoint(),
            qdrant_server.endpoint(),
        );

        let error = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello world".to_string(),
                input_token_count: 2,
                ..Default::default()
            })
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "retrieval.artifact_load");
    }

    #[tokio::test]
    async fn hybrid_invalid_term_stats_file_returns_artifact_validation() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let tokenizer_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: TEST_TOKENIZER_JSON.to_string(),
        }])
        .await;
        let qdrant_server = MockHttpServer::start(vec![]).await;
        let vocab_dir = tempdir().unwrap();
        let term_stats_dir = tempdir().unwrap();
        write_vocabulary(vocab_dir.path(), "chunks_hybrid_test", &["hello", "world"]);
        std::fs::write(
            term_stats_dir
                .path()
                .join("chunks_hybrid_test_bm25__term_stats.json"),
            "{\"document_count\":0}",
        )
        .unwrap();
        let _hf_base = TempEnvVar::set("RAG_RUNTIME_TEST_HF_BASE_URL", tokenizer_server.endpoint());
        let engine = build_hybrid_retriever_with_settings(
            hybrid_bm25_settings(
                vocab_dir.path().to_str().unwrap(),
                term_stats_dir.path().to_str().unwrap(),
            ),
            embedding_server.endpoint(),
            qdrant_server.endpoint(),
        );

        let error = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello world".to_string(),
                input_token_count: 2,
                ..Default::default()
            })
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "retrieval.artifact_validation");
    }

    #[tokio::test]
    async fn hybrid_term_stats_identity_mismatch_returns_artifact_validation() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let tokenizer_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: TEST_TOKENIZER_JSON.to_string(),
        }])
        .await;
        let qdrant_server = MockHttpServer::start(vec![]).await;
        let vocab_dir = tempdir().unwrap();
        let term_stats_dir = tempdir().unwrap();
        write_vocabulary(vocab_dir.path(), "chunks_hybrid_test", &["hello", "world"]);
        write_term_stats_with_identity(
            term_stats_dir.path(),
            "chunks_hybrid_test_bm25",
            "chunks_hybrid_test",
            "other_collection",
        );
        let _hf_base = TempEnvVar::set("RAG_RUNTIME_TEST_HF_BASE_URL", tokenizer_server.endpoint());
        let engine = build_hybrid_retriever_with_settings(
            hybrid_bm25_settings(
                vocab_dir.path().to_str().unwrap(),
                term_stats_dir.path().to_str().unwrap(),
            ),
            embedding_server.endpoint(),
            qdrant_server.endpoint(),
        );

        let error = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello world".to_string(),
                input_token_count: 2,
                ..Default::default()
            })
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "retrieval.artifact_validation");
    }

    #[tokio::test]
    async fn hybrid_missing_result_points_returns_qdrant_validation_error() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let tokenizer_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: TEST_TOKENIZER_JSON.to_string(),
        }])
        .await;
        let qdrant_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"result":{}}).to_string(),
        }])
        .await;
        let tempdir = tempdir().unwrap();
        write_vocabulary(tempdir.path(), "chunks_hybrid_test", &["hello", "world"]);
        let _hf_base = TempEnvVar::set("RAG_RUNTIME_TEST_HF_BASE_URL", tokenizer_server.endpoint());
        let engine = build_hybrid_retriever_with_settings(
            hybrid_bow_settings(tempdir.path().to_str().unwrap()),
            embedding_server.endpoint(),
            qdrant_server.endpoint(),
        );

        let error = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello world".to_string(),
                input_token_count: 2,
                ..Default::default()
            })
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "retrieval.qdrant_response_validation");
    }

    #[tokio::test]
    async fn hybrid_invalid_result_points_shape_returns_qdrant_validation_error() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let tokenizer_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: TEST_TOKENIZER_JSON.to_string(),
        }])
        .await;
        let qdrant_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"result":{"points":{"bad":true}}}).to_string(),
        }])
        .await;
        let tempdir = tempdir().unwrap();
        write_vocabulary(tempdir.path(), "chunks_hybrid_test", &["hello", "world"]);
        let _hf_base = TempEnvVar::set("RAG_RUNTIME_TEST_HF_BASE_URL", tokenizer_server.endpoint());
        let engine = build_hybrid_retriever_with_settings(
            hybrid_bow_settings(tempdir.path().to_str().unwrap()),
            embedding_server.endpoint(),
            qdrant_server.endpoint(),
        );

        let error = engine
            .retrieve(&ValidatedUserRequest {
                query: "hello world".to_string(),
                input_token_count: 2,
                ..Default::default()
            })
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "retrieval.qdrant_response_validation");
    }

    // --- fetch_chunking_strategy unit tests ---

    #[tokio::test]
    async fn fetch_chunking_strategy_returns_value_from_collection_metadata() {
        let qdrant_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({
                "result": {
                    "config": {
                        "metadata": {
                            "chunking_strategy": "fixed"
                        }
                    }
                }
            })
            .to_string(),
        }])
        .await;
        let runtime = RetrievalRuntime::new();
        let strategy = runtime
            .fetch_chunking_strategy(&qdrant_server.endpoint(), "my_collection")
            .await
            .unwrap();
        assert_eq!(strategy, "fixed");
        assert_eq!(
            qdrant_server.recorded_paths(),
            vec!["/collections/my_collection".to_string()]
        );
    }

    #[tokio::test]
    async fn fetch_chunking_strategy_non_2xx_returns_qdrant_request_error() {
        let qdrant_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::NOT_FOUND,
            body: "not found".to_string(),
        }])
        .await;
        let runtime = RetrievalRuntime::new();
        let error = runtime
            .fetch_chunking_strategy(&qdrant_server.endpoint(), "my_collection")
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "retrieval.qdrant_request");
    }

    #[tokio::test]
    async fn fetch_chunking_strategy_missing_field_returns_qdrant_response_validation_error() {
        let qdrant_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"result": {"config": {}}}).to_string(),
        }])
        .await;
        let runtime = RetrievalRuntime::new();
        let error = runtime
            .fetch_chunking_strategy(&qdrant_server.endpoint(), "my_collection")
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "retrieval.qdrant_response_validation");
    }

    // --- Dense retriever chunking_strategy propagation tests ---

    #[tokio::test]
    async fn dense_retrieve_fetches_chunking_strategy_and_populates_output() {
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings": [[0.1, 0.2, 0.3]]}).to_string(),
        }])
        .await;
        let qdrant_server = MockHttpServer::start(vec![
            MockHttpResponse {
                status: StatusCode::OK,
                body: json!({
                    "result": {
                        "config": {
                            "metadata": {
                                "chunking_strategy": "fixed"
                            }
                        }
                    }
                })
                .to_string(),
            },
            MockHttpResponse {
                status: StatusCode::OK,
                body: json!({"result": {"points": []}}).to_string(),
            },
        ])
        .await;
        let mut settings = test_settings().retrieval;
        settings.qdrant_url = qdrant_server.endpoint();
        let retriever = DenseRetriever::new()
            .with_base_urls(embedding_server.endpoint(), qdrant_server.endpoint());
        let output = retriever
            .retrieve(
                &ValidatedUserRequest {
                    query: "hello".to_string(),
                    input_token_count: 1,
                    ..Default::default()
                },
                None,
                &settings,
            )
            .await
            .unwrap();
        assert_eq!(output.chunking_strategy, "fixed");
    }

    #[tokio::test]
    async fn dense_retrieve_caches_chunking_strategy_and_does_not_repeat_metadata_fetch() {
        let embedding_server = MockHttpServer::start(vec![
            MockHttpResponse {
                status: StatusCode::OK,
                body: json!({"embeddings": [[0.1, 0.2, 0.3]]}).to_string(),
            },
            MockHttpResponse {
                status: StatusCode::OK,
                body: json!({"embeddings": [[0.1, 0.2, 0.3]]}).to_string(),
            },
        ])
        .await;
        let qdrant_server = MockHttpServer::start(vec![
            MockHttpResponse {
                status: StatusCode::OK,
                body: json!({
                    "result": {
                        "config": {
                            "metadata": {
                                "chunking_strategy": "structural"
                            }
                        }
                    }
                })
                .to_string(),
            },
            MockHttpResponse {
                status: StatusCode::OK,
                body: json!({"result": {"points": []}}).to_string(),
            },
            MockHttpResponse {
                status: StatusCode::OK,
                body: json!({"result": {"points": []}}).to_string(),
            },
        ])
        .await;
        let mut settings = test_settings().retrieval;
        settings.qdrant_url = qdrant_server.endpoint();
        let retriever = DenseRetriever::new()
            .with_base_urls(embedding_server.endpoint(), qdrant_server.endpoint());
        let req = ValidatedUserRequest {
            query: "hello".to_string(),
            input_token_count: 1,
            ..Default::default()
        };
        retriever.retrieve(&req, None, &settings).await.unwrap();
        retriever.retrieve(&req, None, &settings).await.unwrap();
        let paths = qdrant_server.recorded_paths();
        let metadata_calls = paths.iter().filter(|p| !p.contains("/points")).count();
        assert_eq!(
            metadata_calls, 1,
            "metadata endpoint called more than once: {paths:?}"
        );
        assert_eq!(
            paths.len(),
            3,
            "expected 3 total qdrant calls (1 metadata + 2 search), got {}: {paths:?}",
            paths.len()
        );
    }

    // --- Hybrid retriever chunking_strategy propagation test ---

    #[tokio::test]
    async fn hybrid_retrieve_fetches_chunking_strategy_and_populates_output() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let embedding_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings": [[0.1, 0.2, 0.3]]}).to_string(),
        }])
        .await;
        let tokenizer_server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: TEST_TOKENIZER_JSON.to_string(),
        }])
        .await;
        let qdrant_server = MockHttpServer::start(vec![
            MockHttpResponse {
                status: StatusCode::OK,
                body: json!({
                    "result": {
                        "config": {
                            "metadata": {
                                "chunking_strategy": "structural"
                            }
                        }
                    }
                })
                .to_string(),
            },
            MockHttpResponse {
                status: StatusCode::OK,
                body: json!({"result": {"points": []}}).to_string(),
            },
        ])
        .await;
        let tempdir = tempdir().unwrap();
        write_vocabulary(tempdir.path(), "chunks_hybrid_test", &["hello", "world"]);
        let _hf_base = TempEnvVar::set("RAG_RUNTIME_TEST_HF_BASE_URL", tokenizer_server.endpoint());
        let mut settings = hybrid_bow_settings(tempdir.path().to_str().unwrap());
        settings.qdrant_url = qdrant_server.endpoint();
        let retriever = HybridRetriever::new()
            .with_base_urls(embedding_server.endpoint(), qdrant_server.endpoint());
        let output = retriever
            .retrieve(
                &ValidatedUserRequest {
                    query: "hello world".to_string(),
                    input_token_count: 2,
                    ..Default::default()
                },
                None,
                &settings,
            )
            .await
            .unwrap();
        assert_eq!(output.chunking_strategy, "structural");
    }
}

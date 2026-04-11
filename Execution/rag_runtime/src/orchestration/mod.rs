use std::collections::HashMap;
use std::path::Path;
use std::time::Instant;

use chrono::Utc;
use opentelemetry::trace::TraceContextExt;
use serde::Deserialize;
use tracing::{field, info_span};
use tracing_opentelemetry::OpenTelemetrySpanExt;
use uuid::Uuid;

use crate::config::{RetrievalKind as SettingsRetrievalKind, Settings};
use crate::errors::{OrchestrationError, RagRuntimeError};
use crate::generation::GenerationEngine;
use crate::generation::{PROMPT_TEMPLATE_ID, PROMPT_TEMPLATE_VERSION};
use crate::input_validation::InputValidationEngine;
use crate::models::{
    CrossEncoderConfig, GenerationConfig, GenerationRequest, GoldenRetrievalTargets,
    GradedChunkRelevance, HeuristicWeights, RequestCapture, RerankedRetrievalOutput,
    RerankerConfig, RerankerKind, RetrievalResultItem, RetrievedChunk, RetrieverConfig,
    RetrieverKind, UserRequest, UserResponse,
};
use crate::observability::{
    StatusLabel, mark_span_ok, record_request_close, record_request_retrieval_quality_aggregates,
    record_retrieval_empty,
};
use crate::request_capture_store::RequestCaptureStore;
use crate::reranking::{
    CrossEncoderReranker, HeuristicReranker, PassThroughReranker, Reranker,
    build_reranking_transport,
};
use crate::retrieval::{DenseRetriever, HybridRetriever, Retriever};

pub struct OrchestrationEngine {
    input_validation: Option<InputValidationEngine>,
    retrieval: Option<Box<dyn Retriever + Send + Sync>>,
    generation: Option<GenerationEngine>,
    reranker: Box<dyn Reranker + Send + Sync>,
    request_capture_store: RequestCaptureStoreMode,
    always_fail_for_tests: bool,
    golden_lookup: Option<HashMap<String, GoldenRetrievalTargets>>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum RequestCaptureStoreMode {
    Real,
    #[cfg(test)]
    Noop,
}

impl OrchestrationEngine {
    pub fn new(
        input_validation: InputValidationEngine,
        generation: GenerationEngine,
        settings: &Settings,
    ) -> Result<Self, RagRuntimeError> {
        Ok(Self {
            input_validation: Some(input_validation),
            retrieval: Some(build_retriever(&settings.retrieval)?),
            generation: Some(generation),
            reranker: build_reranker(&settings.reranking)?,
            request_capture_store: RequestCaptureStoreMode::Real,
            always_fail_for_tests: false,
            golden_lookup: None,
        })
    }

    pub fn set_golden_lookup(&mut self, lookup: HashMap<String, GoldenRetrievalTargets>) {
        self.golden_lookup = Some(lookup);
    }

    pub async fn handle_request(
        &self,
        settings: &Settings,
        runtime_run_id: &str,
        request: UserRequest,
    ) -> Result<UserResponse, RagRuntimeError> {
        if self.always_fail_for_tests {
            return Err(OrchestrationError::EmptyRetrievalOutput.into());
        }

        let input_validation = self.input_validation.as_ref().expect("input validation");
        let retrieval = self.retrieval.as_ref().expect("retrieval");
        let generation = self.generation.as_ref().expect("generation");

        let request_id = Uuid::new_v4();
        let received_at = Utc::now();
        let root_span = info_span!(
            "rag.request",
            request_id = %request_id,
            "request.id" = %request_id,
            "span.module" = "orchestration",
            "span.stage" = "request",
            status = field::Empty,
            "error.type" = field::Empty,
            "error.message" = field::Empty,
            "openinference.span.kind" = "CHAIN",
            "input.value" = field::Empty,
            "input.mime_type" = "text/plain",
            "output.value" = field::Empty,
            "output.mime_type" = "text/plain",
            "app.version" = env!("CARGO_PKG_VERSION"),
            "rag.pipeline.name" = "rag_runtime",
            "rag.pipeline.version" = %settings.pipeline.config_version,
            "prompt_template.id" = PROMPT_TEMPLATE_ID,
            "prompt_template.version" = PROMPT_TEMPLATE_VERSION,
            "corpus.version" = %settings.retrieval.corpus_version(),
            "token_length_curve.retrieval" = field::Empty,
            "token_length_curve.reranking" = field::Empty,
            summary_retrieval_context_loss_soft = field::Empty,
            summary_retrieval_context_loss_strict = field::Empty,
            summary_first_relevant_rank_retrieval_soft = field::Empty,
            summary_first_relevant_rank_retrieval_strict = field::Empty,
            summary_first_relevant_rank_context_soft = field::Empty,
            summary_first_relevant_rank_context_strict = field::Empty,
            summary_num_relevant_in_retrieval_topk_soft = field::Empty,
            summary_num_relevant_in_retrieval_topk_strict = field::Empty,
            summary_num_relevant_in_context_topk_soft = field::Empty,
            summary_num_relevant_in_context_topk_strict = field::Empty,
        );
        let _root_guard = root_span.enter();
        let started = Instant::now();
        let result: Result<UserResponse, RagRuntimeError> = async {
            let raw_query = request.query.clone();
            let golden_targets = self.golden_lookup.as_ref().and_then(|m| m.get(&raw_query));
            let validated = input_validation.validate(request).await?;
            root_span.record("input.value", field::display(&validated.query));
            let retrieval_output = retrieval
                .retrieve(&validated, golden_targets, &settings.retrieval)
                .await?;
            if retrieval_output.chunks.is_empty() {
                record_retrieval_empty();
                return Err(OrchestrationError::EmptyRetrievalOutput.into());
            }
            let retrieval_prompt_token_curve = generation
                .prefix_prompt_token_counts(&validated.query, &retrieval_output.chunks)?;
            let retrieval_stage_metrics = retrieval_output.metrics.clone();
            let retrieval_chunking_strategy = retrieval_output.chunking_strategy.clone();
            let reranked_output = self
                .reranker
                .rerank(
                    &validated,
                    golden_targets,
                    settings.reranking.final_k,
                    retrieval_output,
                )
                .await?;
            if reranked_output.chunks.is_empty() {
                return Err(OrchestrationError::EmptyRerankedOutput.into());
            }
            let reranking_stage_metrics = reranked_output.metrics.clone();
            record_request_retrieval_quality_aggregates(
                &root_span,
                retrieval_stage_metrics.as_ref(),
                reranking_stage_metrics.as_ref(),
            );
            if retrieval_stage_metrics.is_some() || reranking_stage_metrics.is_some() {
                let ret = retrieval_stage_metrics.as_ref();
                let rer = reranking_stage_metrics.as_ref();
                tracing::info!(
                    summary_retrieval_context_loss_soft = ret
                        .zip(rer)
                        .map(|(r, re)| (r.recall_soft - re.recall_soft) as f64),
                    summary_retrieval_context_loss_strict = ret
                        .zip(rer)
                        .map(|(r, re)| (r.recall_strict - re.recall_strict) as f64),
                    summary_first_relevant_rank_retrieval_soft =
                        field::debug(ret.and_then(|r| r.first_relevant_rank_soft)),
                    summary_first_relevant_rank_retrieval_strict =
                        field::debug(ret.and_then(|r| r.first_relevant_rank_strict)),
                    summary_first_relevant_rank_context_soft =
                        field::debug(rer.and_then(|r| r.first_relevant_rank_soft)),
                    summary_first_relevant_rank_context_strict =
                        field::debug(rer.and_then(|r| r.first_relevant_rank_strict)),
                    summary_num_relevant_in_retrieval_topk_soft =
                        ret.map(|r| r.num_relevant_soft as i64),
                    summary_num_relevant_in_retrieval_topk_strict =
                        ret.map(|r| r.num_relevant_strict as i64),
                    summary_num_relevant_in_context_topk_soft =
                        rer.map(|r| r.num_relevant_soft as i64),
                    summary_num_relevant_in_context_topk_strict =
                        rer.map(|r| r.num_relevant_strict as i64),
                    "retrieval_quality_metrics"
                );
            }
            let reranked_all_generation_chunks =
                build_reranked_generation_chunks(&reranked_output, reranked_output.chunks.len());
            let reranked_prompt_token_curve = generation
                .prefix_prompt_token_counts(&validated.query, &reranked_all_generation_chunks)?;
            root_span.record(
                "token_length_curve.retrieval",
                field::display(format_usize_list(&retrieval_prompt_token_curve)),
            );
            root_span.record(
                "token_length_curve.reranking",
                field::display(format_usize_list(&reranked_prompt_token_curve)),
            );
            let final_k = settings.reranking.final_k.min(reranked_output.chunks.len());
            let generation_chunks = build_reranked_generation_chunks(&reranked_output, final_k);
            if generation_chunks.is_empty() {
                return Err(OrchestrationError::EmptyRerankedOutput.into());
            }
            let retrieval_results = build_retrieval_result_items(&reranked_output, final_k);
            let generation_request = GenerationRequest {
                query: validated.query.clone(),
                chunks: generation_chunks,
            };
            let response = generation.generate(generation_request).await?;
            root_span.record("output.value", field::display(&response.answer));
            let capture = RequestCapture {
                runtime_run_id: runtime_run_id.to_string(),
                request_id: request_id.to_string(),
                trace_id: active_trace_id_or_na(),
                received_at,
                raw_query,
                normalized_query: validated.query,
                input_token_count: validated.input_token_count,
                pipeline_config_version: settings.pipeline.config_version.clone(),
                corpus_version: settings.retrieval.corpus_version().to_string(),
                retriever_version: settings.retrieval.retriever_version.clone(),
                retriever_kind: capture_retriever_kind(&settings.retrieval.kind),
                retriever_config: capture_retriever_config(
                    &settings.retrieval,
                    &retrieval_chunking_strategy,
                ),
                embedding_model: settings.retrieval.embedding_model_name().to_string(),
                prompt_template_id: PROMPT_TEMPLATE_ID.to_string(),
                prompt_template_version: PROMPT_TEMPLATE_VERSION.to_string(),
                generation_model: settings.generation.transport_model_name().to_string(),
                generation_config: capture_generation_config(&settings.generation),
                reranker_kind: capture_reranker_kind(&settings.reranking.reranker),
                reranker_config: capture_reranker_config(&settings.reranking, &reranked_output),
                top_k_requested: settings.retrieval.top_k,
                retrieval_results,
                final_answer: response.answer.clone(),
                prompt_tokens: response.prompt_tokens,
                completion_tokens: response.completion_tokens,
                total_tokens: response.total_tokens,
                retrieval_stage_metrics,
                reranking_stage_metrics,
            };
            match self.request_capture_store {
                RequestCaptureStoreMode::Real => {
                    if let Err(error) =
                        RequestCaptureStore::store(capture, &settings.request_capture).await
                    {
                        tracing::warn!(
                            error_type = error.error_type(),
                            error_message = %error,
                            "request_capture_persistence_failed"
                        );
                    }
                }
                #[cfg(test)]
                RequestCaptureStoreMode::Noop => {}
            }
            mark_span_ok();
            Ok(UserResponse {
                answer: response.answer,
            })
        }
        .await;
        match &result {
            Ok(_) => {
                root_span.record("status", "ok");
            }
            Err(error) => {
                root_span.record("status", "error");
                root_span.record("error.type", error.error_type());
                root_span.record("error.message", field::display(error.to_string()));
            }
        }
        record_request_close(
            started.elapsed().as_secs_f64() * 1000.0,
            if result.is_ok() {
                StatusLabel::Ok
            } else {
                StatusLabel::Error
            },
        );
        result
    }

    #[cfg(test)]
    pub fn failing_for_tests() -> Self {
        Self {
            input_validation: None,
            retrieval: None,
            generation: None,
            reranker: Box::new(PassThroughReranker::new()),
            request_capture_store: RequestCaptureStoreMode::Noop,
            always_fail_for_tests: true,
            golden_lookup: None,
        }
    }

    #[cfg(test)]
    pub fn from_parts(
        input_validation: InputValidationEngine,
        generation: GenerationEngine,
        settings: &Settings,
    ) -> Result<Self, RagRuntimeError> {
        Ok(Self {
            input_validation: Some(input_validation),
            retrieval: Some(build_retriever_for_tests(&settings.retrieval)),
            generation: Some(generation),
            reranker: build_reranker(&settings.reranking)?,
            request_capture_store: RequestCaptureStoreMode::Noop,
            always_fail_for_tests: false,
            golden_lookup: None,
        })
    }
}

fn build_retriever(
    retrieval: &crate::config::RetrievalSettings,
) -> Result<Box<dyn Retriever + Send + Sync>, RagRuntimeError> {
    match &retrieval.ingest {
        crate::config::RetrievalIngest::Dense(_) => Ok(Box::new(DenseRetriever::new())),
        crate::config::RetrievalIngest::Hybrid(_) => Ok(Box::new(HybridRetriever::new())),
    }
}

#[cfg(test)]
fn build_retriever_for_tests(
    retrieval: &crate::config::RetrievalSettings,
) -> Box<dyn Retriever + Send + Sync> {
    match &retrieval.ingest {
        crate::config::RetrievalIngest::Dense(_) => Box::new(DenseRetriever::new()),
        crate::config::RetrievalIngest::Hybrid(_) => Box::new(HybridRetriever::new()),
    }
}

fn build_reranked_generation_chunks(
    reranked_output: &RerankedRetrievalOutput,
    final_k: usize,
) -> Vec<RetrievedChunk> {
    reranked_output
        .chunks
        .iter()
        .take(final_k)
        .map(|retrieved| RetrievedChunk {
            chunk: retrieved.chunk.clone(),
            score: retrieved.rerank_score,
        })
        .collect()
}

fn build_retrieval_result_items(
    reranked_output: &RerankedRetrievalOutput,
    final_k: usize,
) -> Vec<RetrievalResultItem> {
    reranked_output
        .chunks
        .iter()
        .enumerate()
        .map(|(index, retrieved)| RetrievalResultItem {
            chunk_id: retrieved.chunk.chunk_id.clone(),
            document_id: retrieved.chunk.doc_id.clone(),
            locator: page_locator(retrieved.chunk.page_start, retrieved.chunk.page_end),
            retrieval_score: retrieved.retrieval_score,
            rerank_score: retrieved.rerank_score,
            selected_for_generation: index < final_k,
        })
        .collect()
}

fn build_reranker(
    reranking: &crate::config::RerankingSettings,
) -> Result<Box<dyn Reranker + Send + Sync>, RagRuntimeError> {
    match &reranking.reranker {
        crate::config::RerankerSettings::PassThrough => Ok(Box::new(PassThroughReranker::new())),
        crate::config::RerankerSettings::Heuristic(settings) => {
            Ok(Box::new(HeuristicReranker::new(settings.weights.clone())?))
        }
        crate::config::RerankerSettings::CrossEncoder(settings) => {
            let transport = build_reranking_transport(&settings.transport)?;
            Ok(Box::new(CrossEncoderReranker::new(
                settings.clone(),
                transport,
            )?))
        }
    }
}

fn capture_reranker_kind(reranker: &crate::config::RerankerSettings) -> RerankerKind {
    match reranker {
        crate::config::RerankerSettings::PassThrough => RerankerKind::PassThrough,
        crate::config::RerankerSettings::Heuristic(_) => RerankerKind::Heuristic,
        crate::config::RerankerSettings::CrossEncoder(_) => RerankerKind::CrossEncoder,
    }
}

fn capture_retriever_kind(kind: &SettingsRetrievalKind) -> RetrieverKind {
    match kind {
        SettingsRetrievalKind::Dense => RetrieverKind::Dense,
        SettingsRetrievalKind::Hybrid => RetrieverKind::Hybrid,
    }
}

fn capture_retriever_config(
    settings: &crate::config::RetrievalSettings,
    chunking_strategy: &str,
) -> RetrieverConfig {
    match &settings.ingest {
        crate::config::RetrievalIngest::Dense(ingest) => RetrieverConfig::Dense {
            embedding_model_name: ingest.embedding_model_name.clone(),
            embedding_endpoint: settings.ollama_url.clone(),
            embedding_dimension: ingest.embedding_dimension,
            qdrant_collection_name: ingest.qdrant_collection_name.clone(),
            qdrant_vector_name: ingest.qdrant_vector_name.clone(),
            score_threshold: settings.score_threshold,
            corpus_version: ingest.corpus_version.clone(),
            chunking_strategy: chunking_strategy.to_string(),
        },
        crate::config::RetrievalIngest::Hybrid(ingest) => RetrieverConfig::Hybrid {
            embedding_model_name: ingest.embedding_model_name.clone(),
            embedding_endpoint: settings.ollama_url.clone(),
            embedding_dimension: ingest.embedding_dimension,
            qdrant_collection_name: ingest.qdrant_collection_name.clone(),
            dense_vector_name: ingest.dense_vector_name.clone(),
            sparse_vector_name: ingest.sparse_vector_name.clone(),
            score_threshold: settings.score_threshold,
            corpus_version: ingest.corpus_version.clone(),
            tokenizer_library: ingest.tokenizer_library.clone(),
            tokenizer_source: ingest.tokenizer_source.clone(),
            tokenizer_revision: ingest.tokenizer_revision.clone(),
            preprocessing_kind: ingest.preprocessing_kind.clone(),
            lowercase: ingest.lowercase,
            min_token_length: ingest.min_token_length,
            vocabulary_path: ingest.vocabulary_path.clone(),
            chunking_strategy: chunking_strategy.to_string(),
            strategy: match &ingest.strategy {
                crate::config::RetrievalStrategy::BagOfWords(strategy) => {
                    crate::models::RetrieverStrategyConfig::BagOfWords {
                        version: strategy.version.clone(),
                        query_weighting: strategy.query_weighting.clone(),
                    }
                }
                crate::config::RetrievalStrategy::Bm25Like(strategy) => {
                    crate::models::RetrieverStrategyConfig::Bm25Like {
                        version: strategy.version.clone(),
                        query_weighting: strategy.query_weighting.clone(),
                        k1: strategy.k1,
                        b: strategy.b,
                        idf_smoothing: strategy.idf_smoothing.clone(),
                        term_stats_path: strategy.term_stats_path.clone(),
                    }
                }
            },
        },
    }
}

fn capture_reranker_config(
    settings: &crate::config::RerankingSettings,
    reranked_output: &RerankedRetrievalOutput,
) -> Option<RerankerConfig> {
    match &settings.reranker {
        crate::config::RerankerSettings::PassThrough => None,
        crate::config::RerankerSettings::Heuristic(heuristic) => Some(RerankerConfig::Heuristic {
            final_k: settings.final_k,
            weights: HeuristicWeights {
                retrieval_score: heuristic.weights.retrieval_score,
                query_term_coverage: heuristic.weights.query_term_coverage,
                phrase_match_bonus: heuristic.weights.phrase_match_bonus,
                title_section_match_bonus: heuristic.weights.title_section_match_bonus,
            },
        }),
        crate::config::RerankerSettings::CrossEncoder(cross_encoder) => {
            let cross_encoder = match &cross_encoder.transport {
                crate::config::CrossEncoderTransportSettings::MixedbreadAi(settings) => {
                    CrossEncoderConfig {
                        model_name: settings.model_name.clone(),
                        url: settings.url.clone(),
                        total_tokens: reranked_output.total_tokens,
                        cost_per_million_tokens: settings.cost_per_million_tokens,
                    }
                }
                crate::config::CrossEncoderTransportSettings::VoyageAi(settings) => {
                    CrossEncoderConfig {
                        model_name: settings.model_name.clone(),
                        url: settings.url.clone(),
                        total_tokens: reranked_output.total_tokens,
                        cost_per_million_tokens: settings.cost_per_million_tokens,
                    }
                }
            };
            Some(RerankerConfig::CrossEncoder {
                final_k: settings.final_k,
                cross_encoder,
            })
        }
    }
}

fn capture_generation_config(settings: &crate::config::GenerationSettings) -> GenerationConfig {
    let (input_cost_per_million_tokens, output_cost_per_million_tokens) =
        generation_transport_costs(&settings.transport);
    GenerationConfig {
        model: settings.transport_model_name().to_string(),
        model_endpoint: settings.transport_url().to_string(),
        temperature: settings.temperature,
        max_context_chunks: settings.max_context_chunks,
        input_cost_per_million_tokens,
        output_cost_per_million_tokens,
    }
}

fn generation_transport_costs(transport: &crate::config::TransportSettings) -> (f64, f64) {
    match transport {
        crate::config::TransportSettings::Ollama(settings) => (
            settings.input_cost_per_million_tokens,
            settings.output_cost_per_million_tokens,
        ),
        crate::config::TransportSettings::OpenAi(settings) => (
            settings.input_cost_per_million_tokens,
            settings.output_cost_per_million_tokens,
        ),
    }
}

fn page_locator(page_start: i64, page_end: i64) -> String {
    if page_start == page_end {
        format!("page:{page_start}")
    } else {
        format!("pages:{page_start}-{page_end}")
    }
}

fn format_usize_list(values: &[usize]) -> String {
    let joined = values
        .iter()
        .map(|value| value.to_string())
        .collect::<Vec<_>>()
        .join(", ");
    format!("[{joined}]")
}

// ── Golden retrieval companion loading ──────────────────────────────────────

#[derive(Debug, Deserialize)]
struct GoldenCompanionFile {
    #[allow(dead_code)]
    version: String,
    #[allow(dead_code)]
    scenario: String,
    questions: Vec<GoldenCompanionQuestion>,
}

#[derive(Debug, Deserialize)]
struct GoldenCompanionQuestion {
    #[allow(dead_code)]
    question_id: String,
    question: String,
    soft_positive_chunk_ids: Vec<String>,
    strict_positive_chunk_ids: Vec<String>,
    graded_relevance: Vec<GoldenCompanionGrade>,
}

#[derive(Debug, Deserialize)]
struct GoldenCompanionGrade {
    chunk_id: String,
    score: f32,
}

/// Load and parse a golden retrieval companion file, then validate that every
/// non-empty question in `batch_questions` has a matching entry. Returns a
/// lookup map keyed by exact question text.
pub async fn load_golden_companion(
    path: impl AsRef<Path>,
    batch_questions: &[String],
) -> Result<HashMap<String, GoldenRetrievalTargets>, RagRuntimeError> {
    let raw = tokio::fs::read_to_string(path.as_ref())
        .await
        .map_err(|error| {
            RagRuntimeError::startup(format!(
                "failed to read golden retrieval companion file: {error}"
            ))
        })?;

    let companion: GoldenCompanionFile = serde_json::from_str(&raw).map_err(|error| {
        RagRuntimeError::startup(format!(
            "failed to parse golden retrieval companion file: {error}"
        ))
    })?;

    let mut lookup: HashMap<String, GoldenRetrievalTargets> =
        HashMap::with_capacity(companion.questions.len());

    for q in companion.questions {
        let soft = q
            .soft_positive_chunk_ids
            .iter()
            .map(|s| {
                Uuid::parse_str(s).map_err(|_| {
                    RagRuntimeError::startup(format!(
                        "golden companion soft_positive_chunk_id is not a valid UUID: {s:?}"
                    ))
                })
            })
            .collect::<Result<Vec<Uuid>, _>>()?;

        let strict = q
            .strict_positive_chunk_ids
            .iter()
            .map(|s| {
                Uuid::parse_str(s).map_err(|_| {
                    RagRuntimeError::startup(format!(
                        "golden companion strict_positive_chunk_id is not a valid UUID: {s:?}"
                    ))
                })
            })
            .collect::<Result<Vec<Uuid>, _>>()?;

        let graded = q
            .graded_relevance
            .iter()
            .map(|g| {
                Uuid::parse_str(&g.chunk_id)
                    .map(|uuid| GradedChunkRelevance {
                        chunk_id: uuid,
                        score: g.score,
                    })
                    .map_err(|_| {
                        RagRuntimeError::startup(format!(
                            "golden companion graded_relevance chunk_id is not a valid UUID: {:?}",
                            g.chunk_id
                        ))
                    })
            })
            .collect::<Result<Vec<GradedChunkRelevance>, _>>()?;

        lookup.insert(
            q.question,
            GoldenRetrievalTargets {
                soft_positive_chunk_ids: soft,
                strict_positive_chunk_ids: strict,
                graded_relevance: graded,
            },
        );
    }

    // Validate that every non-empty batch question has a matching companion entry.
    for question in batch_questions {
        let trimmed = question.trim();
        if trimmed.is_empty() {
            continue;
        }
        if !lookup.contains_key(trimmed) {
            return Err(
                OrchestrationError::BatchQuestionMissingFromGoldenCompanion {
                    question: trimmed.to_string(),
                }
                .into(),
            );
        }
    }

    Ok(lookup)
}

fn active_trace_id_or_na() -> String {
    let context = tracing::Span::current().context();
    let span = context.span();
    let span_context = span.span_context();
    if span_context.is_valid() {
        span_context.trace_id().to_string()
    } else {
        "NA".to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::http::StatusCode;
    use serde_json::json;
    use tempfile::tempdir;

    use crate::models::UserRequest;
    use crate::test_support;
    use crate::test_support::{
        MockHttpResponse, MockHttpServer, TempEnvVar, env_lock, test_settings,
    };

    const TEST_TOKENIZER_JSON: &str = r#"{
      "version":"1.0",
      "truncation":null,
      "padding":null,
      "added_tokens":[],
      "normalizer":null,
      "pre_tokenizer":{"type":"Whitespace"},
      "post_processor":null,
      "decoder":null,
      "model":{"type":"WordLevel","vocab":{"[UNK]":0,"hello":1,"world":2},"unk_token":"[UNK]"}
    }"#;

    fn sample_qdrant_payload() -> serde_json::Value {
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
            "text": "chunk text"
        })
    }

    fn collection_metadata_response() -> MockHttpResponse {
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
        }
    }

    fn write_vocabulary(dir: &std::path::Path, collection_name: &str, tokens: &[&str]) {
        let token_entries = tokens
            .iter()
            .enumerate()
            .map(|(index, token)| json!({"token": token, "token_id": index}))
            .collect::<Vec<_>>();
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
                "tokenizer": {
                    "library": "tokenizers",
                    "source": "test/sparse"
                },
                "created_at": "2026-04-03T00:00:00Z",
                "tokens": token_entries
            })
            .to_string(),
        )
        .unwrap();
    }

    fn hybrid_test_settings(vocabulary_dir: &str) -> crate::config::Settings {
        let mut settings = test_settings();
        settings.retrieval.kind = crate::config::RetrievalKind::Hybrid;
        settings.retrieval.ingest =
            crate::config::RetrievalIngest::Hybrid(crate::config::HybridRetrievalIngest {
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
                strategy: crate::config::RetrievalStrategy::BagOfWords(
                    crate::config::BagOfWordsRetrievalStrategy {
                        version: "v1".to_string(),
                        query_weighting: "binary_presence".to_string(),
                    },
                ),
            });
        settings
    }

    fn set_generation_transport_url(settings: &mut crate::config::Settings, url: String) {
        match &mut settings.generation.transport {
            crate::config::TransportSettings::Ollama(transport) => {
                transport.url = url;
            }
            crate::config::TransportSettings::OpenAi(transport) => {
                transport.url = url;
            }
        }
    }

    #[test]
    fn missing_active_trace_context_uses_na_trace_id() {
        assert_eq!(active_trace_id_or_na(), "NA");
    }

    #[test]
    fn capture_reranker_kind_maps_config_variants() {
        assert_eq!(
            capture_reranker_kind(&crate::config::RerankerSettings::PassThrough),
            RerankerKind::PassThrough
        );
        assert_eq!(
            capture_reranker_kind(&crate::config::RerankerSettings::Heuristic(
                crate::config::HeuristicRerankerSettings {
                    weights: crate::config::HeuristicWeights {
                        retrieval_score: 1.0,
                        query_term_coverage: 1.0,
                        phrase_match_bonus: 1.0,
                        title_section_match_bonus: 1.0,
                    },
                }
            )),
            RerankerKind::Heuristic
        );
        assert_eq!(
            capture_reranker_kind(&test_support::test_cross_encoder_reranking_settings().reranker),
            RerankerKind::CrossEncoder
        );
    }

    #[test]
    fn capture_retriever_kind_maps_config_variants() {
        assert_eq!(
            capture_retriever_kind(&crate::config::RetrievalKind::Dense),
            RetrieverKind::Dense
        );
        assert_eq!(
            capture_retriever_kind(&crate::config::RetrievalKind::Hybrid),
            RetrieverKind::Hybrid
        );
    }

    #[test]
    fn capture_retriever_config_preserves_dense_snapshot() {
        let settings = test_support::test_settings();
        let config = capture_retriever_config(&settings.retrieval, "structural");
        assert_eq!(
            config,
            RetrieverConfig::Dense {
                embedding_model_name: "qwen3-embedding:0.6b".to_string(),
                embedding_endpoint: "http://127.0.0.1:9".to_string(),
                embedding_dimension: 3,
                qdrant_collection_name: "chunks_dense_qwen3".to_string(),
                qdrant_vector_name: "default".to_string(),
                score_threshold: 0.2,
                corpus_version: "v1".to_string(),
                chunking_strategy: "structural".to_string(),
            }
        );
    }

    #[test]
    fn capture_retriever_config_preserves_hybrid_snapshot() {
        let mut settings = test_support::test_settings();
        settings.retrieval.kind = crate::config::RetrievalKind::Hybrid;
        settings.retrieval.ingest =
            crate::config::RetrievalIngest::Hybrid(crate::config::HybridRetrievalIngest {
                embedding_model_name: "qwen3-embedding:0.6b".to_string(),
                embedding_dimension: 1024,
                qdrant_collection_name: "chunks_hybrid_structural_qwen3".to_string(),
                dense_vector_name: "dense".to_string(),
                sparse_vector_name: "sparse".to_string(),
                corpus_version: "v1".to_string(),
                tokenizer_library: "tokenizers".to_string(),
                tokenizer_source: "Qwen/Qwen3-Embedding-0.6B".to_string(),
                tokenizer_revision: None,
                preprocessing_kind: "basic_word_v1".to_string(),
                lowercase: true,
                min_token_length: 2,
                vocabulary_path: "Execution/ingest/hybrid/artifacts/vocabularies".to_string(),
                strategy: crate::config::RetrievalStrategy::BagOfWords(
                    crate::config::BagOfWordsRetrievalStrategy {
                        version: "v1".to_string(),
                        query_weighting: "binary_presence".to_string(),
                    },
                ),
            });

        let config = capture_retriever_config(&settings.retrieval, "structural");
        assert_eq!(
            config,
            RetrieverConfig::Hybrid {
                embedding_model_name: "qwen3-embedding:0.6b".to_string(),
                embedding_endpoint: "http://127.0.0.1:9".to_string(),
                embedding_dimension: 1024,
                qdrant_collection_name: "chunks_hybrid_structural_qwen3".to_string(),
                dense_vector_name: "dense".to_string(),
                sparse_vector_name: "sparse".to_string(),
                score_threshold: 0.2,
                corpus_version: "v1".to_string(),
                chunking_strategy: "structural".to_string(),
                tokenizer_library: "tokenizers".to_string(),
                tokenizer_source: "Qwen/Qwen3-Embedding-0.6B".to_string(),
                tokenizer_revision: None,
                preprocessing_kind: "basic_word_v1".to_string(),
                lowercase: true,
                min_token_length: 2,
                vocabulary_path: "Execution/ingest/hybrid/artifacts/vocabularies".to_string(),
                strategy: crate::models::RetrieverStrategyConfig::BagOfWords {
                    version: "v1".to_string(),
                    query_weighting: "binary_presence".to_string(),
                },
            }
        );
    }

    #[test]
    fn capture_reranker_config_preserves_pass_through_and_heuristic_snapshots() {
        let settings = test_support::test_settings();
        let mut reranking = settings.reranking;
        let reranked_output = RerankedRetrievalOutput {
            chunks: vec![],
            metrics: None,
            total_tokens: Some(321),
        };

        let pass_through = capture_reranker_config(&reranking, &reranked_output);
        assert!(
            pass_through.is_none(),
            "pass-through reranker config must be absent per spec"
        );

        reranking = test_support::test_heuristic_reranking_settings();
        if let crate::config::RerankerSettings::Heuristic(settings) = &mut reranking.reranker {
            settings.weights.retrieval_score = 0.7;
            settings.weights.query_term_coverage = 0.15;
            settings.weights.phrase_match_bonus = 0.1;
            settings.weights.title_section_match_bonus = 0.05;
        }

        let config =
            capture_reranker_config(&reranking, &reranked_output).expect("heuristic config");
        match config {
            RerankerConfig::Heuristic { final_k, weights } => {
                assert_eq!(final_k, 5);
                assert_eq!(weights.retrieval_score, 0.7);
                assert_eq!(weights.query_term_coverage, 0.15);
                assert_eq!(weights.phrase_match_bonus, 0.1);
                assert_eq!(weights.title_section_match_bonus, 0.05);
            }
            other => panic!("expected heuristic config, got {other:?}"),
        }
    }

    #[test]
    fn capture_generation_config_preserves_snapshot() {
        let settings = test_support::test_settings();
        let config = capture_generation_config(&settings.generation);
        assert_eq!(config.model, "qwen2.5:1.5b-instruct-q4_K_M");
        assert_eq!(config.model_endpoint, "http://127.0.0.1:9");
        assert_eq!(config.temperature, 0.0);
        assert_eq!(config.max_context_chunks, 5);
        assert_eq!(config.input_cost_per_million_tokens, 0.0);
        assert_eq!(config.output_cost_per_million_tokens, 0.0);
    }

    #[test]
    fn capture_reranker_config_preserves_cross_encoder_snapshot() {
        let reranking = test_support::test_cross_encoder_reranking_settings();
        let reranked_output = RerankedRetrievalOutput {
            chunks: vec![],
            metrics: None,
            total_tokens: Some(987),
        };

        let config =
            capture_reranker_config(&reranking, &reranked_output).expect("cross-encoder config");
        match config {
            RerankerConfig::CrossEncoder {
                final_k,
                cross_encoder,
            } => {
                assert_eq!(final_k, 5);
                assert_eq!(
                    cross_encoder.model_name,
                    "mixedbread-ai/mxbai-rerank-base-v2"
                );
                assert_eq!(cross_encoder.url, "http://127.0.0.1:8081");
                assert_eq!(cross_encoder.total_tokens, Some(987));
                assert_eq!(cross_encoder.cost_per_million_tokens, 0.0);
            }
            other => panic!("expected cross-encoder config, got {other:?}"),
        }
    }

    fn build_orchestrator(
        embedding: &MockHttpServer,
        qdrant: &MockHttpServer,
        chat: &MockHttpServer,
    ) -> (OrchestrationEngine, crate::config::Settings) {
        let mut settings = test_settings();
        settings.retrieval.ollama_url = embedding.endpoint();
        settings.retrieval.qdrant_url = qdrant.endpoint();
        set_generation_transport_url(&mut settings, chat.endpoint());
        let input_validation = InputValidationEngine::for_tests(settings.input_validation.clone());
        let generation = GenerationEngine::for_tests(settings.generation.clone());
        (
            OrchestrationEngine::from_parts(input_validation, generation, &settings).unwrap(),
            settings,
        )
    }

    #[tokio::test]
    async fn happy_path_returns_user_response_from_generation() {
        let embedding = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let qdrant = MockHttpServer::start(vec![
            collection_metadata_response(),
            MockHttpResponse {
                status: StatusCode::OK,
                body: json!({"result":[{"score":0.9,"payload":sample_qdrant_payload()}]})
                    .to_string(),
            },
        ])
        .await;
        let chat = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"message":{"content":"final answer"}}).to_string(),
        }])
        .await;
        let (orchestrator, settings) = build_orchestrator(&embedding, &qdrant, &chat);

        let response = orchestrator
            .handle_request(
                &settings,
                "runtime-run-test",
                UserRequest {
                    query: "question".to_string(),
                },
            )
            .await
            .unwrap();
        assert_eq!(response.answer, "final answer");
    }

    #[tokio::test]
    async fn dense_retrieval_ingest_selects_dense_retriever_request_shape() {
        let embedding = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let qdrant = MockHttpServer::start(vec![
            collection_metadata_response(),
            MockHttpResponse {
                status: StatusCode::OK,
                body:
                    json!({"result":{"points":[{"score":0.9,"payload":sample_qdrant_payload()}]}})
                        .to_string(),
            },
        ])
        .await;
        let chat = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"message":{"content":"answer"}}).to_string(),
        }])
        .await;
        let (orchestrator, settings) = build_orchestrator(&embedding, &qdrant, &chat);

        let _ = orchestrator
            .handle_request(
                &settings,
                "runtime-run-test",
                UserRequest {
                    query: "question".to_string(),
                },
            )
            .await
            .unwrap();

        let paths = qdrant.recorded_paths();
        let search_path = paths
            .iter()
            .find(|p| p.contains("/points"))
            .expect("search path not recorded");
        assert_eq!(search_path, "/collections/chunks_dense_qwen3/points/query");
        let request = qdrant
            .recorded_requests()
            .into_iter()
            .find(|r| r.get("with_payload").is_some())
            .expect("search request not recorded");
        assert!(request.get("prefetch").is_none());
        assert!(request.get("using").is_none());
        assert_eq!(request["with_payload"], true);
        assert_eq!(request["with_vector"], false);
    }

    #[tokio::test]
    async fn hybrid_retrieval_ingest_selects_hybrid_retriever_request_shape() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let embedding = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let tokenizer = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: TEST_TOKENIZER_JSON.to_string(),
        }])
        .await;
        let qdrant = MockHttpServer::start(vec![
            collection_metadata_response(),
            MockHttpResponse {
                status: StatusCode::OK,
                body:
                    json!({"result":{"points":[{"score":0.9,"payload":sample_qdrant_payload()}]}})
                        .to_string(),
            },
        ])
        .await;
        let chat = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"message":{"content":"answer"}}).to_string(),
        }])
        .await;
        let tempdir = tempdir().unwrap();
        write_vocabulary(tempdir.path(), "chunks_hybrid_test", &["hello"]);
        let _hf_base = TempEnvVar::set("RAG_RUNTIME_TEST_HF_BASE_URL", tokenizer.endpoint());

        let mut settings = hybrid_test_settings(tempdir.path().to_str().unwrap());
        settings.retrieval.ollama_url = embedding.endpoint();
        settings.retrieval.qdrant_url = qdrant.endpoint();
        set_generation_transport_url(&mut settings, chat.endpoint());
        let input_validation = InputValidationEngine::for_tests(settings.input_validation.clone());
        let generation = GenerationEngine::for_tests(settings.generation.clone());
        let orchestrator =
            OrchestrationEngine::from_parts(input_validation, generation, &settings).unwrap();

        let _ = orchestrator
            .handle_request(
                &settings,
                "runtime-run-test",
                UserRequest {
                    query: "hello".to_string(),
                },
            )
            .await
            .unwrap();

        let paths = qdrant.recorded_paths();
        let search_path = paths
            .iter()
            .find(|p| p.contains("/points"))
            .expect("search path not recorded");
        assert_eq!(
            search_path,
            "/collections/chunks_hybrid_test_bow/points/query"
        );
        let request = qdrant
            .recorded_requests()
            .into_iter()
            .find(|r| r.get("with_payload").is_some())
            .expect("search request not recorded");
        assert_eq!(request["query"]["fusion"], "rrf");
        assert_eq!(request["prefetch"][0]["using"], "dense");
        assert_eq!(request["prefetch"][1]["using"], "sparse");
        assert_eq!(request["with_payload"], true);
        assert_eq!(request["with_vector"], false);
    }

    #[tokio::test]
    async fn normalized_query_is_propagated_downstream() {
        let embedding = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let qdrant = MockHttpServer::start(vec![
            collection_metadata_response(),
            MockHttpResponse {
                status: StatusCode::OK,
                body:
                    json!({"result":{"points":[{"score":0.9,"payload":sample_qdrant_payload()}]}})
                        .to_string(),
            },
        ])
        .await;
        let chat = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"message":{"content":"answer"}}).to_string(),
        }])
        .await;
        let (orchestrator, settings) = build_orchestrator(&embedding, &qdrant, &chat);

        orchestrator
            .handle_request(
                &settings,
                "runtime-run-test",
                UserRequest {
                    query: " hello   world ".to_string(),
                },
            )
            .await
            .unwrap();
        let requests = embedding.recorded_requests();
        assert_eq!(requests[0]["input"][0], "hello world");
    }

    #[tokio::test]
    async fn empty_retrieval_output_returns_exact_error() {
        let embedding = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let qdrant = MockHttpServer::start(vec![
            collection_metadata_response(),
            MockHttpResponse {
                status: StatusCode::OK,
                body: json!({"result":[]}).to_string(),
            },
        ])
        .await;
        let chat = MockHttpServer::start(vec![]).await;
        let (orchestrator, settings) = build_orchestrator(&embedding, &qdrant, &chat);

        let error = orchestrator
            .handle_request(
                &settings,
                "runtime-run-test",
                UserRequest {
                    query: "question".to_string(),
                },
            )
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "orchestration.empty_retrieval_output");
        assert!(chat.recorded_requests().is_empty());
    }

    #[tokio::test]
    async fn input_validation_failure_stops_before_retrieval() {
        let embedding = MockHttpServer::start(vec![]).await;
        let qdrant = MockHttpServer::start(vec![]).await;
        let chat = MockHttpServer::start(vec![]).await;
        let (orchestrator, settings) = build_orchestrator(&embedding, &qdrant, &chat);

        let error = orchestrator
            .handle_request(
                &settings,
                "runtime-run-test",
                UserRequest {
                    query: "   ".to_string(),
                },
            )
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "input_validation.empty_query");
        assert!(embedding.recorded_requests().is_empty());
        assert!(qdrant.recorded_requests().is_empty());
        assert!(chat.recorded_requests().is_empty());
    }

    #[tokio::test]
    async fn retrieval_failure_stops_before_generation() {
        let embedding = MockHttpServer::start(vec![
            MockHttpResponse {
                status: StatusCode::BAD_GATEWAY,
                body: "bad".to_string(),
            };
            10
        ])
        .await;
        let qdrant = MockHttpServer::start(vec![collection_metadata_response()]).await;
        let chat = MockHttpServer::start(vec![]).await;
        let (orchestrator, settings) = build_orchestrator(&embedding, &qdrant, &chat);

        let error = orchestrator
            .handle_request(
                &settings,
                "runtime-run-test",
                UserRequest {
                    query: "question".to_string(),
                },
            )
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "retrieval.embedding_request");
        assert!(chat.recorded_requests().is_empty());
    }

    #[tokio::test]
    async fn generation_failure_is_propagated_after_successful_retrieval() {
        let embedding = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let qdrant = MockHttpServer::start(vec![
            collection_metadata_response(),
            MockHttpResponse {
                status: StatusCode::OK,
                body:
                    json!({"result":{"points":[{"score":0.9,"payload":sample_qdrant_payload()}]}})
                        .to_string(),
            },
        ])
        .await;
        let retry_attempts = test_settings().generation.retry.max_attempts;
        let chat = MockHttpServer::start(
            (0..=retry_attempts)
                .map(|_| MockHttpResponse {
                    status: StatusCode::BAD_GATEWAY,
                    body: "bad".to_string(),
                })
                .collect(),
        )
        .await;
        let (orchestrator, settings) = build_orchestrator(&embedding, &qdrant, &chat);

        let error = orchestrator
            .handle_request(
                &settings,
                "runtime-run-test",
                UserRequest {
                    query: "question".to_string(),
                },
            )
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "generation.request_failure");
    }

    #[tokio::test]
    async fn retrieved_chunks_are_passed_to_generation_in_same_order() {
        let first = sample_qdrant_payload();
        let second = json!({
            "schema_version": 1,
            "doc_id": "doc-2",
            "chunk_id": "chunk-2",
            "url": "local://doc",
            "document_title": "Doc",
            "section_title": "Section 2",
            "section_path": ["Section 2"],
            "chunk_index": 1,
            "page_start": 2,
            "page_end": 3,
            "tags": ["tag"],
            "content_hash": "sha256:def",
            "chunking_version": "v1",
            "chunk_created_at": "2026-01-01T00:01:00Z",
            "text": "second chunk"
        });
        let embedding = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let qdrant = MockHttpServer::start(vec![
            collection_metadata_response(),
            MockHttpResponse {
                status: StatusCode::OK,
                body: json!({"result":{"points":[
                    {"score":0.9,"payload":first},
                    {"score":0.8,"payload":second}
                ]}})
                .to_string(),
            },
        ])
        .await;
        let chat = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"message":{"content":"answer"}}).to_string(),
        }])
        .await;
        let (orchestrator, settings) = build_orchestrator(&embedding, &qdrant, &chat);

        orchestrator
            .handle_request(
                &settings,
                "runtime-run-test",
                UserRequest {
                    query: "question".to_string(),
                },
            )
            .await
            .unwrap();
        let request = chat.recorded_requests().remove(0);
        let user_message = request["messages"][1]["content"].as_str().unwrap();
        assert!(user_message.contains("[page 1]\nchunk text"));
        assert!(user_message.contains("[pages 2-3]\nsecond chunk"));
        assert!(
            user_message.find("chunk text").unwrap() < user_message.find("second chunk").unwrap()
        );
    }

    #[tokio::test]
    async fn empty_retrieval_output_never_calls_generation() {
        let embedding = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let qdrant = MockHttpServer::start(vec![
            collection_metadata_response(),
            MockHttpResponse {
                status: StatusCode::OK,
                body: json!({"result":{"points":[]}}).to_string(),
            },
        ])
        .await;
        let chat = MockHttpServer::start(vec![]).await;
        let (orchestrator, settings) = build_orchestrator(&embedding, &qdrant, &chat);

        let error = orchestrator
            .handle_request(
                &settings,
                "runtime-run-test",
                UserRequest {
                    query: "question".to_string(),
                },
            )
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "orchestration.empty_retrieval_output");
        assert!(chat.recorded_requests().is_empty());
    }
}

use std::collections::HashSet;
use std::time::Instant;

use async_trait::async_trait;
use tracing::Instrument;
use tracing::{field, info_span};

use crate::config::{HeuristicWeights, RerankerKind};
use crate::errors::{RagRuntimeError, RerankingError};
use crate::models::{
    Chunk, GoldenRetrievalTargets, RerankedChunk, RerankedRetrievalOutput, RetrievalOutput,
    ValidatedUserRequest,
};
use crate::observability::{
    StatusLabel, mark_span_ok, record_reranking_quality_attributes, record_reranking_stage_close,
};
use crate::retrieval_metrics::RetrievalMetricsHelper;

mod cross_encoder;
mod helpers;
mod transport;
mod transports;

pub use cross_encoder::CrossEncoderReranker;
pub use transport::{
    BoxedRerankingTransport, RerankingTransport, RerankingTransportRequest,
    RerankingTransportResponse, RerankingTransportResult, build_reranking_transport,
};

#[async_trait]
pub trait Reranker: Send + Sync {
    fn kind(&self) -> RerankerKind;

    async fn rerank(
        &self,
        request: &ValidatedUserRequest,
        golden_targets: Option<&GoldenRetrievalTargets>,
        final_k: usize,
        retrieval_output: RetrievalOutput,
    ) -> Result<RerankedRetrievalOutput, RagRuntimeError>;
}

#[derive(Debug, Default)]
pub struct PassThroughReranker;

impl PassThroughReranker {
    pub fn new() -> Self {
        Self
    }

    fn kind_label(&self) -> &'static str {
        kind_label(self.kind())
    }

    fn rerank_output(
        &self,
        golden_targets: Option<&GoldenRetrievalTargets>,
        final_k: usize,
        retrieval_output: RetrievalOutput,
    ) -> Result<(RerankedRetrievalOutput, Vec<usize>), RerankingError> {
        let mut result_indices = Vec::with_capacity(retrieval_output.chunks.len());
        let chunks: Vec<RerankedChunk> = retrieval_output
            .chunks
            .into_iter()
            .enumerate()
            .map(|(index, retrieved)| {
                result_indices.push(index);
                RerankedChunk {
                    chunk: retrieved.chunk,
                    retrieval_score: retrieved.score,
                    rerank_score: retrieved.score,
                }
            })
            .collect();
        let metrics = if let Some(golden) = golden_targets {
            let ranked_ids: Vec<String> = chunks.iter().map(|c| c.chunk.chunk_id.clone()).collect();
            let m =
                RetrievalMetricsHelper::compute(golden, &ranked_ids, final_k).map_err(|error| {
                    RerankingError::MetricsComputation {
                        message: error.to_string(),
                    }
                })?;
            Some(m)
        } else {
            None
        };
        Ok((
            RerankedRetrievalOutput {
                chunks,
                metrics,
                total_tokens: None,
            },
            result_indices,
        ))
    }
}

#[async_trait]
impl Reranker for PassThroughReranker {
    fn kind(&self) -> RerankerKind {
        RerankerKind::PassThrough
    }

    async fn rerank(
        &self,
        _request: &ValidatedUserRequest,
        golden_targets: Option<&GoldenRetrievalTargets>,
        final_k: usize,
        retrieval_output: RetrievalOutput,
    ) -> Result<RerankedRetrievalOutput, RagRuntimeError> {
        let kind_label = self.kind_label();
        run_reranking_stage(kind_label, None, async move {
            let output = self.rerank_output(golden_targets, final_k, retrieval_output)?;
            mark_span_ok();
            Ok(output)
        })
        .await
    }
}

#[derive(Debug, Clone)]
pub struct HeuristicReranker {
    weights: HeuristicWeights,
}

impl HeuristicReranker {
    pub fn new(weights: HeuristicWeights) -> Result<Self, RerankingError> {
        validate_weights(&weights)?;
        Ok(Self { weights })
    }

    fn kind_label(&self) -> &'static str {
        kind_label(self.kind())
    }

    fn rerank_output(
        &self,
        request: &ValidatedUserRequest,
        golden_targets: Option<&GoldenRetrievalTargets>,
        final_k: usize,
        retrieval_output: RetrievalOutput,
    ) -> Result<(RerankedRetrievalOutput, Vec<usize>), RerankingError> {
        let normalized_query = normalize_text(&request.query);
        let query_terms = tokenize_terms(&normalized_query);
        let unique_query_terms = unique_terms(&query_terms);
        let raw_scores: Vec<f32> = retrieval_output
            .chunks
            .iter()
            .map(|chunk| chunk.score)
            .collect();
        if raw_scores.iter().any(|score| !score.is_finite()) {
            return Err(RerankingError::InternalState {
                message: "retrieval scores must be finite".to_string(),
            });
        }

        let min_score = raw_scores.iter().copied().reduce(f32::min).unwrap_or(0.0);
        let max_score = raw_scores.iter().copied().reduce(f32::max).unwrap_or(0.0);

        let mut ranked_candidates: Vec<(usize, RerankedChunk)> = retrieval_output
            .chunks
            .into_iter()
            .enumerate()
            .map(|(index, retrieved)| {
                let normalized_chunk_text = normalize_text(&retrieved.chunk.text);
                let chunk_terms = tokenize_terms(&normalized_chunk_text);
                let retrieval_score =
                    normalized_retrieval_score(retrieved.score, min_score, max_score);
                let query_term_coverage = query_term_coverage(&unique_query_terms, &chunk_terms);
                let phrase_match_bonus =
                    phrase_match_bonus(&query_terms, &normalized_query, &normalized_chunk_text);
                let title_section_match_bonus =
                    title_section_match_bonus(&unique_query_terms, &retrieved.chunk);
                let rerank_score = self.weights.retrieval_score * retrieval_score
                    + self.weights.query_term_coverage * query_term_coverage
                    + self.weights.phrase_match_bonus * phrase_match_bonus
                    + self.weights.title_section_match_bonus * title_section_match_bonus;
                (
                    index,
                    RerankedChunk {
                        chunk: retrieved.chunk,
                        retrieval_score: retrieved.score,
                        rerank_score,
                    },
                )
            })
            .collect();

        ranked_candidates.sort_by(|left, right| {
            right
                .1
                .rerank_score
                .total_cmp(&left.1.rerank_score)
                .then_with(|| left.0.cmp(&right.0))
        });

        let result_indices = ranked_candidates.iter().map(|(index, _)| *index).collect();
        let chunks: Vec<RerankedChunk> = ranked_candidates
            .into_iter()
            .map(|(_, chunk)| chunk)
            .collect();
        let metrics = if let Some(golden) = golden_targets {
            let ranked_ids: Vec<String> = chunks.iter().map(|c| c.chunk.chunk_id.clone()).collect();
            let m =
                RetrievalMetricsHelper::compute(golden, &ranked_ids, final_k).map_err(|error| {
                    RerankingError::MetricsComputation {
                        message: error.to_string(),
                    }
                })?;
            Some(m)
        } else {
            None
        };
        Ok((
            RerankedRetrievalOutput {
                chunks,
                metrics,
                total_tokens: None,
            },
            result_indices,
        ))
    }
}

#[async_trait]
impl Reranker for HeuristicReranker {
    fn kind(&self) -> RerankerKind {
        RerankerKind::Heuristic
    }

    async fn rerank(
        &self,
        request: &ValidatedUserRequest,
        golden_targets: Option<&GoldenRetrievalTargets>,
        final_k: usize,
        retrieval_output: RetrievalOutput,
    ) -> Result<RerankedRetrievalOutput, RagRuntimeError> {
        let kind_label = self.kind_label();
        run_reranking_stage(kind_label, None, async move {
            let output = self.rerank_output(request, golden_targets, final_k, retrieval_output)?;
            mark_span_ok();
            Ok(output)
        })
        .await
    }
}

async fn run_reranking_stage<Fut>(
    reranker_kind: &'static str,
    cost_per_million_tokens: Option<f64>,
    future: Fut,
) -> Result<RerankedRetrievalOutput, RagRuntimeError>
where
    Fut: std::future::Future<Output = Result<(RerankedRetrievalOutput, Vec<usize>), RagRuntimeError>>
        + Send,
{
    let stage_span = info_span!(
        "reranking.rank",
        "span.module" = "reranking",
        "span.stage" = "rank",
        status = field::Empty,
        "error.type" = field::Empty,
        "error.message" = field::Empty,
        "openinference.span.kind" = "RERANKER",
        reranker_kind = reranker_kind,
        "reranker.retrieval_scores" = field::Empty,
        "reranker.rerank_scores" = field::Empty,
        "reranker.result_indices" = field::Empty,
        "reranking.total_tokens" = field::Empty,
        "reranking.total_cost_usd" = field::Empty,
        context_recall_soft = field::Empty,
        context_recall_strict = field::Empty,
        context_rr_soft = field::Empty,
        context_rr_strict = field::Empty,
        context_ndcg = field::Empty,
        context_num_relevant_soft = field::Empty,
        context_num_relevant_strict = field::Empty,
        context_first_relevant_rank_soft = field::Empty,
        context_first_relevant_rank_strict = field::Empty,
    );
    let stage_started = Instant::now();
    let result = future.instrument(stage_span.clone()).await;
    let status = match &result {
        Err(error) => {
            stage_span.record("status", "error");
            stage_span.record("error.type", error.error_type());
            stage_span.record("error.message", field::display(error.to_string()));
            StatusLabel::Error
        }
        Ok((output, result_indices)) => {
            stage_span.record("status", "ok");
            stage_span.record(
                "reranker.retrieval_scores",
                field::display(compact_score_list(
                    output.chunks.iter().map(|chunk| chunk.retrieval_score),
                )),
            );
            stage_span.record(
                "reranker.rerank_scores",
                field::display(compact_score_list(
                    output.chunks.iter().map(|chunk| chunk.rerank_score),
                )),
            );
            stage_span.record(
                "reranker.result_indices",
                field::display(compact_usize_list(result_indices.iter().copied())),
            );
            if let Some(total_tokens) = output.total_tokens {
                stage_span.record("reranking.total_tokens", total_tokens);
                if let Some(cost_per_million_tokens) = cost_per_million_tokens {
                    stage_span.record(
                        "reranking.total_cost_usd",
                        total_tokens as f64 * cost_per_million_tokens / 1_000_000.0,
                    );
                }
            }
            if let Some(metrics) = &output.metrics {
                record_reranking_quality_attributes(&stage_span, metrics);
                let _guard = stage_span.enter();
                tracing::info!(
                    context_recall_soft = metrics.recall_soft as f64,
                    context_recall_strict = metrics.recall_strict as f64,
                    context_rr_soft = metrics.rr_soft as f64,
                    context_rr_strict = metrics.rr_strict as f64,
                    context_ndcg = metrics.ndcg as f64,
                    context_first_relevant_rank_soft =
                        field::debug(metrics.first_relevant_rank_soft),
                    context_first_relevant_rank_strict =
                        field::debug(metrics.first_relevant_rank_strict),
                    context_num_relevant_soft = metrics.num_relevant_soft as i64,
                    context_num_relevant_strict = metrics.num_relevant_strict as i64,
                    "reranker_quality_metrics"
                );
            }
            StatusLabel::Ok
        }
    };
    record_reranking_stage_close(
        reranker_kind,
        stage_started.elapsed().as_secs_f64() * 1000.0,
        status,
    );
    result.map(|(output, _)| output)
}

fn kind_label(kind: RerankerKind) -> &'static str {
    match kind {
        RerankerKind::PassThrough => "PassThrough",
        RerankerKind::Heuristic => "Heuristic",
        RerankerKind::CrossEncoder => "CrossEncoder",
    }
}

fn compact_score_list(scores: impl Iterator<Item = f32>) -> String {
    let formatted = scores
        .map(|score| format!("{score:.6}"))
        .collect::<Vec<_>>()
        .join(", ");
    format!("[{formatted}]")
}

fn compact_usize_list(values: impl Iterator<Item = usize>) -> String {
    let formatted = values
        .map(|value| value.to_string())
        .collect::<Vec<_>>()
        .join(", ");
    format!("[{formatted}]")
}

fn validate_weights(weights: &HeuristicWeights) -> Result<(), RerankingError> {
    if !weights.retrieval_score.is_finite()
        || !weights.query_term_coverage.is_finite()
        || !weights.phrase_match_bonus.is_finite()
        || !weights.title_section_match_bonus.is_finite()
    {
        return Err(RerankingError::InvalidConfiguration {
            message: "reranker weights must be finite".to_string(),
        });
    }
    if weights.retrieval_score < 0.0
        || weights.query_term_coverage < 0.0
        || weights.phrase_match_bonus < 0.0
        || weights.title_section_match_bonus < 0.0
    {
        return Err(RerankingError::InvalidConfiguration {
            message: "reranker weights must be non-negative".to_string(),
        });
    }
    Ok(())
}

fn normalize_text(text: &str) -> String {
    text.trim()
        .to_lowercase()
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}

fn tokenize_terms(normalized_text: &str) -> Vec<String> {
    normalized_text
        .split_whitespace()
        .filter(|token| token.len() > 1)
        .map(ToOwned::to_owned)
        .collect()
}

fn unique_terms(terms: &[String]) -> Vec<String> {
    let mut seen = HashSet::new();
    let mut unique = Vec::with_capacity(terms.len());
    for term in terms {
        if seen.insert(term.clone()) {
            unique.push(term.clone());
        }
    }
    unique
}

fn normalized_retrieval_score(raw_score: f32, min_score: f32, max_score: f32) -> f32 {
    if max_score > min_score {
        (raw_score - min_score) / (max_score - min_score)
    } else {
        1.0
    }
}

fn query_term_coverage(unique_query_terms: &[String], chunk_terms: &[String]) -> f32 {
    if unique_query_terms.is_empty() {
        return 0.0;
    }
    let matched_query_terms = unique_query_terms
        .iter()
        .filter(|term| chunk_terms.iter().any(|chunk_term| chunk_term == *term))
        .count();
    matched_query_terms as f32 / unique_query_terms.len() as f32
}

fn phrase_match_bonus(
    query_terms: &[String],
    normalized_query_text: &str,
    normalized_chunk_text: &str,
) -> f32 {
    if !normalized_query_text.is_empty() && normalized_chunk_text.contains(normalized_query_text) {
        return 1.0;
    }
    if query_terms.len() < 2 {
        return 0.0;
    }
    let has_adjacent_phrase = query_terms
        .windows(2)
        .map(|pair| pair.join(" "))
        .any(|phrase| normalized_chunk_text.contains(&phrase));
    if has_adjacent_phrase { 0.5 } else { 0.0 }
}

fn title_section_match_bonus(unique_query_terms: &[String], chunk: &Chunk) -> f32 {
    if unique_query_terms.is_empty() {
        return 0.0;
    }
    let mut metadata_text = chunk.document_title.clone();
    if let Some(section_title) = &chunk.section_title {
        metadata_text.push(' ');
        metadata_text.push_str(section_title);
    }
    if !chunk.section_path.is_empty() {
        metadata_text.push(' ');
        metadata_text.push_str(&chunk.section_path.join(" "));
    }
    let metadata_terms = tokenize_terms(&normalize_text(&metadata_text));
    let matched_metadata_terms = unique_query_terms
        .iter()
        .filter(|term| {
            metadata_terms
                .iter()
                .any(|metadata_term| metadata_term == *term)
        })
        .count();
    matched_metadata_terms as f32 / unique_query_terms.len() as f32
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::RetrievedChunk;

    fn sample_chunk(
        chunk_id: &str,
        text: &str,
        title: &str,
        section_title: Option<&str>,
        score: f32,
    ) -> RetrievedChunk {
        RetrievedChunk {
            score,
            chunk: Chunk {
                schema_version: 1,
                doc_id: "doc-1".to_string(),
                chunk_id: chunk_id.to_string(),
                url: "local://doc".to_string(),
                document_title: title.to_string(),
                section_title: section_title.map(ToOwned::to_owned),
                section_path: section_title
                    .map(|value| vec![value.to_string()])
                    .unwrap_or_default(),
                chunk_index: 0,
                page_start: 1,
                page_end: 1,
                tags: vec![],
                content_hash: format!("sha256:{chunk_id}"),
                chunking_version: "v1".to_string(),
                chunk_created_at: "2026-01-01T00:00:00Z".to_string(),
                text: text.to_string(),
                ingest: None,
            },
        }
    }

    #[tokio::test]
    async fn pass_through_preserves_order_and_scores() {
        let reranker = PassThroughReranker::new();
        let output = reranker
            .rerank(
                &ValidatedUserRequest {
                    query: "query".to_string(),
                    input_token_count: 1,
                    ..Default::default()
                },
                None,
                4,
                RetrievalOutput {
                    chunks: vec![
                        sample_chunk("chunk-1", "alpha", "Doc 1", Some("Section 1"), 0.9),
                        sample_chunk("chunk-2", "beta", "Doc 2", Some("Section 2"), 0.7),
                    ],
                    metrics: None,
                    chunking_strategy: String::new(),
                },
            )
            .await
            .expect("rerank output");

        assert_eq!(output.chunks.len(), 2);
        assert_eq!(output.chunks[0].chunk.chunk_id, "chunk-1");
        assert_eq!(output.chunks[1].chunk.chunk_id, "chunk-2");
        assert_eq!(output.chunks[0].rerank_score, 0.9);
        assert_eq!(output.chunks[1].rerank_score, 0.7);
    }
}

use std::collections::HashSet;
use std::sync::{
    Arc,
    atomic::{AtomicUsize, Ordering},
};
use std::time::Duration;

use backon::{ExponentialBuilder, Retryable};

use super::transport::RerankingTransportResult;
use crate::config::{CrossEncoderTransportSettings, RetryBackoff};
use crate::errors::RerankingError;
use crate::models::{RerankedChunk, RetrievedChunk};
use crate::observability::record_retry_attempts;

pub(super) fn validate_cross_encoder_transport_settings(
    settings: &CrossEncoderTransportSettings,
) -> Result<(), RerankingError> {
    match settings {
        CrossEncoderTransportSettings::MixedbreadAi(settings) => {
            if settings.url.trim().is_empty() {
                return Err(RerankingError::InvalidConfiguration {
                    message: "mixedbread cross-encoder url must be non-empty".to_string(),
                });
            }
            if settings.model_name.trim().is_empty() {
                return Err(RerankingError::InvalidConfiguration {
                    message: "mixedbread cross-encoder model_name must be non-empty".to_string(),
                });
            }
            if settings.batch_size == 0 {
                return Err(RerankingError::InvalidConfiguration {
                    message: "mixedbread cross-encoder batch_size must be >= 1".to_string(),
                });
            }
            if settings.timeout_sec == 0 {
                return Err(RerankingError::InvalidConfiguration {
                    message: "mixedbread cross-encoder timeout_sec must be >= 1".to_string(),
                });
            }
        }
        CrossEncoderTransportSettings::VoyageAi(settings) => {
            if settings.url.trim().is_empty() {
                return Err(RerankingError::InvalidConfiguration {
                    message: "voyageai cross-encoder url must be non-empty".to_string(),
                });
            }
            if settings.api_key.trim().is_empty() {
                return Err(RerankingError::InvalidConfiguration {
                    message: "voyageai cross-encoder api_key must be non-empty".to_string(),
                });
            }
            if settings.model_name.trim().is_empty() {
                return Err(RerankingError::InvalidConfiguration {
                    message: "voyageai cross-encoder model_name must be non-empty".to_string(),
                });
            }
            if settings.batch_size == 0 {
                return Err(RerankingError::InvalidConfiguration {
                    message: "voyageai cross-encoder batch_size must be >= 1".to_string(),
                });
            }
            if settings.timeout_sec == 0 {
                return Err(RerankingError::InvalidConfiguration {
                    message: "voyageai cross-encoder timeout_sec must be >= 1".to_string(),
                });
            }
        }
    }
    Ok(())
}

pub(super) fn map_transport_results(
    retrieval_chunks: &[RetrievedChunk],
    results: Vec<RerankingTransportResult>,
) -> Result<(Vec<RerankedChunk>, Vec<usize>), RerankingError> {
    validate_transport_results(
        &retrieval_chunks
            .iter()
            .map(|chunk| chunk.chunk.text.clone())
            .collect::<Vec<_>>(),
        &results,
    )?;
    let result_indices = results
        .iter()
        .map(|result| result.index)
        .collect::<Vec<_>>();
    let chunks = results
        .into_iter()
        .map(|result| {
            let retrieved = &retrieval_chunks[result.index];
            RerankedChunk {
                chunk: retrieved.chunk.clone(),
                retrieval_score: retrieved.score,
                rerank_score: result.score,
            }
        })
        .collect();
    Ok((chunks, result_indices))
}

pub(super) fn validate_transport_results(
    documents: &[String],
    results: &[RerankingTransportResult],
) -> Result<(), RerankingError> {
    if results.len() != documents.len() {
        return Err(RerankingError::CandidateTransformation {
            message: format!(
                "transport returned {} results for {} inputs",
                results.len(),
                documents.len()
            ),
        });
    }
    let mut seen = HashSet::new();
    for result in results {
        if result.index >= documents.len() {
            return Err(RerankingError::CandidateTransformation {
                message: format!(
                    "transport result index {} is out of range for batch of size {}",
                    result.index,
                    documents.len()
                ),
            });
        }
        if !result.score.is_finite() {
            return Err(RerankingError::CandidateTransformation {
                message: "transport rerank score must be finite".to_string(),
            });
        }
        if !seen.insert(result.index) {
            return Err(RerankingError::CandidateTransformation {
                message: format!("transport returned duplicate index {}", result.index),
            });
        }
    }
    Ok(())
}

pub(super) async fn retry_reranking_with_policy<F, Fut, T>(
    max_attempts: usize,
    backoff: RetryBackoff,
    dependency: &'static str,
    operation: F,
) -> Result<T, RerankingError>
where
    F: Fn() -> Fut,
    Fut: std::future::Future<Output = Result<T, RerankingError>>,
{
    let failure_count = Arc::new(AtomicUsize::new(0));
    let builder = match backoff {
        RetryBackoff::Exponential => ExponentialBuilder::default()
            .with_factor(2.0)
            .with_min_delay(Duration::from_millis(10))
            .with_max_delay(Duration::from_millis(250))
            .with_jitter()
            .with_max_times(max_attempts),
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
    .when(|error: &RerankingError| error.is_retryable())
    .await;
    let retry_attempts = failure_count.load(Ordering::Relaxed).saturating_sub(1);
    if retry_attempts > 0 {
        record_retry_attempts(dependency, retry_attempts);
    }
    result
}

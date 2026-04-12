use std::sync::Arc;
use std::time::Duration;

use async_trait::async_trait;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use tokio::sync::Mutex;

use super::super::helpers::{retry_reranking_with_policy, validate_transport_results};
use super::super::transport::{
    RerankingTransport, RerankingTransportRequest, RerankingTransportResponse,
    RerankingTransportResult,
};
use crate::config::{CrossEncoderTransportSettings, MixedbreadAiCrossEncoderTransportSettings};
use crate::errors::RerankingError;
use crate::generation::tokenizer::{TokenizerResource, load_tokenizer_from_repo};
use crate::observability::{StatusLabel, record_dependency_close};

#[derive(Debug, Default)]
pub struct MixedbreadAiRerankingTransport {
    tokenizer: Mutex<Option<Arc<TokenizerResource>>>,
}

#[derive(Debug, Serialize)]
struct MixedbreadRequestBody<'a> {
    query: &'a str,
    texts: &'a [String],
}

#[derive(Debug, Deserialize)]
struct MixedbreadHealthResponse {
    status: String,
    #[allow(dead_code)]
    model_id: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum MixedbreadHealthStatus {
    Ready,
    Warming,
}

#[derive(Debug, Deserialize)]
struct MixedbreadResponse {
    model_id: String,
    results: Vec<MixedbreadResultItem>,
}

#[derive(Debug, Deserialize)]
struct MixedbreadResultItem {
    index: usize,
    score: f32,
    text: Option<String>,
    #[allow(dead_code)]
    rank: Option<usize>,
}

#[async_trait]
impl RerankingTransport for MixedbreadAiRerankingTransport {
    async fn rerank(
        &self,
        request: RerankingTransportRequest,
        settings: &CrossEncoderTransportSettings,
    ) -> Result<RerankingTransportResponse, RerankingError> {
        let settings = match settings {
            CrossEncoderTransportSettings::MixedbreadAi(settings) => settings,
            _ => {
                return Err(RerankingError::InternalState {
                    message: "mixedbread transport received non-mixedbread settings".to_string(),
                });
            }
        };
        let client = Client::builder()
            .timeout(Duration::from_secs(settings.timeout_sec))
            .build()
            .map_err(|error| RerankingError::InvalidConfiguration {
                message: format!("failed to initialize mixedbread reranking client: {error}"),
            })?;

        let mut aggregated = Vec::with_capacity(request.documents.len());
        let mut total_tokens = 0usize;
        for (batch_index, documents) in request.documents.chunks(settings.batch_size).enumerate() {
            let batch_request = RerankingTransportRequest {
                query: request.query.clone(),
                documents: documents.to_vec(),
                top_k: None,
            };
            let batch_started = std::time::Instant::now();
            let response = retry_reranking_with_policy(
                settings.max_attempts,
                settings.backoff.clone(),
                "rerank",
                || async {
                    match self.probe_mixedbread_health(&client, settings).await? {
                        MixedbreadHealthStatus::Ready | MixedbreadHealthStatus::Warming => {}
                    }
                    self.call_mixedbread_batch(&client, &batch_request, settings)
                        .await
                },
            )
            .await;
            record_dependency_close(
                "reranking",
                "reranking",
                "rerank",
                batch_started.elapsed().as_secs_f64() * 1000.0,
                if response.is_ok() {
                    StatusLabel::Ok
                } else {
                    StatusLabel::Error
                },
            );
            let response = response?;
            let batch_offset = batch_index * settings.batch_size;
            total_tokens += self
                .estimate_mixedbread_tokens(settings, &batch_request, &response)
                .await?;
            aggregated.extend(response.results.into_iter().map(|result| {
                RerankingTransportResult {
                    index: batch_offset + result.index,
                    score: result.score,
                }
            }));
        }

        aggregated.sort_by(|left, right| {
            right
                .score
                .total_cmp(&left.score)
                .then_with(|| left.index.cmp(&right.index))
        });
        validate_transport_results(&request.documents, &aggregated)?;
        Ok(RerankingTransportResponse {
            results: aggregated,
            total_tokens: Some(total_tokens),
        })
    }
}

impl MixedbreadAiRerankingTransport {
    async fn probe_mixedbread_health(
        &self,
        client: &Client,
        settings: &MixedbreadAiCrossEncoderTransportSettings,
    ) -> Result<MixedbreadHealthStatus, RerankingError> {
        let url = format!("{}/health", settings.url.trim_end_matches('/'));
        let response =
            client
                .get(&url)
                .send()
                .await
                .map_err(|error| RerankingError::ServiceRequest {
                    status: 0,
                    message: error.to_string(),
                })?;
        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        if !status.is_success() {
            return Err(RerankingError::ServiceRequest {
                status: status.as_u16(),
                message: format!("status {status}: {body}"),
            });
        }
        let parsed: MixedbreadHealthResponse = serde_json::from_str(&body).map_err(|error| {
            RerankingError::ServiceResponseValidation {
                message: format!("invalid mixedbread health response: {error}"),
            }
        })?;
        match parsed.status.as_str() {
            "ready" => Ok(MixedbreadHealthStatus::Ready),
            "warming" => Ok(MixedbreadHealthStatus::Warming),
            other => Err(RerankingError::ServiceResponseValidation {
                message: format!("unexpected mixedbread health status {other}"),
            }),
        }
    }

    async fn call_mixedbread_batch(
        &self,
        client: &Client,
        request: &RerankingTransportRequest,
        settings: &MixedbreadAiCrossEncoderTransportSettings,
    ) -> Result<MixedbreadResponse, RerankingError> {
        let url = format!("{}/rerank", settings.url.trim_end_matches('/'));
        let response = client
            .post(&url)
            .json(&MixedbreadRequestBody {
                query: &request.query,
                texts: &request.documents,
            })
            .send()
            .await
            .map_err(|error| RerankingError::ServiceRequest {
                status: 0,
                message: error.to_string(),
            })?;
        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        if !status.is_success() {
            return Err(RerankingError::ServiceRequest {
                status: status.as_u16(),
                message: format!("status {status}: {body}"),
            });
        }

        let parsed: MixedbreadResponse = serde_json::from_str(&body).map_err(|error| {
            RerankingError::ServiceResponseValidation {
                message: format!("invalid mixedbread rerank response: {error}"),
            }
        })?;
        if parsed.model_id.trim().is_empty() {
            return Err(RerankingError::ServiceResponseValidation {
                message: "mixedbread rerank response missing model_id".to_string(),
            });
        }
        validate_mixedbread_results(&request.documents, &parsed.results)?;
        Ok(parsed)
    }

    async fn estimate_mixedbread_tokens(
        &self,
        settings: &MixedbreadAiCrossEncoderTransportSettings,
        request: &RerankingTransportRequest,
        response: &MixedbreadResponse,
    ) -> Result<usize, RerankingError> {
        let tokenizer = self.mixedbread_tokenizer(settings).await?;
        let mut total = tokenizer.count_tokens(&request.query).map_err(|error| {
            RerankingError::InternalState {
                message: error.to_string(),
            }
        })?;
        for document in &request.documents {
            total += tokenizer.count_tokens(document).map_err(|error| {
                RerankingError::InternalState {
                    message: error.to_string(),
                }
            })?;
        }
        for result in &response.results {
            if let Some(text) = &result.text {
                total += tokenizer.count_tokens(text).map_err(|error| {
                    RerankingError::InternalState {
                        message: error.to_string(),
                    }
                })?;
            }
        }
        Ok(total)
    }

    async fn mixedbread_tokenizer(
        &self,
        settings: &MixedbreadAiCrossEncoderTransportSettings,
    ) -> Result<Arc<TokenizerResource>, RerankingError> {
        let mut guard = self.tokenizer.lock().await;
        if let Some(existing) = guard.as_ref() {
            return Ok(Arc::clone(existing));
        }
        let resource = Arc::new(
            load_tokenizer_from_repo(&settings.tokenizer_source)
                .await
                .map_err(|error| RerankingError::InvalidConfiguration {
                    message: format!(
                        "failed to initialize mixedbread tokenizer from {}: {error}",
                        settings.tokenizer_source
                    ),
                })?,
        );
        *guard = Some(Arc::clone(&resource));
        Ok(resource)
    }
}

fn validate_mixedbread_results(
    documents: &[String],
    results: &[MixedbreadResultItem],
) -> Result<(), RerankingError> {
    let normalized = results
        .iter()
        .map(|result| RerankingTransportResult {
            index: result.index,
            score: result.score,
        })
        .collect::<Vec<_>>();
    validate_transport_results(documents, &normalized)
}

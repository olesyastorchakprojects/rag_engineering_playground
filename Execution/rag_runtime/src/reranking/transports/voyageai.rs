use std::time::Duration;

use async_trait::async_trait;
use reqwest::Client;
use serde::{Deserialize, Serialize};

use super::super::helpers::{retry_reranking_with_policy, validate_transport_results};
use super::super::transport::{
    RerankingTransport, RerankingTransportRequest, RerankingTransportResponse,
    RerankingTransportResult,
};
use crate::config::{CrossEncoderTransportSettings, VoyageAiCrossEncoderTransportSettings};
use crate::errors::RerankingError;
use crate::observability::{StatusLabel, record_dependency_close};

#[derive(Debug, Default)]
pub struct VoyageAiRerankingTransport;

#[derive(Debug, Serialize)]
struct VoyageAiRequestBody<'a> {
    model: &'a str,
    query: &'a str,
    documents: &'a [String],
    top_k: usize,
}

#[derive(Debug, Deserialize)]
struct VoyageAiResponse {
    data: Vec<VoyageAiResultItem>,
    usage: Option<VoyageAiUsage>,
}

#[derive(Debug, Deserialize)]
struct VoyageAiResultItem {
    relevance_score: f32,
    index: usize,
}

#[derive(Debug, Deserialize)]
struct VoyageAiUsage {
    total_tokens: Option<usize>,
}

#[async_trait]
impl RerankingTransport for VoyageAiRerankingTransport {
    async fn rerank(
        &self,
        request: RerankingTransportRequest,
        settings: &CrossEncoderTransportSettings,
    ) -> Result<RerankingTransportResponse, RerankingError> {
        let settings = match settings {
            CrossEncoderTransportSettings::VoyageAi(settings) => settings,
            _ => {
                return Err(RerankingError::InternalState {
                    message: "voyageai transport received non-voyageai settings".to_string(),
                });
            }
        };
        let client = Client::builder()
            .timeout(Duration::from_secs(settings.timeout_sec))
            .build()
            .map_err(|error| RerankingError::InvalidConfiguration {
                message: format!("failed to initialize voyageai reranking client: {error}"),
            })?;

        let mut aggregated = Vec::with_capacity(request.documents.len());
        let mut total_tokens = 0usize;
        for (batch_index, documents) in request.documents.chunks(settings.batch_size).enumerate() {
            let batch_request = RerankingTransportRequest {
                query: request.query.clone(),
                documents: documents.to_vec(),
                top_k: Some(documents.len()),
            };
            let batch_started = std::time::Instant::now();
            let response = retry_reranking_with_policy(
                settings.max_attempts,
                settings.backoff.clone(),
                "rerank",
                || async {
                    self.call_voyage_batch(&client, &batch_request, settings)
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
            total_tokens += response
                .usage
                .as_ref()
                .and_then(|usage| usage.total_tokens)
                .unwrap_or(0);
            validate_voyage_results(&batch_request.documents, &response.data)?;
            aggregated.extend(
                response
                    .data
                    .into_iter()
                    .map(|result| RerankingTransportResult {
                        index: batch_offset + result.index,
                        score: result.relevance_score,
                    }),
            );
        }
        validate_transport_results(&request.documents, &aggregated)?;
        Ok(RerankingTransportResponse {
            results: aggregated,
            total_tokens: Some(total_tokens),
        })
    }
}

impl VoyageAiRerankingTransport {
    async fn call_voyage_batch(
        &self,
        client: &Client,
        request: &RerankingTransportRequest,
        settings: &VoyageAiCrossEncoderTransportSettings,
    ) -> Result<VoyageAiResponse, RerankingError> {
        let response = client
            .post(&settings.url)
            .bearer_auth(&settings.api_key)
            .json(&VoyageAiRequestBody {
                model: &settings.model_name,
                query: &request.query,
                documents: &request.documents,
                top_k: request.top_k.unwrap_or(request.documents.len()),
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
        serde_json::from_str(&body).map_err(|error| RerankingError::ServiceResponseValidation {
            message: format!("invalid voyageai rerank response: {error}"),
        })
    }
}

fn validate_voyage_results(
    documents: &[String],
    results: &[VoyageAiResultItem],
) -> Result<(), RerankingError> {
    let normalized = results
        .iter()
        .map(|result| RerankingTransportResult {
            index: result.index,
            score: result.relevance_score,
        })
        .collect::<Vec<_>>();
    validate_transport_results(documents, &normalized)
}

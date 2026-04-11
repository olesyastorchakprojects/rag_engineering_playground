use async_trait::async_trait;

use crate::config::{CrossEncoderRerankerSettings, CrossEncoderTransportSettings, RerankerKind};
use crate::errors::{RagRuntimeError, RerankingError};
use crate::models::{
    GoldenRetrievalTargets, RerankedRetrievalOutput, RetrievalOutput, ValidatedUserRequest,
};
use crate::observability::mark_span_ok;
use crate::retrieval_metrics::RetrievalMetricsHelper;

use super::helpers::{map_transport_results, validate_cross_encoder_transport_settings};
use super::transport::{BoxedRerankingTransport, RerankingTransportRequest};
use super::{Reranker, kind_label, run_reranking_stage};

pub struct CrossEncoderReranker {
    settings: CrossEncoderRerankerSettings,
    transport: BoxedRerankingTransport,
}

impl CrossEncoderReranker {
    pub fn new(
        settings: CrossEncoderRerankerSettings,
        transport: BoxedRerankingTransport,
    ) -> Result<Self, RerankingError> {
        validate_cross_encoder_transport_settings(&settings.transport)?;
        Ok(Self {
            settings,
            transport,
        })
    }

    fn kind_label(&self) -> &'static str {
        kind_label(self.kind())
    }

    fn cost_per_million_tokens(&self) -> f64 {
        match &self.settings.transport {
            CrossEncoderTransportSettings::MixedbreadAi(settings) => {
                settings.cost_per_million_tokens
            }
            CrossEncoderTransportSettings::VoyageAi(settings) => settings.cost_per_million_tokens,
        }
    }

    async fn rerank_output(
        &self,
        request: &ValidatedUserRequest,
        golden_targets: Option<&GoldenRetrievalTargets>,
        final_k: usize,
        retrieval_output: RetrievalOutput,
    ) -> Result<(RerankedRetrievalOutput, Vec<usize>), RerankingError> {
        let transport_request = RerankingTransportRequest {
            query: request.query.clone(),
            documents: retrieval_output
                .chunks
                .iter()
                .map(|retrieved| retrieved.chunk.text.clone())
                .collect(),
            top_k: Some(retrieval_output.chunks.len()),
        };
        let transport_response = self
            .transport
            .rerank(transport_request, &self.settings.transport)
            .await?;

        let (chunks, result_indices) =
            map_transport_results(&retrieval_output.chunks, transport_response.results)?;
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
                total_tokens: transport_response.total_tokens,
            },
            result_indices,
        ))
    }
}

#[async_trait]
impl Reranker for CrossEncoderReranker {
    fn kind(&self) -> RerankerKind {
        RerankerKind::CrossEncoder
    }

    async fn rerank(
        &self,
        request: &ValidatedUserRequest,
        golden_targets: Option<&GoldenRetrievalTargets>,
        final_k: usize,
        retrieval_output: RetrievalOutput,
    ) -> Result<RerankedRetrievalOutput, RagRuntimeError> {
        let kind_label = self.kind_label();
        let cost_per_million_tokens = self.cost_per_million_tokens();
        run_reranking_stage(kind_label, Some(cost_per_million_tokens), async move {
            let output = self
                .rerank_output(request, golden_targets, final_k, retrieval_output)
                .await?;
            mark_span_ok();
            Ok(output)
        })
        .await
    }
}

#[cfg(test)]
mod tests {
    use axum::http::StatusCode;
    use serde_json::json;

    use super::*;
    use crate::config::{CrossEncoderRerankerSettings, CrossEncoderTransportSettings};
    use crate::models::{Chunk, RetrievedChunk};
    use crate::reranking::build_reranking_transport;

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

    fn sample_cross_encoder_settings(
        endpoint: String,
        batch_size: usize,
    ) -> CrossEncoderRerankerSettings {
        CrossEncoderRerankerSettings {
            transport: CrossEncoderTransportSettings::MixedbreadAi(
                crate::config::MixedbreadAiCrossEncoderTransportSettings {
                    url: endpoint,
                    model_name: "mixedbread-ai/mxbai-rerank-base-v2".to_string(),
                    batch_size,
                    timeout_sec: 30,
                    cost_per_million_tokens: 0.0,
                    tokenizer_source: "mixedbread-ai/mxbai-rerank-base-v2".to_string(),
                    max_attempts: 3,
                    backoff: crate::config::RetryBackoff::Exponential,
                },
            ),
        }
    }

    #[tokio::test]
    async fn cross_encoder_sends_query_and_texts_only() {
        let server = crate::test_support::MockHttpServer::start(vec![
            crate::test_support::MockHttpResponse {
                status: StatusCode::OK,
                body: json!({
                    "status":"ready",
                    "model_id":"mixedbread-ai/mxbai-rerank-base-v2"
                })
                .to_string(),
            },
            crate::test_support::MockHttpResponse {
                status: StatusCode::OK,
                body: json!({
                    "model_id":"mixedbread-ai/mxbai-rerank-base-v2",
                    "results":[
                        {"index":1,"score":0.9,"text":"beta","rank":1},
                        {"index":0,"score":0.3,"text":"alpha","rank":2}
                    ]
                })
                .to_string(),
            },
        ])
        .await;

        let settings = sample_cross_encoder_settings(server.endpoint(), 8);
        let transport = build_reranking_transport(&settings.transport).expect("transport");
        let reranker = CrossEncoderReranker::new(settings, transport).expect("valid settings");
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
                        sample_chunk("chunk-1", "alpha", "Doc 1", None, 0.8),
                        sample_chunk("chunk-2", "beta", "Doc 2", None, 0.7),
                    ],
                    metrics: None,
                    chunking_strategy: String::new(),
                },
            )
            .await
            .expect("cross encoder output");

        let requests = server.recorded_requests();
        assert_eq!(requests.len(), 2);
        assert_eq!(requests[1]["query"], "query");
        assert_eq!(requests[1]["texts"], json!(["alpha", "beta"]));
        assert!(requests[1].get("top_n").is_none());
        assert!(requests[1].get("instruction").is_none());
        assert_eq!(
            output
                .chunks
                .iter()
                .map(|chunk| chunk.chunk.chunk_id.as_str())
                .collect::<Vec<_>>(),
            vec!["chunk-2", "chunk-1"]
        );
        assert_eq!(output.total_tokens, Some(5));
    }
}

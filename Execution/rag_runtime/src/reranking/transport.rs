use async_trait::async_trait;

use crate::config::CrossEncoderTransportSettings;
use crate::errors::{RagRuntimeError, RerankingError};

use super::transports::{MixedbreadAiRerankingTransport, VoyageAiRerankingTransport};

pub type BoxedRerankingTransport = Box<dyn RerankingTransport + Send + Sync>;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RerankingTransportRequest {
    pub query: String,
    pub documents: Vec<String>,
    pub top_k: Option<usize>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct RerankingTransportResponse {
    pub results: Vec<RerankingTransportResult>,
    pub total_tokens: Option<usize>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct RerankingTransportResult {
    pub index: usize,
    pub score: f32,
}

#[async_trait]
pub trait RerankingTransport: Send + Sync {
    async fn rerank(
        &self,
        request: RerankingTransportRequest,
        settings: &CrossEncoderTransportSettings,
    ) -> Result<RerankingTransportResponse, RerankingError>;
}

pub fn build_reranking_transport(
    settings: &CrossEncoderTransportSettings,
) -> Result<BoxedRerankingTransport, RagRuntimeError> {
    match settings {
        CrossEncoderTransportSettings::MixedbreadAi(_) => {
            Ok(Box::new(MixedbreadAiRerankingTransport::default()))
        }
        CrossEncoderTransportSettings::VoyageAi(_) => Ok(Box::new(VoyageAiRerankingTransport)),
    }
}

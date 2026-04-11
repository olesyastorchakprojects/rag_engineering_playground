use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Duration;

use async_trait::async_trait;
use backon::{ExponentialBuilder, Retryable};
use serde_json::Value;

use crate::config::{GenerationSettings, RetryBackoff, RetrySettings, TransportSettings};
use crate::errors::{GenerationError, RagRuntimeError};
use crate::observability::record_retry_attempts;

use super::ollama::OllamaTransport;
use super::openai::OpenAiTransport;

pub type BoxedGenerationTransport = Box<dyn GenerationTransport + Send + Sync>;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ChatPrompt {
    pub system: String,
    pub user: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ModelAnswer {
    pub content: String,
    pub prompt_tokens: Option<usize>,
    pub completion_tokens: Option<usize>,
}

#[derive(Debug, Clone, Copy)]
pub struct GenerationTransportRuntime<'a> {
    pub retry: &'a RetrySettings,
    pub temperature: f32,
}

#[async_trait]
pub trait GenerationTransport: Send + Sync {
    async fn complete(
        &self,
        prompt: ChatPrompt,
        transport: &TransportSettings,
        runtime: GenerationTransportRuntime<'_>,
    ) -> Result<ModelAnswer, GenerationError>;
}

pub fn build_generation_transport(
    settings: &GenerationSettings,
) -> Result<BoxedGenerationTransport, RagRuntimeError> {
    match settings.transport {
        TransportSettings::Ollama(_) => Ok(Box::new(OllamaTransport::default())),
        TransportSettings::OpenAi(_) => Ok(Box::new(OpenAiTransport::default())),
    }
}

pub(crate) async fn retry_generation_with_policy<F, Fut, T>(
    settings: &RetrySettings,
    dependency: &'static str,
    operation: F,
) -> Result<(T, usize), GenerationError>
where
    F: Fn() -> Fut,
    Fut: std::future::Future<Output = Result<T, GenerationError>>,
{
    let failure_count = Arc::new(AtomicUsize::new(0));
    let builder = match settings.backoff {
        RetryBackoff::Exponential => ExponentialBuilder::default()
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
    result.map(|value| (value, retry_attempts))
}

pub(crate) fn parse_json_object(response_text: &str) -> Result<Value, GenerationError> {
    let parsed: Value = serde_json::from_str(response_text).map_err(|error| {
        GenerationError::ResponseValidation {
            message: format!("invalid json: {error}"),
        }
    })?;
    if !parsed.is_object() {
        return Err(GenerationError::ResponseValidation {
            message: "response body is not a json object".to_string(),
        });
    }
    Ok(parsed)
}

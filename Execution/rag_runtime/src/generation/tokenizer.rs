use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Duration;

use backon::{ExponentialBuilder, Retryable};
use reqwest::StatusCode;
use tokenizers::Tokenizer;

use crate::errors::GenerationError;
use crate::observability::record_retry_attempts;

const TOKENIZER_DOWNLOAD_TIMEOUT_SEC: u64 = 10;
const TOKENIZER_DOWNLOAD_MAX_ATTEMPTS: usize = 3;
const TOKENIZER_DOWNLOAD_MIN_DELAY_MS: u64 = 50;
const TOKENIZER_DOWNLOAD_MAX_DELAY_MS: u64 = 500;

#[derive(Debug)]
pub(crate) struct TokenizerResource {
    _artifact_bytes: Vec<u8>,
    tokenizer: Tokenizer,
}

impl TokenizerResource {
    pub(crate) fn count_tokens(&self, text: &str) -> Result<usize, GenerationError> {
        self.tokenizer
            .encode(text, true)
            .map(|encoding| encoding.len())
            .map_err(|error| GenerationError::TokenizerInitialization {
                message: format!("failed to encode text with generation tokenizer: {error}"),
            })
    }

    #[cfg(test)]
    pub(crate) fn from_test_bytes(bytes: &[u8]) -> Self {
        Self {
            _artifact_bytes: br#"{"model":{"type":"WordLevel"}}"#.to_vec(),
            tokenizer: Tokenizer::from_bytes(bytes).expect("test tokenizer json must be valid"),
        }
    }
}

pub(crate) async fn load_tokenizer_from_repo(
    repo_id: &str,
) -> Result<TokenizerResource, GenerationError> {
    let url = tokenizer_url(repo_id);
    load_tokenizer_from_url(url.as_str()).await
}

pub(crate) fn tokenizer_url(repo_id: &str) -> String {
    format!(
        "{}/{repo_id}/resolve/main/tokenizer.json",
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

pub(crate) async fn load_tokenizer_from_url(
    url: &str,
) -> Result<TokenizerResource, GenerationError> {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(TOKENIZER_DOWNLOAD_TIMEOUT_SEC))
        .build()
        .map_err(|error| GenerationError::TokenizerInitialization {
            message: format!("failed to build tokenizer download client: {error}"),
        })?;
    let failure_count = Arc::new(AtomicUsize::new(0));
    let builder = ExponentialBuilder::default()
        .with_factor(2.0)
        .with_min_delay(Duration::from_millis(TOKENIZER_DOWNLOAD_MIN_DELAY_MS))
        .with_max_delay(Duration::from_millis(TOKENIZER_DOWNLOAD_MAX_DELAY_MS))
        .with_jitter()
        .with_max_times(TOKENIZER_DOWNLOAD_MAX_ATTEMPTS);
    let url = url.to_string();
    let bytes: Vec<u8> = (|| {
        let client = client.clone();
        let url = url.clone();
        let failure_count = Arc::clone(&failure_count);
        async move {
            let value: Result<Vec<u8>, TokenizerDownloadError> =
                fetch_tokenizer_bytes(&client, &url).await;
            if value.is_err() {
                failure_count.fetch_add(1, Ordering::Relaxed);
            }
            value
        }
    })
    .retry(builder)
    .when(|error: &TokenizerDownloadError| error.is_retryable())
    .await
    .map_err(TokenizerDownloadError::into_generation_error)?;

    let retry_attempts = failure_count.load(Ordering::Relaxed).saturating_sub(1);
    if retry_attempts > 0 {
        record_retry_attempts("generation.tokenizer", retry_attempts);
    }

    let json: serde_json::Value = serde_json::from_slice(&bytes).map_err(|error| {
        GenerationError::TokenizerInitialization {
            message: format!("tokenizer artifact is not valid json: {error}"),
        }
    })?;
    if !json.is_object() || json.get("model").is_none() {
        return Err(GenerationError::TokenizerInitialization {
            message: "tokenizer artifact does not look like a tokenizer.json payload".to_string(),
        });
    }
    let tokenizer = Tokenizer::from_bytes(bytes.as_slice()).map_err(|error| {
        GenerationError::TokenizerInitialization {
            message: format!(
                "failed to construct generation tokenizer from artifact bytes: {error}"
            ),
        }
    })?;
    Ok(TokenizerResource {
        _artifact_bytes: bytes.to_vec(),
        tokenizer,
    })
}

#[derive(Debug)]
enum TokenizerDownloadError {
    Request(String),
    Status(StatusCode),
    ReadBody(String),
}

impl TokenizerDownloadError {
    fn is_retryable(&self) -> bool {
        match self {
            Self::Request(_) | Self::ReadBody(_) => true,
            Self::Status(status) => {
                *status == StatusCode::REQUEST_TIMEOUT
                    || *status == StatusCode::TOO_MANY_REQUESTS
                    || status.is_server_error()
            }
        }
    }

    fn into_generation_error(self) -> GenerationError {
        match self {
            Self::Request(message) => GenerationError::TokenizerInitialization {
                message: format!("request to tokenizer artifact failed: {message}"),
            },
            Self::Status(status) => GenerationError::TokenizerInitialization {
                message: format!("tokenizer artifact returned non-2xx status {status}"),
            },
            Self::ReadBody(message) => GenerationError::TokenizerInitialization {
                message: format!("failed to read tokenizer artifact bytes: {message}"),
            },
        }
    }
}

async fn fetch_tokenizer_bytes(
    client: &reqwest::Client,
    url: &str,
) -> Result<Vec<u8>, TokenizerDownloadError> {
    let response = client
        .get(url)
        .send()
        .await
        .map_err(|error| TokenizerDownloadError::Request(error.to_string()))?;
    if response.status() != StatusCode::OK {
        return Err(TokenizerDownloadError::Status(response.status()));
    }
    let bytes = response
        .bytes()
        .await
        .map_err(|error| TokenizerDownloadError::ReadBody(error.to_string()))?;
    Ok(bytes.to_vec())
}

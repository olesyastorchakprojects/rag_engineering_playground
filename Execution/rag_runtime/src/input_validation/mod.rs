use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Duration;
use std::time::Instant;

use backon::{ExponentialBuilder, Retryable};
use reqwest::StatusCode;
use serde_json::Value;
use tokenizers::Tokenizer;
use crate::config::InputValidationSettings;
use crate::errors::{InputValidationError, RagRuntimeError};
use crate::models::{UserRequest, ValidatedUserRequest};
use crate::observability::{
    StatusLabel, record_query_token_count, record_retry_attempts, record_stage_close,
};

const TOKENIZER_DOWNLOAD_TIMEOUT_SEC: u64 = 10;
const TOKENIZER_DOWNLOAD_MAX_ATTEMPTS: usize = 3;
const TOKENIZER_DOWNLOAD_MIN_DELAY_MS: u64 = 50;
const TOKENIZER_DOWNLOAD_MAX_DELAY_MS: u64 = 500;

#[derive(Debug, Clone)]
pub struct InputValidationEngine {
    settings: InputValidationSettings,
    tokenizer: Arc<TokenizerResource>,
}

#[derive(Debug)]
struct TokenizerResource {
    _artifact_bytes: Vec<u8>,
    tokenizer: Tokenizer,
}

#[cfg(test)]
const TEST_TOKENIZER_JSON: &[u8] = br#"{
  "version":"1.0",
  "truncation":null,
  "padding":null,
  "added_tokens":[],
  "normalizer":null,
  "pre_tokenizer":{"type":"Whitespace"},
  "post_processor":null,
  "decoder":null,
  "model":{"type":"WordLevel","vocab":{"[UNK]":0,"hello":1,"world":2,"one":3,"two":4,"alpha":5,"beta":6,"gamma":7,"delta":8},"unk_token":"[UNK]"}
}"#;

impl InputValidationEngine {
    pub async fn new(settings: InputValidationSettings) -> Result<Self, RagRuntimeError> {
        let tokenizer = load_tokenizer_from_repo(&settings.tokenizer_source)
            .await
            .map_err(RagRuntimeError::from)?;
        Ok(Self {
            settings,
            tokenizer: Arc::new(tokenizer),
        })
    }

    pub async fn validate(
        &self,
        request: UserRequest,
    ) -> Result<ValidatedUserRequest, RagRuntimeError> {
        let started = Instant::now();
        let result: Result<ValidatedUserRequest, RagRuntimeError> = {
            let mut query = request.query;
            if self.settings.trim_whitespace {
                query = query.trim().to_string();
            }
            if self.settings.collapse_internal_whitespace {
                query = query.split_whitespace().collect::<Vec<_>>().join(" ");
            }
            let normalized_query_length = query.len();
            if self.settings.reject_empty_query && query.is_empty() {
                Err(InputValidationError::EmptyQuery.into())
            } else {
                let token_count = self.tokenizer.count_tokens(&query)?;
                record_query_token_count(token_count);
                if token_count > self.settings.max_query_tokens {
                    Err(InputValidationError::QueryTooLong {
                        actual: token_count,
                        max_allowed: self.settings.max_query_tokens,
                    }
                    .into())
                } else {
                    Ok(ValidatedUserRequest {
                        query,
                        input_token_count: token_count,
                        trim_whitespace_applied: self.settings.trim_whitespace,
                        collapse_internal_whitespace_applied: self.settings.collapse_internal_whitespace,
                        normalized_query_length,
                        tokenizer_source: self.settings.tokenizer_source.clone(),
                    })
                }
            }
        };
        let status = if result.is_err() {
            StatusLabel::Error
        } else {
            StatusLabel::Ok
        };
        record_stage_close(
            "input_validation",
            "input_validation",
            started.elapsed().as_secs_f64() * 1000.0,
            status,
        );
        result
    }

    #[cfg(test)]
    pub fn for_tests(settings: InputValidationSettings) -> Self {
        Self {
            settings,
            tokenizer: Arc::new(TokenizerResource {
                _artifact_bytes: br#"{"model":{"type":"WordLevel"}}"#.to_vec(),
                tokenizer: Tokenizer::from_bytes(TEST_TOKENIZER_JSON)
                    .expect("test tokenizer json must be valid"),
            }),
        }
    }
}

impl TokenizerResource {
    fn count_tokens(&self, text: &str) -> Result<usize, InputValidationError> {
        self.tokenizer
            .encode(text, true)
            .map(|encoding| encoding.len())
            .map_err(|error| InputValidationError::TokenizerInitialization {
                message: format!("failed to encode query with tokenizer: {error}"),
            })
    }
}

async fn load_tokenizer_from_repo(
    repo_id: &str,
) -> Result<TokenizerResource, InputValidationError> {
    let url = tokenizer_url(repo_id);
    load_tokenizer_from_url(&url).await
}

fn tokenizer_url(repo_id: &str) -> String {
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

async fn load_tokenizer_from_url(url: &str) -> Result<TokenizerResource, InputValidationError> {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(TOKENIZER_DOWNLOAD_TIMEOUT_SEC))
        .build()
        .map_err(|error| InputValidationError::TokenizerInitialization {
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
    .map_err(TokenizerDownloadError::into_input_validation_error)?;

    let retry_attempts = failure_count.load(Ordering::Relaxed).saturating_sub(1);
    if retry_attempts > 0 {
        record_retry_attempts("input_validation.tokenizer", retry_attempts);
    }

    let json: Value = serde_json::from_slice(&bytes).map_err(|error| {
        InputValidationError::TokenizerInitialization {
            message: format!("tokenizer artifact is not valid json: {error}"),
        }
    })?;
    if !json.is_object() || json.get("model").is_none() {
        return Err(InputValidationError::TokenizerInitialization {
            message: "tokenizer artifact does not look like a tokenizer.json payload".to_string(),
        });
    }
    let tokenizer = Tokenizer::from_bytes(bytes.as_slice()).map_err(|error| {
        InputValidationError::TokenizerInitialization {
            message: format!("failed to construct tokenizer from artifact bytes: {error}"),
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

    fn into_input_validation_error(self) -> InputValidationError {
        match self {
            Self::Request(message) => InputValidationError::TokenizerInitialization {
                message: format!("request to tokenizer artifact failed: {message}"),
            },
            Self::Status(status) => InputValidationError::TokenizerInitialization {
                message: format!("tokenizer artifact returned non-2xx status {status}"),
            },
            Self::ReadBody(message) => InputValidationError::TokenizerInitialization {
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

#[cfg(test)]
mod tests {
    use super::*;
    use axum::http::StatusCode;

    use crate::test_support::{MockHttpResponse, MockHttpServer, test_settings};

    fn settings_with_flags(
        trim_whitespace: bool,
        collapse_internal_whitespace: bool,
    ) -> InputValidationSettings {
        InputValidationSettings {
            trim_whitespace,
            collapse_internal_whitespace,
            ..test_settings().input_validation
        }
    }

    #[tokio::test]
    async fn non_empty_query_passes_validation() {
        let engine = InputValidationEngine::for_tests(test_settings().input_validation);
        let validated = engine
            .validate(UserRequest {
                query: "hello world".to_string(),
            })
            .await
            .unwrap();
        assert_eq!(validated.query, "hello world");
    }

    #[tokio::test]
    async fn whitespace_only_query_is_rejected() {
        let engine = InputValidationEngine::for_tests(test_settings().input_validation);
        let error = engine
            .validate(UserRequest {
                query: "   ".to_string(),
            })
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "input_validation.empty_query");
    }

    #[tokio::test]
    async fn leading_and_trailing_whitespace_is_removed() {
        let engine = InputValidationEngine::for_tests(settings_with_flags(true, false));
        let validated = engine
            .validate(UserRequest {
                query: "  hello world  ".to_string(),
            })
            .await
            .unwrap();
        assert_eq!(validated.query, "hello world");
    }

    #[tokio::test]
    async fn repeated_internal_whitespace_is_collapsed() {
        let engine = InputValidationEngine::for_tests(settings_with_flags(false, true));
        let validated = engine
            .validate(UserRequest {
                query: "hello   world".to_string(),
            })
            .await
            .unwrap();
        assert_eq!(validated.query, "hello world");
    }

    #[tokio::test]
    async fn normalization_can_be_disabled() {
        let engine = InputValidationEngine::for_tests(settings_with_flags(false, false));
        let validated = engine
            .validate(UserRequest {
                query: "  hello   world  ".to_string(),
            })
            .await
            .unwrap();
        assert_eq!(validated.query, "  hello   world  ");
    }

    #[tokio::test]
    async fn query_exactly_at_token_limit_passes() {
        let mut settings = test_settings().input_validation;
        settings.max_query_tokens = 2;
        let engine = InputValidationEngine::for_tests(settings);
        let validated = engine
            .validate(UserRequest {
                query: "hello world".to_string(),
            })
            .await
            .unwrap();
        assert_eq!(validated.query, "hello world");
    }

    #[tokio::test]
    async fn query_above_token_limit_fails() {
        let mut settings = test_settings().input_validation;
        settings.max_query_tokens = 1;
        let engine = InputValidationEngine::for_tests(settings);
        let error = engine
            .validate(UserRequest {
                query: "hello world".to_string(),
            })
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "input_validation.query_too_long");
    }

    #[tokio::test]
    async fn normalized_empty_query_fails() {
        let engine = InputValidationEngine::for_tests(test_settings().input_validation);
        let error = engine
            .validate(UserRequest {
                query: " \n\t ".to_string(),
            })
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "input_validation.empty_query");
    }

    #[tokio::test]
    async fn identical_inputs_produce_same_output() {
        let engine = InputValidationEngine::for_tests(test_settings().input_validation);
        let first = engine
            .validate(UserRequest {
                query: "hello   world".to_string(),
            })
            .await
            .unwrap();
        let second = engine
            .validate(UserRequest {
                query: "hello   world".to_string(),
            })
            .await
            .unwrap();
        assert_eq!(first, second);
    }

    #[tokio::test]
    async fn tokenizer_init_fails_when_artifact_cannot_be_loaded() {
        let error = load_tokenizer_from_url("http://127.0.0.1:9/missing")
            .await
            .unwrap_err();
        assert_eq!(
            error.error_type(),
            "input_validation.tokenizer_initialization"
        );
    }

    #[tokio::test]
    async fn tokenizer_init_fails_on_non_2xx() {
        let server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::BAD_GATEWAY,
            body: "{}".to_string(),
        }])
        .await;
        let error = load_tokenizer_from_url(&server.endpoint())
            .await
            .unwrap_err();
        assert_eq!(
            error.error_type(),
            "input_validation.tokenizer_initialization"
        );
    }

    #[tokio::test]
    async fn tokenizer_init_fails_on_invalid_bytes() {
        let server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: "not-json".to_string(),
        }])
        .await;
        let error = load_tokenizer_from_url(&server.endpoint())
            .await
            .unwrap_err();
        assert_eq!(
            error.error_type(),
            "input_validation.tokenizer_initialization"
        );
    }

    #[tokio::test]
    async fn empty_query_is_allowed_when_reject_flag_disabled() {
        let mut settings = test_settings().input_validation;
        settings.reject_empty_query = false;
        let engine = InputValidationEngine::for_tests(settings);
        let validated = engine
            .validate(UserRequest {
                query: "   ".to_string(),
            })
            .await
            .unwrap();
        assert_eq!(validated.query, "");
    }

    #[tokio::test]
    async fn trim_and_collapse_apply_in_order() {
        let engine = InputValidationEngine::for_tests(test_settings().input_validation);
        let validated = engine
            .validate(UserRequest {
                query: "  hello   brave   world  ".to_string(),
            })
            .await
            .unwrap();
        assert_eq!(validated.query, "hello brave world");
    }

    #[tokio::test]
    async fn tokenizer_init_fails_when_json_missing_model() {
        let server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: "{}".to_string(),
        }])
        .await;
        let error = load_tokenizer_from_url(&server.endpoint())
            .await
            .unwrap_err();
        assert_eq!(
            error.error_type(),
            "input_validation.tokenizer_initialization"
        );
    }

    #[tokio::test]
    async fn tokenizer_init_succeeds_for_valid_tokenizer_payload() {
        let server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: std::str::from_utf8(TEST_TOKENIZER_JSON)
                .unwrap()
                .to_string(),
        }])
        .await;
        let tokenizer = load_tokenizer_from_url(&format!("{}/tokenizer.json", server.endpoint()))
            .await
            .unwrap();
        assert_eq!(tokenizer.count_tokens("one two").unwrap(), 2);
    }

    #[test]
    fn tokenizer_repo_url_matches_expected_huggingface_path() {
        assert_eq!(
            tokenizer_url("org/tokenizer"),
            "https://huggingface.co/org/tokenizer/resolve/main/tokenizer.json"
        );
    }

    #[tokio::test]
    async fn tokenizer_init_retries_retryable_status_and_recovers() {
        let server = MockHttpServer::start(vec![
            MockHttpResponse {
                status: StatusCode::GATEWAY_TIMEOUT,
                body: "{}".to_string(),
            },
            MockHttpResponse {
                status: StatusCode::OK,
                body: std::str::from_utf8(TEST_TOKENIZER_JSON)
                    .unwrap()
                    .to_string(),
            },
        ])
        .await;

        let tokenizer = load_tokenizer_from_url(&format!("{}/tokenizer.json", server.endpoint()))
            .await
            .unwrap();

        assert_eq!(tokenizer.count_tokens("one two").unwrap(), 2);
        assert_eq!(server.recorded_paths().len(), 2);
    }

    #[test]
    fn tokenizer_counts_tokens_with_real_tokenizer() {
        let tokenizer = TokenizerResource {
            _artifact_bytes: Vec::new(),
            tokenizer: Tokenizer::from_bytes(TEST_TOKENIZER_JSON).unwrap(),
        };
        assert_eq!(
            tokenizer
                .count_tokens("alpha   beta\tgamma\n delta")
                .unwrap(),
            4
        );
    }
}

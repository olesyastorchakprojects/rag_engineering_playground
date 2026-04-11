#![cfg(test)]

use std::collections::HashMap;
use std::collections::VecDeque;
use std::env;
use std::net::SocketAddr;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex, OnceLock};

use axum::Router;
use axum::extract::OriginalUri;
use axum::extract::State;
use axum::http::HeaderMap;
use axum::http::StatusCode;
use axum::routing::any;
use serde_json::Value;
use tokio::net::TcpListener;

use crate::config::{
    CrossEncoderRerankerSettings, CrossEncoderTransportSettings, DenseRetrievalIngest,
    GenerationSettings, HeuristicRerankerSettings, HeuristicWeights, InputValidationSettings,
    MixedbreadAiCrossEncoderTransportSettings, ObservabilitySettings, OllamaTransportSettings,
    PipelineSettings, RequestCaptureSettings, RerankerSettings, RerankingSettings, RetrievalIngest,
    RetrievalKind, RetrievalSettings, RetryBackoff, RetrySettings, Settings, TransportSettings,
};

#[derive(Debug, Clone)]
pub struct MockHttpResponse {
    pub status: StatusCode,
    pub body: String,
}

#[derive(Clone)]
struct MockServerState {
    responses: Arc<Mutex<VecDeque<MockHttpResponse>>>,
    requests: Arc<Mutex<Vec<Value>>>,
    paths: Arc<Mutex<Vec<String>>>,
    headers: Arc<Mutex<Vec<HashMap<String, String>>>>,
}

pub struct MockHttpServer {
    address: SocketAddr,
    requests: Arc<Mutex<Vec<Value>>>,
    paths: Arc<Mutex<Vec<String>>>,
    headers: Arc<Mutex<Vec<HashMap<String, String>>>>,
    join_handle: tokio::task::JoinHandle<()>,
}

impl MockHttpServer {
    pub async fn start(responses: Vec<MockHttpResponse>) -> Self {
        let state = MockServerState {
            responses: Arc::new(Mutex::new(VecDeque::from(responses))),
            requests: Arc::new(Mutex::new(Vec::new())),
            paths: Arc::new(Mutex::new(Vec::new())),
            headers: Arc::new(Mutex::new(Vec::new())),
        };

        let app = Router::new()
            .route("/{*path}", any(handler))
            .with_state(state.clone());

        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let address = listener.local_addr().unwrap();
        let join_handle = tokio::spawn(async move {
            axum::serve(listener, app).await.unwrap();
        });

        Self {
            address,
            requests: state.requests,
            paths: state.paths,
            headers: state.headers,
            join_handle,
        }
    }

    pub fn endpoint(&self) -> String {
        format!("http://{}", self.address)
    }

    pub fn recorded_requests(&self) -> Vec<Value> {
        self.requests.lock().unwrap().clone()
    }

    pub fn recorded_paths(&self) -> Vec<String> {
        self.paths.lock().unwrap().clone()
    }

    pub fn recorded_headers(&self) -> Vec<HashMap<String, String>> {
        self.headers.lock().unwrap().clone()
    }
}

impl Drop for MockHttpServer {
    fn drop(&mut self) {
        self.join_handle.abort();
    }
}

async fn handler(
    State(state): State<MockServerState>,
    uri: OriginalUri,
    headers: HeaderMap,
    body: String,
) -> (StatusCode, String) {
    let parsed = serde_json::from_str::<Value>(&body).unwrap_or_else(|_| Value::String(body));
    state.requests.lock().unwrap().push(parsed);
    state.paths.lock().unwrap().push(uri.0.path().to_string());
    state.headers.lock().unwrap().push(
        headers
            .iter()
            .filter_map(|(name, value)| {
                value
                    .to_str()
                    .ok()
                    .map(|v| (name.to_string(), v.to_string()))
            })
            .collect(),
    );
    let response = state
        .responses
        .lock()
        .unwrap()
        .pop_front()
        .unwrap_or(MockHttpResponse {
            status: StatusCode::OK,
            body: "{}".to_string(),
        });
    (response.status, response.body)
}

pub fn test_settings() -> Settings {
    Settings {
        pipeline: PipelineSettings {
            config_version: "v1".to_string(),
        },
        input_validation: InputValidationSettings {
            max_query_tokens: 128,
            tokenizer_source: "test/input".to_string(),
            reject_empty_query: true,
            trim_whitespace: true,
            collapse_internal_whitespace: true,
        },
        retrieval: RetrievalSettings {
            kind: RetrievalKind::Dense,
            ollama_url: "http://127.0.0.1:9".to_string(),
            qdrant_url: "http://127.0.0.1:9".to_string(),
            retriever_version: "v1".to_string(),
            top_k: 3,
            score_threshold: 0.2,
            embedding_retry: RetrySettings {
                max_attempts: 3,
                backoff: RetryBackoff::Exponential,
            },
            qdrant_retry: RetrySettings {
                max_attempts: 3,
                backoff: RetryBackoff::Exponential,
            },
            ingest: RetrievalIngest::Dense(DenseRetrievalIngest {
                embedding_model_name: "qwen3-embedding:0.6b".to_string(),
                embedding_dimension: 3,
                qdrant_collection_name: "chunks_dense_qwen3".to_string(),
                qdrant_vector_name: "default".to_string(),
                corpus_version: "v1".to_string(),
            }),
        },
        generation: GenerationSettings {
            transport: TransportSettings::Ollama(OllamaTransportSettings {
                url: "http://127.0.0.1:9".to_string(),
                model_name: "qwen2.5:1.5b-instruct-q4_K_M".to_string(),
                timeout_sec: 90,
                input_cost_per_million_tokens: 0.0,
                output_cost_per_million_tokens: 0.0,
            }),
            tokenizer_source: "test/generation".to_string(),
            temperature: 0.0,
            max_context_chunks: 5,
            max_prompt_tokens: 1024,
            retry: RetrySettings {
                max_attempts: 3,
                backoff: RetryBackoff::Exponential,
            },
        },
        reranking: RerankingSettings {
            reranker: RerankerSettings::PassThrough,
            candidate_k: 3,
            final_k: 5,
        },
        observability: disabled_observability_settings(),
        request_capture: RequestCaptureSettings {
            postgres_url: "postgres://postgres:postgres@127.0.0.1:5432/rag_eval".to_string(),
        },
    }
}

pub fn test_cross_encoder_reranking_settings() -> RerankingSettings {
    RerankingSettings {
        reranker: RerankerSettings::CrossEncoder(CrossEncoderRerankerSettings {
            transport: CrossEncoderTransportSettings::MixedbreadAi(
                MixedbreadAiCrossEncoderTransportSettings {
                    url: "http://127.0.0.1:8081".to_string(),
                    model_name: "mixedbread-ai/mxbai-rerank-base-v2".to_string(),
                    batch_size: 12,
                    timeout_sec: 120,
                    cost_per_million_tokens: 0.0,
                    tokenizer_source: "mixedbread-ai/mxbai-rerank-base-v2".to_string(),
                    max_attempts: 3,
                    backoff: RetryBackoff::Exponential,
                },
            ),
        }),
        candidate_k: 3,
        final_k: 5,
    }
}

pub fn test_heuristic_reranking_settings() -> RerankingSettings {
    RerankingSettings {
        reranker: RerankerSettings::Heuristic(HeuristicRerankerSettings {
            weights: HeuristicWeights {
                retrieval_score: 1.0,
                query_term_coverage: 1.0,
                phrase_match_bonus: 1.0,
                title_section_match_bonus: 1.0,
            },
        }),
        candidate_k: 3,
        final_k: 5,
    }
}

pub fn disabled_observability_settings() -> ObservabilitySettings {
    ObservabilitySettings {
        tracing_enabled: false,
        metrics_enabled: false,
        tracing_endpoint: "http://127.0.0.1:4317".to_string(),
        metrics_endpoint: "http://127.0.0.1:4317".to_string(),
        trace_batch_scheduled_delay_ms: 10,
        metrics_export_interval_ms: 10,
    }
}

pub fn env_lock() -> &'static Mutex<()> {
    static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
    LOCK.get_or_init(|| Mutex::new(()))
}

pub struct TempEnvVar {
    key: String,
    previous: Option<String>,
}

impl TempEnvVar {
    pub fn set(key: impl Into<String>, value: impl Into<String>) -> Self {
        let key = key.into();
        let previous = env::var(&key).ok();
        unsafe { env::set_var(&key, value.into()) };
        Self { key, previous }
    }

    pub fn remove(key: impl Into<String>) -> Self {
        let key = key.into();
        let previous = env::var(&key).ok();
        unsafe { env::remove_var(&key) };
        Self { key, previous }
    }
}

impl Drop for TempEnvVar {
    fn drop(&mut self) {
        match &self.previous {
            Some(value) => unsafe { env::set_var(&self.key, value) },
            None => unsafe { env::remove_var(&self.key) },
        }
    }
}

pub struct CurrentDirGuard {
    previous: PathBuf,
}

impl CurrentDirGuard {
    pub fn change_to(path: impl AsRef<Path>) -> Self {
        let previous = env::current_dir().expect("current dir");
        env::set_current_dir(path.as_ref()).expect("set current dir");
        Self { previous }
    }
}

impl Drop for CurrentDirGuard {
    fn drop(&mut self) {
        env::set_current_dir(&self.previous).expect("restore current dir");
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn temp_env_var_remove_restores_previous_value() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        unsafe { env::set_var("RAG_RUNTIME_TEST_TEMP_ENV", "before") };
        {
            let _temp = TempEnvVar::remove("RAG_RUNTIME_TEST_TEMP_ENV");
            assert!(env::var("RAG_RUNTIME_TEST_TEMP_ENV").is_err());
        }
        assert_eq!(
            env::var("RAG_RUNTIME_TEST_TEMP_ENV").unwrap(),
            "before".to_string()
        );
        unsafe { env::remove_var("RAG_RUNTIME_TEST_TEMP_ENV") };
    }

    #[test]
    fn current_dir_guard_restores_previous_directory() {
        let original = env::current_dir().unwrap();
        let tempdir = tempfile::tempdir().unwrap();
        {
            let _guard = CurrentDirGuard::change_to(tempdir.path());
            assert_eq!(env::current_dir().unwrap(), tempdir.path());
        }
        assert_eq!(env::current_dir().unwrap(), original);
    }
}

pub mod config;
pub mod errors;
pub mod generation;
pub mod input_validation;
pub mod models;
pub mod observability;
pub mod orchestration;
pub mod request_capture_store;
pub mod reranking;
pub mod retrieval;
pub mod retrieval_metrics;
pub mod runtime_run_config_store;

pub use orchestration::load_golden_companion;

#[cfg(test)]
mod test_support;

use std::path::Path;

use config::Settings;
use errors::RagRuntimeError;
use generation::{GenerationEngine, build_generation_transport};
use input_validation::InputValidationEngine;
use models::{UserRequest, UserResponse};
use observability::{ObservabilityRuntime, mark_span_ok};
use orchestration::OrchestrationEngine;
use tracing::{Instrument, field, info_span};
use uuid::Uuid;

use crate::runtime_run_config_store::RuntimeRunConfigStore;

pub struct RagRuntime {
    runtime_run_id: String,
    settings: Settings,
    orchestrator: OrchestrationEngine,
    observability: ObservabilityRuntime,
}
#[tracing::instrument(name = "Service::session::add", skip_all)]
pub async fn test_instrumented_span() {
    tracing::info!(session_id = "asdasd", "create session");
}

impl RagRuntime {
    pub async fn from_config_paths(
        rag_runtime_config_path: impl AsRef<Path>,
        ingest_config_path: impl AsRef<Path>,
    ) -> Result<Self, RagRuntimeError> {
        let settings = config::load_settings(rag_runtime_config_path, ingest_config_path).await?;
        let observability = ObservabilityRuntime::initialize(&settings.observability)?;
        let runtime_run_id = Uuid::new_v4().to_string();
        let input_validation_span = info_span!(
            "startup.input_validation_init",
            "span.module" = "startup",
            "span.stage" = "input_validation_init",
            status = field::Empty,
            "error.type" = field::Empty,
            "error.message" = field::Empty,
            tokenizer_source = %settings.input_validation.tokenizer_source,
        );
        let input_validation = match InputValidationEngine::new(settings.input_validation.clone())
            .instrument(input_validation_span.clone())
            .await
        {
            Ok(engine) => {
                input_validation_span.in_scope(mark_span_ok);
                engine
            }
            Err(error) => {
                input_validation_span.record("error.type", error.error_type());
                input_validation_span.record("error.message", field::display(error.to_string()));
                observability.flush();
                return Err(error);
            }
        };

        let generation_span = info_span!(
            "startup.generation_init",
            "span.module" = "startup",
            "span.stage" = "generation_init",
            status = field::Empty,
            "error.type" = field::Empty,
            "error.message" = field::Empty,
            tokenizer_source = %settings.generation.tokenizer_source,
            transport_kind = %match &settings.generation.transport {
                config::TransportSettings::Ollama(_) => "ollama",
                config::TransportSettings::OpenAi(_) => "openai",
            },
            model_name = %settings.generation.transport_model_name(),
        );
        let generation = match GenerationEngine::new(
            build_generation_transport(&settings.generation)?,
            settings.generation.clone(),
        )
        .instrument(generation_span.clone())
        .await
        {
            Ok(engine) => {
                generation_span.in_scope(mark_span_ok);
                engine
            }
            Err(error) => {
                generation_span.record("error.type", error.error_type());
                generation_span.record("error.message", field::display(error.to_string()));
                observability.flush();
                return Err(error);
            }
        };
        let orchestrator = OrchestrationEngine::new(input_validation, generation, &settings)?;
        if let Err(error) = RuntimeRunConfigStore::store(&runtime_run_id, &settings).await {
            tracing::warn!(
                error_type = error.error_type(),
                error_message = %error,
                runtime_run_id = %runtime_run_id,
                "runtime_run_config_persistence_failed"
            );
        }

        Ok(Self {
            runtime_run_id,
            settings,
            orchestrator,
            observability,
        })
    }

    pub async fn handle_request(
        &self,
        request: UserRequest,
    ) -> Result<UserResponse, RagRuntimeError> {
        self.orchestrator
            .handle_request(&self.settings, &self.runtime_run_id, request)
            .await
    }

    /// Load a golden retrieval companion file and attach it to the runtime for
    /// evaluated batch execution. Validates that every question in
    /// `batch_questions` has a matching companion entry before returning.
    pub async fn with_golden_companion(
        mut self,
        golden_path: impl AsRef<std::path::Path>,
        batch_questions: &[String],
    ) -> Result<Self, RagRuntimeError> {
        let lookup = load_golden_companion(golden_path, batch_questions).await?;
        self.orchestrator.set_golden_lookup(lookup);
        Ok(self)
    }

    pub fn flush_observability(&self) {
        self.observability.flush();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::http::StatusCode;
    use serde_json::json;
    use std::env;
    use std::fs;

    use crate::models::UserRequest;
    use crate::test_support::{MockHttpResponse, MockHttpServer, TempEnvVar, env_lock};

    #[tokio::test]
    async fn handle_request_propagates_downstream_failure() {
        let runtime = RagRuntime {
            runtime_run_id: "runtime-run-test".to_string(),
            settings: crate::test_support::test_settings(),
            orchestrator: OrchestrationEngine::failing_for_tests(),
            observability: ObservabilityRuntime::disabled_for_tests(),
        };

        let error = runtime
            .handle_request(UserRequest {
                query: "question".to_string(),
            })
            .await
            .unwrap_err();

        assert_eq!(error.error_type(), "orchestration.empty_retrieval_output");
    }

    #[tokio::test]
    async fn handle_request_returns_successful_user_response() {
        let embedding = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"embeddings":[[0.1,0.2,0.3]]}).to_string(),
        }])
        .await;
        let qdrant = MockHttpServer::start(vec![
            MockHttpResponse {
                status: StatusCode::OK,
                body: json!({
                    "result": {
                        "config": {
                            "metadata": {
                                "chunking_strategy": "structural"
                            }
                        }
                    }
                })
                .to_string(),
            },
            MockHttpResponse {
                status: StatusCode::OK,
                body: json!({"result":{"points":[{"score":0.9,"payload":{
                    "schema_version":1,
                    "doc_id":"doc-1",
                    "chunk_id":"chunk-1",
                    "url":"local://doc",
                    "document_title":"Doc",
                    "section_title":"Section",
                    "section_path":["Section"],
                    "chunk_index":0,
                    "page_start":1,
                    "page_end":1,
                    "tags":["tag"],
                    "content_hash":"sha256:abc",
                    "chunking_version":"v1",
                    "chunk_created_at":"2026-01-01T00:00:00Z",
                    "text":"chunk text"
                }}]}})
                .to_string(),
            },
        ])
        .await;
        let chat = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"message":{"content":"answer"}}).to_string(),
        }])
        .await;

        let mut settings = crate::test_support::test_settings();
        settings.retrieval.ollama_url = embedding.endpoint();
        settings.retrieval.qdrant_url = qdrant.endpoint();
        match &mut settings.generation.transport {
            crate::config::TransportSettings::Ollama(transport) => {
                transport.url = chat.endpoint();
            }
            crate::config::TransportSettings::OpenAi(transport) => {
                transport.url = chat.endpoint();
            }
        }

        let runtime = RagRuntime {
            runtime_run_id: "runtime-run-test".to_string(),
            orchestrator: OrchestrationEngine::from_parts(
                InputValidationEngine::for_tests(settings.input_validation.clone()),
                GenerationEngine::for_tests(settings.generation.clone()),
                &settings,
            )
            .unwrap(),
            settings,
            observability: ObservabilityRuntime::disabled_for_tests(),
        };

        let response = runtime
            .handle_request(UserRequest {
                query: "question".to_string(),
            })
            .await
            .unwrap();
        assert_eq!(response.answer, "answer");
    }

    #[tokio::test]
    async fn from_config_paths_reports_startup_failure_without_required_env() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let dir = tempfile::tempdir().unwrap();
        let runtime_config = dir.path().join("rag_runtime.toml");
        let ingest_config = dir.path().join("ingest.toml");
        fs::write(
            &runtime_config,
            fs::read_to_string(
                "/home/olesia/code/prompt_gen_proj/Execution/rag_runtime/rag_runtime.toml",
            )
            .unwrap(),
        )
        .unwrap();
        fs::write(
            &ingest_config,
            fs::read_to_string(
                "/home/olesia/code/prompt_gen_proj/Execution/ingest/dense/ingest.toml",
            )
            .unwrap(),
        )
        .unwrap();
        unsafe { env::set_var("RAG_RUNTIME_SKIP_DOTENV", "1") };
        unsafe { env::remove_var("OLLAMA_URL") };
        unsafe { env::remove_var("QDRANT_URL") };
        unsafe { env::remove_var("TRACING_ENDPOINT") };
        unsafe { env::remove_var("METRICS_ENDPOINT") };

        match RagRuntime::from_config_paths(&runtime_config, &ingest_config).await {
            Ok(_) => panic!("expected startup failure"),
            Err(error) => assert!(matches!(
                error.error_type(),
                "rag_runtime.startup" | "observability.initialization"
            )),
        }

        unsafe { env::remove_var("RAG_RUNTIME_SKIP_DOTENV") };
    }

    #[tokio::test]
    async fn from_config_paths_constructs_runnable_runtime_from_valid_inputs() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let dir = tempfile::tempdir().unwrap();
        let runtime_config = dir.path().join("rag_runtime.toml");
        let ingest_config = dir.path().join("ingest.toml");
        let runtime_config_text = fs::read_to_string(
            "/home/olesia/code/prompt_gen_proj/Execution/rag_runtime/rag_runtime.toml",
        )
        .unwrap()
        .replace("tracing_enabled = true", "tracing_enabled = false")
        .replace("metrics_enabled = true", "metrics_enabled = false")
        .replace("top_k = 12", "top_k = 4")
        .replace("max_context_chunks = 4", "max_context_chunks = 12");
        fs::write(&runtime_config, runtime_config_text).unwrap();
        fs::write(
            &ingest_config,
            fs::read_to_string(
                "/home/olesia/code/prompt_gen_proj/Execution/ingest/dense/ingest.toml",
            )
            .unwrap(),
        )
        .unwrap();

        let tokenizer_server = MockHttpServer::start(vec![
            MockHttpResponse {
                status: StatusCode::OK,
                body: r#"{"version":"1.0","truncation":null,"padding":null,"added_tokens":[],"normalizer":null,"pre_tokenizer":{"type":"Whitespace"},"post_processor":null,"decoder":null,"model":{"type":"WordLevel","vocab":{"[UNK]":0,"question":1},"unk_token":"[UNK]"}}"#.to_string(),
            },
            MockHttpResponse {
                status: StatusCode::OK,
                body: r#"{"version":"1.0","truncation":null,"padding":null,"added_tokens":[],"normalizer":null,"pre_tokenizer":{"type":"Whitespace"},"post_processor":null,"decoder":null,"model":{"type":"WordLevel","vocab":{"[UNK]":0,"question":1},"unk_token":"[UNK]"}}"#.to_string(),
            },
        ])
        .await;

        let _skip_dotenv = TempEnvVar::set("RAG_RUNTIME_SKIP_DOTENV", "1");
        let _ollama = TempEnvVar::set("OLLAMA_URL", "http://ollama.test");
        let _qdrant = TempEnvVar::set("QDRANT_URL", "http://qdrant.test");
        let _postgres = TempEnvVar::set(
            "POSTGRES_URL",
            "postgres://postgres:postgres@localhost:5432/rag_eval",
        );
        let _tracing = TempEnvVar::set("TRACING_ENDPOINT", "http://trace.test");
        let _metrics = TempEnvVar::set("METRICS_ENDPOINT", "http://metrics.test");
        let _reranker = TempEnvVar::set("RERANKER_ENDPOINT", "http://reranker.test");
        let _hf_base = TempEnvVar::set("RAG_RUNTIME_TEST_HF_BASE_URL", tokenizer_server.endpoint());

        let runtime = RagRuntime::from_config_paths(&runtime_config, &ingest_config)
            .await
            .unwrap();
        let response = runtime
            .handle_request(UserRequest {
                query: "question".to_string(),
            })
            .await;
        assert!(response.is_err());

        assert_eq!(tokenizer_server.recorded_requests().len(), 2);
    }
}

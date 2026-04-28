mod ollama;
mod openai;
pub(crate) mod tokenizer;
mod transport;

use std::sync::Arc;
use std::time::Instant;

use tracing::{Instrument, field, info_span};

use crate::config::{GenerationSettings, TransportSettings};
use crate::errors::{GenerationError, RagRuntimeError};
use crate::models::{GenerationRequest, GenerationResponse, RetrievedChunk};
use crate::observability::{
    StatusLabel, mark_span_ok, record_dependency_close, record_generation_completion_tokens,
    record_generation_cost_total, record_generation_input_chunk_count,
    record_generation_prompt_tokens, record_stage_close,
};

pub use ollama::OllamaTransport;
pub use openai::OpenAiTransport;
use tokenizer::{TokenizerResource, load_tokenizer_from_repo};
pub use transport::{
    BoxedGenerationTransport, ChatPrompt, GenerationTransport, GenerationTransportRuntime,
    ModelAnswer, build_generation_transport,
};

pub(crate) const PROMPT_TEMPLATE_ID: &str = "rag_runtime.default";
pub(crate) const PROMPT_TEMPLATE_VERSION: &str = "v1";
const SYSTEM_PROMPT: &str = "You are a documentation assistant.\nYou MUST answer using ONLY the provided context chunks.\nIf the answer is not explicitly supported by the context, say: \"I don't know based on the provided docs.\" and stop.\nDo not use general knowledge.\nEvery factual claim must have a citation using only a page label that appears in the provided context chunks.\nDo not invent page labels.\nIf you cannot cite a claim, do not make it.\nLanguage: match the user's language.\n";
const USER_PROMPT_TEMPLATE: &str = "Question:\n{{question}}\n\nContext chunks:\n{{context_chunks}}\n\nInstructions:\n- First, restate the question in one short sentence in your own words.\n- Restate the question without changing its intent. If the user asks for meaning or definition, restate it as a definition question.\n- Use only the context.\n- Cite sources using only page labels that appear in the context chunks, after the relevant sentences.\n- Do not invent page labels.\n- If multiple chunks disagree, mention the ambiguity.\n- Prefer citing the single most relevant chunk per claim; do not cite multiple chunks unless necessary.\n- Do NOT add disclaimers like \"not explicitly stated\" if the context clearly answers the question.\n- Use the exact terms from the context; do not substitute terms with related concepts unless a chunk explicitly does so.\n";

pub type GenerationEngine = Generator;

pub struct Generator {
    transport: BoxedGenerationTransport,
    settings: GenerationSettings,
    tokenizer: Arc<TokenizerResource>,
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
  "model":{"type":"WordLevel","vocab":{"[UNK]":0,"Q":1,"a":2,"b":3,"c":4,"Question":5,"Context":6,"chunks":7,"context":8,"page":9,"answer":10},"unk_token":"[UNK]"}
}"#;

impl Generator {
    pub async fn new(
        transport: BoxedGenerationTransport,
        settings: GenerationSettings,
    ) -> Result<Self, RagRuntimeError> {
        let tokenizer = load_tokenizer_from_repo(&settings.tokenizer_source)
            .await
            .map_err(RagRuntimeError::from)?;
        Ok(Self {
            transport,
            settings,
            tokenizer: Arc::new(tokenizer),
        })
    }

    pub async fn generate(
        &self,
        request: GenerationRequest,
    ) -> Result<GenerationResponse, RagRuntimeError> {
        let stage_started = Instant::now();

        let result: Result<GenerationResponse, RagRuntimeError> = {
            if request.chunks.is_empty() {
                Err(GenerationError::InvalidInput {
                    message: "generation requires at least one retrieved chunk".to_string(),
                }
                .into())
            } else if request.chunks.len() > self.settings.max_context_chunks {
                Err(GenerationError::ChunkLimitExceeded {
                    actual: request.chunks.len(),
                    max_allowed: self.settings.max_context_chunks,
                }
                .into())
            } else {
                let prompt = build_chat_prompt(&request.query, &request.chunks);
                let prompt_token_count = self.prompt_token_count_for_prompt(&prompt)?;
                let prompt_length = prompt.user.len();

                tracing::info!(
                    tokenizer_source = %self.settings.tokenizer_source,
                    max_context_chunks = self.settings.max_context_chunks as i64,
                    max_prompt_tokens = self.settings.max_prompt_tokens as i64,
                    input_chunk_count = request.chunks.len() as i64,
                    prompt_length = prompt_length as i64,
                    prompt_token_count = prompt_token_count as i64,
                    "generation.prompt_assembly"
                );

                if prompt_token_count > self.settings.max_prompt_tokens {
                    Err(GenerationError::PromptTokenLimitExceeded {
                        actual: prompt_token_count,
                        max_allowed: self.settings.max_prompt_tokens,
                    }
                    .into())
                } else {
                    let (llm_system, llm_provider) =
                        transport_otel_identity(&self.settings.transport);
                    let model_name = self.settings.transport_model_name();
                    record_generation_input_chunk_count(request.chunks.len());
                    record_generation_prompt_tokens(prompt_token_count, llm_provider, model_name);
                    let chat_span = info_span!(
                        "generation.chat",
                        "span.module" = "generation",
                        "span.stage" = "chat",
                        status = field::Empty,
                        "error.type" = field::Empty,
                        "error.message" = field::Empty,
                        "openinference.span.kind" = "LLM",
                        "llm.system" = llm_system,
                        "llm.provider" = llm_provider,
                        "llm.model.name" = %model_name,
                        "llm.invocation.temperature" = self.settings.temperature,
                        "llm.input_messages.count" = 2_i64,
                        "llm.input_messages.roles" = ?vec!["system", "user"],
                        "llm.output_messages.count" = 1_i64,
                        "llm.prompt.template.id" = PROMPT_TEMPLATE_ID,
                        "llm.prompt.template.version" = PROMPT_TEMPLATE_VERSION,
                        "output.value" = field::Empty,
                        "output.mime_type" = "text/plain",
                        "llm.token_count.prompt" = prompt_token_count as i64,
                        "llm.token_count.completion" = field::Empty,
                        "llm.token_count.total" = field::Empty,
                        "llm.cost.prompt" = field::Empty,
                        "llm.cost.completion" = field::Empty,
                        "llm.cost.total" = field::Empty,
                        "rag.cost.prompt_microusd" = field::Empty,
                        "rag.cost.completion_microusd" = field::Empty,
                        "rag.cost.total_microusd" = field::Empty
                    );
                    let chat_started = Instant::now();

                    let result: Result<GenerationResponse, RagRuntimeError> = async {
                        let answer = self
                            .transport
                            .complete(
                                prompt.clone(),
                                &self.settings.transport,
                                GenerationTransportRuntime {
                                    retry: &self.settings.retry,
                                    temperature: self.settings.temperature,
                                },
                            )
                            .await?;

                        mark_span_ok();

                        let completion_tokens = answer
                            .completion_tokens
                            .unwrap_or(self.tokenizer.count_tokens(&answer.content)?);
                        let prompt_tokens = answer.prompt_tokens.unwrap_or(prompt_token_count);
                        let total_tokens = prompt_tokens + completion_tokens;
                        let (prompt_cost_usd, completion_cost_usd, total_cost_usd) =
                            generation_costs_usd(
                                &self.settings.transport,
                                prompt_tokens,
                                completion_tokens,
                            );

                        tracing::Span::current()
                            .record("output.value", field::display(&answer.content));
                        tracing::Span::current()
                            .record("llm.token_count.completion", completion_tokens as i64);
                        tracing::Span::current()
                            .record("llm.token_count.total", total_tokens as i64);
                        tracing::Span::current().record("llm.cost.prompt", prompt_cost_usd);
                        tracing::Span::current().record("llm.cost.completion", completion_cost_usd);
                        tracing::Span::current().record("llm.cost.total", total_cost_usd);
                        tracing::Span::current()
                            .record("rag.cost.prompt_microusd", usd_to_microusd(prompt_cost_usd));
                        tracing::Span::current().record(
                            "rag.cost.completion_microusd",
                            usd_to_microusd(completion_cost_usd),
                        );
                        tracing::Span::current()
                            .record("rag.cost.total_microusd", usd_to_microusd(total_cost_usd));

                        tracing::info!(
                            model_name = %model_name,
                            answer_present = !answer.content.is_empty(),
                            answer_length = answer.content.len() as i64,
                            completion_token_count = completion_tokens as i64,
                            total_token_count = total_tokens as i64,
                            "generation.response_validation"
                        );
                        record_generation_completion_tokens(
                            completion_tokens,
                            total_tokens,
                            llm_provider,
                            model_name,
                        );
                        record_generation_cost_total(total_cost_usd, llm_provider, model_name);

                        Ok(GenerationResponse {
                            answer: answer.content,
                            prompt_tokens,
                            completion_tokens,
                            total_tokens,
                        })
                    }
                    .instrument(chat_span.clone())
                    .await;

                    match &result {
                        Ok(_) => {
                            chat_span.record("status", "ok");
                        }
                        Err(error) => {
                            if error.error_type() != "generation.response_validation" {
                                chat_span.record("status", "error");
                                chat_span.record("error.type", error.error_type());
                                chat_span
                                    .record("error.message", field::display(error.to_string()));
                            }
                            tracing::info!(
                                model_name = %model_name,
                                error_type = error.error_type(),
                                error_message = %error,
                                "generation_request_failed"
                            );
                        }
                    }

                    record_dependency_close(
                        "generation",
                        "generation",
                        "chat",
                        chat_started.elapsed().as_secs_f64() * 1000.0,
                        if result.is_ok() {
                            StatusLabel::Ok
                        } else {
                            StatusLabel::Error
                        },
                    );
                    result
                }
            }
        };

        let status = if result.is_err() {
            StatusLabel::Error
        } else {
            StatusLabel::Ok
        };
        record_stage_close(
            "generation",
            "generation",
            stage_started.elapsed().as_secs_f64() * 1000.0,
            status,
        );
        result
    }

    pub fn prefix_prompt_token_counts(
        &self,
        query: &str,
        chunks: &[RetrievedChunk],
    ) -> Result<Vec<usize>, RagRuntimeError> {
        let mut counts = Vec::with_capacity(chunks.len());
        for end in 1..=chunks.len() {
            let prompt = build_chat_prompt(query, &chunks[..end]);
            counts.push(self.prompt_token_count_for_prompt(&prompt)?);
        }
        Ok(counts)
    }

    fn prompt_token_count_for_prompt(&self, prompt: &ChatPrompt) -> Result<usize, RagRuntimeError> {
        self.tokenizer
            .count_tokens(&full_chat_prompt(prompt))
            .map_err(RagRuntimeError::from)
    }

    #[cfg(test)]
    pub fn for_tests(settings: GenerationSettings) -> Self {
        Self {
            transport: build_generation_transport(&settings)
                .expect("generation test transport should build"),
            settings,
            tokenizer: Arc::new(TokenizerResource::from_test_bytes(TEST_TOKENIZER_JSON)),
        }
    }

    #[cfg(test)]
    pub fn with_transport_for_tests(
        transport: BoxedGenerationTransport,
        settings: GenerationSettings,
    ) -> Self {
        Self {
            transport,
            settings,
            tokenizer: Arc::new(TokenizerResource::from_test_bytes(TEST_TOKENIZER_JSON)),
        }
    }
}

fn build_chat_prompt(query: &str, chunks: &[RetrievedChunk]) -> ChatPrompt {
    let context_chunks = render_context_chunks(chunks);
    ChatPrompt {
        system: SYSTEM_PROMPT.to_string(),
        user: build_user_prompt(query, &context_chunks),
    }
}

fn render_context_chunks(chunks: &[RetrievedChunk]) -> String {
    chunks
        .iter()
        .map(|retrieved| {
            render_chunk_block(
                &retrieved.chunk.page_start,
                &retrieved.chunk.page_end,
                &retrieved.chunk.text,
            )
        })
        .collect::<Vec<_>>()
        .join("\n\n")
}

fn build_user_prompt(query: &str, context_chunks: &str) -> String {
    USER_PROMPT_TEMPLATE
        .replace("{{question}}", query)
        .replace("{{context_chunks}}", context_chunks)
}

fn full_chat_prompt(prompt: &ChatPrompt) -> String {
    format!("{}\n{}", prompt.system, prompt.user)
}

fn render_chunk_block(page_start: &i64, page_end: &i64, text: &str) -> String {
    let label = if page_start == page_end {
        format!("[page {page_start}]")
    } else {
        format!("[pages {page_start}-{page_end}]")
    };
    format!("{label}\n{text}")
}

fn transport_otel_identity(transport: &TransportSettings) -> (&'static str, &'static str) {
    match transport {
        TransportSettings::Ollama(_) => ("ollama", "ollama"),
        TransportSettings::OpenAi(settings) => (
            "openai",
            if settings.url.contains("together") {
                "together"
            } else {
                "openai"
            },
        ),
    }
}

fn generation_costs_usd(
    transport: &TransportSettings,
    prompt_tokens: usize,
    completion_tokens: usize,
) -> (f64, f64, f64) {
    let (input_cost_per_million_tokens, output_cost_per_million_tokens) = match transport {
        TransportSettings::Ollama(settings) => (
            settings.input_cost_per_million_tokens,
            settings.output_cost_per_million_tokens,
        ),
        TransportSettings::OpenAi(settings) => (
            settings.input_cost_per_million_tokens,
            settings.output_cost_per_million_tokens,
        ),
    };
    let prompt_cost = prompt_tokens as f64 * input_cost_per_million_tokens / 1_000_000.0;
    let completion_cost = completion_tokens as f64 * output_cost_per_million_tokens / 1_000_000.0;
    (prompt_cost, completion_cost, prompt_cost + completion_cost)
}

fn usd_to_microusd(value: f64) -> i64 {
    (value * 1_000_000.0).round() as i64
}

#[cfg(test)]
mod tests {
    use std::collections::VecDeque;
    use std::sync::Mutex;

    use async_trait::async_trait;
    use axum::http::StatusCode;
    use serde_json::json;

    use super::*;
    use crate::config::{OllamaTransportSettings, OpenAiTransportSettings, TransportSettings};
    use crate::generation::tokenizer::{load_tokenizer_from_url, tokenizer_url};
    use crate::models::{Chunk, RetrievedChunk};
    use crate::test_support::{MockHttpResponse, MockHttpServer, test_settings};

    fn sample_chunk(page_start: i64, page_end: i64, text: &str) -> RetrievedChunk {
        RetrievedChunk {
            chunk: Chunk {
                schema_version: 1,
                doc_id: "doc-1".to_string(),
                chunk_id: format!("chunk-{page_start}-{page_end}"),
                url: "local://doc".to_string(),
                document_title: "Doc".to_string(),
                section_title: Some("Section".to_string()),
                section_path: vec!["Section".to_string()],
                chunk_index: 0,
                page_start,
                page_end,
                tags: vec![],
                content_hash: "sha256:abc".to_string(),
                chunking_version: "v1".to_string(),
                chunk_created_at: "2026-01-01T00:00:00Z".to_string(),
                text: text.to_string(),
                ingest: None,
            },
            score: 0.9,
        }
    }

    fn sample_request() -> GenerationRequest {
        GenerationRequest {
            query: "What is consensus?".to_string(),
            chunks: vec![sample_chunk(1, 1, "chunk text")],
        }
    }

    struct MockTransport {
        responses: Mutex<VecDeque<Result<ModelAnswer, GenerationError>>>,
        calls: Arc<Mutex<Vec<(ChatPrompt, f32)>>>,
    }

    #[async_trait]
    impl GenerationTransport for MockTransport {
        async fn complete(
            &self,
            prompt: ChatPrompt,
            _transport: &TransportSettings,
            runtime: GenerationTransportRuntime<'_>,
        ) -> Result<ModelAnswer, GenerationError> {
            self.calls
                .lock()
                .unwrap()
                .push((prompt, runtime.temperature));
            self.responses
                .lock()
                .unwrap()
                .pop_front()
                .unwrap_or_else(|| {
                    Ok(ModelAnswer {
                        content: "answer".to_string(),
                        prompt_tokens: None,
                        completion_tokens: None,
                    })
                })
        }
    }

    #[tokio::test]
    async fn empty_chunks_fail_with_invalid_input() {
        let engine = Generator::for_tests(test_settings().generation);
        let error = engine
            .generate(GenerationRequest {
                query: "Q".to_string(),
                chunks: vec![],
            })
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "generation.invalid_input");
    }

    #[tokio::test]
    async fn chunk_limit_exceeded_returns_exact_variant() {
        let mut settings = test_settings().generation;
        settings.max_context_chunks = 1;
        let engine = Generator::for_tests(settings);
        let error = engine
            .generate(GenerationRequest {
                query: "Q".to_string(),
                chunks: vec![sample_chunk(1, 1, "one"), sample_chunk(2, 2, "two")],
            })
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "generation.chunk_limit_exceeded");
    }

    #[tokio::test]
    async fn prompt_above_limit_fails_with_exact_variant() {
        let mut settings = test_settings().generation;
        settings.max_prompt_tokens = 0;
        let engine = Generator::for_tests(settings);
        let error = engine.generate(sample_request()).await.unwrap_err();
        assert_eq!(error.error_type(), "generation.prompt_token_limit_exceeded");
    }

    #[tokio::test]
    async fn transport_none_token_counts_use_local_tokenizer() {
        let settings = test_settings().generation;
        let calls = Arc::new(Mutex::new(Vec::new()));
        let engine = Generator::with_transport_for_tests(
            Box::new(MockTransport {
                responses: Mutex::new(VecDeque::from(vec![Ok(ModelAnswer {
                    content: "answer".to_string(),
                    prompt_tokens: None,
                    completion_tokens: None,
                })])),
                calls: Arc::clone(&calls),
            }),
            settings,
        );

        let response = engine.generate(sample_request()).await.unwrap();
        assert_eq!(response.answer, "answer");
        assert!(response.prompt_tokens > 0);
        assert_eq!(response.completion_tokens, 1);
        assert_eq!(
            response.total_tokens,
            response.prompt_tokens + response.completion_tokens
        );
        assert_eq!(calls.lock().unwrap().len(), 1);
    }

    #[tokio::test]
    async fn transport_supplied_token_counts_are_used_directly() {
        let settings = test_settings().generation;
        let engine = Generator::with_transport_for_tests(
            Box::new(MockTransport {
                responses: Mutex::new(VecDeque::from(vec![Ok(ModelAnswer {
                    content: "answer".to_string(),
                    prompt_tokens: Some(11),
                    completion_tokens: Some(7),
                })])),
                calls: Arc::new(Mutex::new(Vec::new())),
            }),
            settings,
        );

        let response = engine.generate(sample_request()).await.unwrap();
        assert_eq!(response.prompt_tokens, 11);
        assert_eq!(response.completion_tokens, 7);
        assert_eq!(response.total_tokens, 18);
    }

    #[test]
    fn single_page_chunk_renders_single_page_label() {
        assert_eq!(render_chunk_block(&1, &1, "text"), "[page 1]\ntext");
    }

    #[test]
    fn multi_page_chunk_renders_multi_page_label() {
        assert_eq!(render_chunk_block(&1, &3, "text"), "[pages 1-3]\ntext");
    }

    #[test]
    fn multiple_chunk_blocks_are_joined_with_double_newline_in_input_order() {
        let rendered =
            render_context_chunks(&[sample_chunk(1, 1, "first"), sample_chunk(2, 3, "second")]);
        assert_eq!(rendered, "[page 1]\nfirst\n\n[pages 2-3]\nsecond");
    }

    #[test]
    fn user_prompt_substitution_replaces_placeholders() {
        let prompt = build_user_prompt("What is Raft?", "[page 1]\nchunk");
        assert!(prompt.contains("What is Raft?"));
        assert!(prompt.contains("[page 1]\nchunk"));
        assert!(!prompt.contains("{{question}}"));
        assert!(!prompt.contains("{{context_chunks}}"));
    }

    #[tokio::test]
    async fn valid_ollama_response_returns_message_content() {
        let server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"message":{"content":"answer"}}).to_string(),
        }])
        .await;
        let transport = OllamaTransport::default();
        let settings = TransportSettings::Ollama(OllamaTransportSettings {
            url: server.endpoint(),
            model_name: "model".to_string(),
            timeout_sec: 30,
            input_cost_per_million_tokens: 0.0,
            output_cost_per_million_tokens: 0.0,
        });

        let answer = transport
            .complete(
                ChatPrompt {
                    system: "system".to_string(),
                    user: "user".to_string(),
                },
                &settings,
                GenerationTransportRuntime {
                    retry: &test_settings().generation.retry,
                    temperature: 0.0,
                },
            )
            .await
            .unwrap();

        assert_eq!(answer.content, "answer");
        assert_eq!(answer.prompt_tokens, None);
        assert_eq!(answer.completion_tokens, None);
    }

    #[tokio::test]
    async fn ollama_request_body_matches_contract_shape() {
        let server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({"message":{"content":"answer"}}).to_string(),
        }])
        .await;
        let transport = OllamaTransport::default();
        let settings = TransportSettings::Ollama(OllamaTransportSettings {
            url: server.endpoint(),
            model_name: "model".to_string(),
            timeout_sec: 30,
            input_cost_per_million_tokens: 0.0,
            output_cost_per_million_tokens: 0.0,
        });

        transport
            .complete(
                ChatPrompt {
                    system: "system".to_string(),
                    user: "user".to_string(),
                },
                &settings,
                GenerationTransportRuntime {
                    retry: &test_settings().generation.retry,
                    temperature: 0.7,
                },
            )
            .await
            .unwrap();

        let requests = server.recorded_requests();
        let body = requests.first().unwrap();
        assert_eq!(body["model"], "model");
        assert_eq!(body["stream"], false);
        assert_eq!(body["options"]["temperature"], json!(0.7_f32));
        assert_eq!(body["messages"].as_array().unwrap().len(), 2);
    }

    #[tokio::test]
    async fn openai_request_includes_authorization_header() {
        let server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({
                "choices":[{"message":{"content":"answer"}}],
                "usage":{"prompt_tokens":3,"completion_tokens":2}
            })
            .to_string(),
        }])
        .await;
        let transport = OpenAiTransport::default();
        let settings = TransportSettings::OpenAi(OpenAiTransportSettings {
            url: server.endpoint(),
            api_key: "secret".to_string(),
            model_name: "openai/gpt-oss-20b".to_string(),
            timeout_sec: 30,
            input_cost_per_million_tokens: 0.0,
            output_cost_per_million_tokens: 0.0,
        });

        transport
            .complete(
                ChatPrompt {
                    system: "system".to_string(),
                    user: "user".to_string(),
                },
                &settings,
                GenerationTransportRuntime {
                    retry: &test_settings().generation.retry,
                    temperature: 0.2,
                },
            )
            .await
            .unwrap();

        let headers = server.recorded_headers();
        let auth = headers
            .first()
            .and_then(|header_map| header_map.get("authorization"))
            .cloned();
        assert_eq!(auth.as_deref(), Some("Bearer secret"));
    }

    #[tokio::test]
    async fn valid_openai_response_returns_usage_counts() {
        let server = MockHttpServer::start(vec![MockHttpResponse {
            status: StatusCode::OK,
            body: json!({
                "choices":[{"message":{"content":"answer"}}],
                "usage":{"prompt_tokens":5,"completion_tokens":4}
            })
            .to_string(),
        }])
        .await;
        let transport = OpenAiTransport::default();
        let settings = TransportSettings::OpenAi(OpenAiTransportSettings {
            url: server.endpoint(),
            api_key: "secret".to_string(),
            model_name: "openai/gpt-oss-20b".to_string(),
            timeout_sec: 30,
            input_cost_per_million_tokens: 0.0,
            output_cost_per_million_tokens: 0.0,
        });

        let answer = transport
            .complete(
                ChatPrompt {
                    system: "system".to_string(),
                    user: "user".to_string(),
                },
                &settings,
                GenerationTransportRuntime {
                    retry: &test_settings().generation.retry,
                    temperature: 0.2,
                },
            )
            .await
            .unwrap();

        assert_eq!(answer.content, "answer");
        assert_eq!(answer.prompt_tokens, Some(5));
        assert_eq!(answer.completion_tokens, Some(4));
    }

    #[tokio::test]
    async fn transport_variant_mismatch_returns_exact_variant() {
        let transport = OpenAiTransport::default();
        let settings = TransportSettings::Ollama(OllamaTransportSettings {
            url: "http://127.0.0.1:9".to_string(),
            model_name: "model".to_string(),
            timeout_sec: 30,
            input_cost_per_million_tokens: 0.0,
            output_cost_per_million_tokens: 0.0,
        });

        let error = transport
            .complete(
                ChatPrompt {
                    system: "system".to_string(),
                    user: "user".to_string(),
                },
                &settings,
                GenerationTransportRuntime {
                    retry: &test_settings().generation.retry,
                    temperature: 0.2,
                },
            )
            .await
            .unwrap_err();

        assert_eq!(error.error_type(), "generation.unexpected_internal_state");
    }

    #[tokio::test]
    async fn tokenizer_init_fails_when_artifact_cannot_be_loaded() {
        let error = load_tokenizer_from_url("http://127.0.0.1:9/missing")
            .await
            .unwrap_err();
        assert_eq!(error.error_type(), "generation.tokenizer_initialization");
    }

    #[test]
    fn tokenizer_repo_url_matches_expected_huggingface_path() {
        assert_eq!(
            tokenizer_url("org/tokenizer"),
            "https://huggingface.co/org/tokenizer/resolve/main/tokenizer.json"
        );
    }
}

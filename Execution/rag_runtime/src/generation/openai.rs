use std::time::Duration;

use async_trait::async_trait;
use reqwest::Client;
use serde_json::{Value, json};

use crate::config::TransportSettings;
use crate::errors::GenerationError;

use super::transport::{
    ChatPrompt, GenerationTransport, GenerationTransportRuntime, ModelAnswer, parse_json_object,
    retry_generation_with_policy,
};

#[derive(Debug, Default)]
pub struct OpenAiTransport {
    client: Client,
}

#[async_trait]
impl GenerationTransport for OpenAiTransport {
    async fn complete(
        &self,
        prompt: ChatPrompt,
        transport: &TransportSettings,
        runtime: GenerationTransportRuntime<'_>,
    ) -> Result<ModelAnswer, GenerationError> {
        let settings = match transport {
            TransportSettings::OpenAi(settings) => settings,
            _ => {
                return Err(GenerationError::UnexpectedInternalState {
                    message: "openai transport received non-openai transport settings".to_string(),
                });
            }
        };

        let url = format!("{}/v1/chat/completions", settings.url.trim_end_matches('/'));
        let request_body = json!({
            "model": settings.model_name,
            "messages": [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
            "temperature": runtime.temperature
        });

        let ((response_text, http_status_code), retry_attempt_count) =
            retry_generation_with_policy(runtime.retry, "chat", || async {
                let response = self
                    .client
                    .post(&url)
                    .timeout(Duration::from_secs(settings.timeout_sec))
                    .bearer_auth(&settings.api_key)
                    .json(&request_body)
                    .send()
                    .await
                    .map_err(|error| GenerationError::RequestFailure {
                        message: error.to_string(),
                    })?;
                let status = response.status();
                if !status.is_success() {
                    let body = response.text().await.unwrap_or_default();
                    return Err(GenerationError::RequestFailure {
                        message: format!("status {status}: {body}"),
                    });
                }
                response
                    .text()
                    .await
                    .map(|text| (text, status.as_u16()))
                    .map_err(|error| GenerationError::RequestFailure {
                        message: error.to_string(),
                    })
            })
            .await?;

        tracing::info!(
            model_name = %settings.model_name,
            temperature = runtime.temperature,
            http_status_code,
            request_body_length = request_body.to_string().len() as i64,
            retry_attempt_count,
            "generation.response_returned"
        );

        let parsed = parse_json_object(&response_text)?;
        let choices = parsed
            .get("choices")
            .and_then(Value::as_array)
            .filter(|choices| !choices.is_empty())
            .ok_or_else(|| GenerationError::ResponseValidation {
                message: "missing choices[0]".to_string(),
            })?;
        let content = choices[0]
            .get("message")
            .and_then(Value::as_object)
            .and_then(|message| message.get("content"))
            .and_then(Value::as_str)
            .ok_or_else(|| GenerationError::ResponseValidation {
                message: "missing choices[0].message.content".to_string(),
            })?;
        let usage = parsed
            .get("usage")
            .and_then(Value::as_object)
            .ok_or_else(|| GenerationError::ResponseValidation {
                message: "missing usage".to_string(),
            })?;
        let prompt_tokens = usage
            .get("prompt_tokens")
            .and_then(Value::as_u64)
            .ok_or_else(|| GenerationError::ResponseValidation {
                message: "missing usage.prompt_tokens".to_string(),
            })? as usize;
        let completion_tokens = usage
            .get("completion_tokens")
            .and_then(Value::as_u64)
            .ok_or_else(|| GenerationError::ResponseValidation {
                message: "missing usage.completion_tokens".to_string(),
            })? as usize;

        Ok(ModelAnswer {
            content: content.to_string(),
            prompt_tokens: Some(prompt_tokens),
            completion_tokens: Some(completion_tokens),
        })
    }
}

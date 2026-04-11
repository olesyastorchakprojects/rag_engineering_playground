use std::fs;
use std::path::{Path, PathBuf};

use serde_json::Value;

fn repo_root() -> PathBuf {
    let start = Path::new(env!("CARGO_MANIFEST_DIR"));
    for candidate in start.ancestors() {
        if candidate.join("Specification").is_dir() {
            return candidate.to_path_buf();
        }
    }
    panic!("repo root");
}

fn read_text(path: impl AsRef<Path>) -> String {
    let path = path.as_ref();
    fs::read_to_string(path)
        .unwrap_or_else(|error| panic!("read text fixture {}: {error}", path.display()))
}

fn read_json(path: impl AsRef<Path>) -> Value {
    let text = read_text(path);
    serde_json::from_str(&text).expect("parse json fixture")
}

struct TempEnvVar {
    key: String,
    previous: Option<String>,
}

impl TempEnvVar {
    fn set(key: impl Into<String>, value: impl Into<String>) -> Self {
        let key = key.into();
        let previous = std::env::var(&key).ok();
        unsafe { std::env::set_var(&key, value.into()) };
        Self { key, previous }
    }
}

impl Drop for TempEnvVar {
    fn drop(&mut self) {
        match &self.previous {
            Some(value) => unsafe { std::env::set_var(&self.key, value) },
            None => unsafe { std::env::remove_var(&self.key) },
        }
    }
}

#[test]
fn cross_encoder_docs_remain_generic_and_api_focused() {
    let root = repo_root();
    let api_path = root.join("Specification/codegen/rag_runtime/reranking/mixedbread_ai_api.md");
    let reranker_path = root.join("Specification/codegen/rag_runtime/reranking/cross_encoder.md");
    let api_doc = read_text(api_path);
    let reranker_doc = read_text(reranker_path);

    assert!(api_doc.contains("external HTTP API contract"));
    assert!(api_doc.contains("POST /rerank"));
    assert!(api_doc.contains("results[*].index"));
    assert!(api_doc.contains("informational only for the current runtime contract"));

    assert!(reranker_doc.contains("Box<dyn RerankingTransport + Send + Sync>"));
    assert!(reranker_doc.contains(
        "preserve the final candidate order produced by the normalized transport response"
    ));
}

#[tokio::test]
async fn cross_encoder_runtime_config_loading_from_toml_and_env_succeeds() {
    let root = repo_root();
    let runtime_config = root.join("Execution/rag_runtime/rag_runtime.toml");
    let ingest_config = root.join("Execution/ingest/dense/ingest.toml");
    let tempdir = tempfile::tempdir().expect("temp dir");
    let runtime_copy = tempdir.path().join("rag_runtime.toml");
    let ingest_copy = tempdir.path().join("ingest.toml");

    fs::write(&runtime_copy, read_text(&runtime_config)).expect("write runtime config");
    fs::write(&ingest_copy, read_text(&ingest_config)).expect("write ingest config");

    let _ollama = TempEnvVar::set("OLLAMA_URL", "http://ollama.test");
    let _qdrant = TempEnvVar::set("QDRANT_URL", "http://qdrant.test");
    let _reranker = TempEnvVar::set("RERANKER_ENDPOINT", "http://reranker.test");
    let _postgres = TempEnvVar::set(
        "POSTGRES_URL",
        "postgres://postgres:postgres@localhost:5432/rag_eval",
    );
    let _tracing = TempEnvVar::set("TRACING_ENDPOINT", "http://trace.test");
    let _metrics = TempEnvVar::set("METRICS_ENDPOINT", "http://metrics.test");

    let result = rag_runtime::RagRuntime::from_config_paths(&runtime_copy, &ingest_copy).await;
    assert!(
        result.is_ok(),
        "cross_encoder config loading should succeed"
    );
}

#[ignore = "pending CrossEncoder runtime/schema support in request_capture schema and SQL"]
#[test]
fn cross_encoder_request_capture_schema_and_sql_should_accept_cross_encoder_snapshot() {
    let root = repo_root();
    let request_capture_schema =
        read_json(root.join("Execution/rag_runtime/schemas/request_capture.schema.json"));
    let request_capture_sql =
        read_text(root.join("Execution/docker/postgres/init/001_request_captures.sql"));

    let reranker_kind_enum = request_capture_schema
        .pointer("/properties/reranker_kind/enum")
        .and_then(Value::as_array)
        .expect("reranker_kind enum");
    assert!(
        reranker_kind_enum
            .iter()
            .any(|value| value == "CrossEncoder")
    );

    let retriever_kind_enum = request_capture_schema
        .pointer("/properties/retriever_kind/enum")
        .and_then(Value::as_array)
        .expect("retriever_kind enum");
    assert!(retriever_kind_enum.iter().any(|value| value == "Dense"));
    assert!(retriever_kind_enum.iter().any(|value| value == "Hybrid"));

    let reranker_config_shape = request_capture_schema
        .pointer("/properties/reranker_config/oneOf/2/properties")
        .and_then(Value::as_object)
        .expect("reranker_config object shape");
    assert!(reranker_config_shape.contains_key("kind"));
    assert!(reranker_config_shape.contains_key("cross_encoder"));

    assert!(
        request_capture_sql
            .contains("reranker_kind in ('PassThrough', 'Heuristic', 'CrossEncoder')")
    );
    assert!(request_capture_sql.contains("retriever_kind in ('Dense', 'Hybrid')"));
    assert!(request_capture_sql.contains("request_capture_reranker_config_is_valid"));
    assert!(request_capture_sql.contains("model_name"));
    assert!(request_capture_sql.contains("url"));
}

#[ignore = "pending external mxbai-reranker live smoke"]
#[tokio::test]
async fn mxbai_reranker_live_api_returns_ranked_results_for_real_chunks() {
    let root = repo_root();
    let chunks_path =
        root.join("Evidence/parsing/understanding_distributed_systems/chunks/chunks.jsonl");
    let endpoint =
        std::env::var("RERANKER_ENDPOINT").unwrap_or_else(|_| "http://127.0.0.1:8000".to_string());

    let chunks_text = read_text(&chunks_path);
    let texts: Vec<String> = chunks_text
        .lines()
        .take(12)
        .map(|line| {
            let value: Value = serde_json::from_str(line).expect("chunk json");
            value["text"].as_str().expect("chunk text").to_string()
        })
        .collect();

    let client = reqwest::Client::new();
    let health = client
        .get(format!("{endpoint}/health"))
        .send()
        .await
        .expect("health request");
    assert!(
        health.status().is_success(),
        "health endpoint should be reachable"
    );

    let response = client
        .post(format!("{endpoint}/rerank"))
        .json(&serde_json::json!({
            "query": "What is eventual consistency?",
            "texts": texts,
        }))
        .send()
        .await
        .expect("rerank request");

    assert!(
        response.status().is_success(),
        "rerank request should succeed"
    );
    let body: Value = response.json().await.expect("rerank response json");

    let results = body["results"].as_array().expect("results array");
    assert_eq!(results.len(), 12);
    let model_id = body["model_id"].as_str().expect("model_id string");
    assert!(!model_id.trim().is_empty());

    let mut seen_indices = std::collections::BTreeSet::new();
    let mut last_score = f64::INFINITY;
    for (expected_rank, result) in results.iter().enumerate() {
        let index = result["index"].as_u64().expect("result index") as usize;
        let score = result["score"].as_f64().expect("result score");
        let rank = result["rank"].as_u64().expect("result rank");
        let text = result["text"].as_str().expect("result text");

        assert!(
            index < texts.len(),
            "index must map back to the input batch"
        );
        assert!(seen_indices.insert(index), "indices must be unique");
        assert!(
            !text.trim().is_empty(),
            "service should echo candidate text in each result"
        );
        assert_eq!(rank as usize, expected_rank + 1);
        assert!(score <= last_score, "scores must be sorted descending");
        last_score = score;
    }
}

use std::env;
use std::fs;

use rag_runtime::RagRuntime;
use rag_runtime::errors::RagRuntimeError;
use tempfile::tempdir;

fn remove_env_var(key: &str) {
    unsafe { env::remove_var(key) };
}

#[tokio::test]
async fn e2e_smoke_reports_startup_failure_without_required_env() {
    let dir = tempdir().unwrap();
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
        fs::read_to_string("/home/olesia/code/prompt_gen_proj/Execution/ingest/dense/ingest.toml")
            .unwrap(),
    )
    .unwrap();

    remove_env_var("OLLAMA_URL");
    remove_env_var("QDRANT_URL");
    remove_env_var("TRACING_ENDPOINT");
    remove_env_var("METRICS_ENDPOINT");
    unsafe { env::set_var("RAG_RUNTIME_SKIP_DOTENV", "1") };

    match RagRuntime::from_config_paths(&runtime_config, &ingest_config).await {
        Ok(_) => panic!("expected startup failure without required environment variables"),
        Err(error) => assert!(matches!(error, RagRuntimeError::Startup { .. })),
    }

    remove_env_var("RAG_RUNTIME_SKIP_DOTENV");
}

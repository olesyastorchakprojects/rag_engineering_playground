use std::error::Error;
use std::time::Duration;

use clap::Parser;
use otel_smoke::{
    emit_tracing_tree_smoke, init_observability_with_mode, shutdown_observability, InitMode,
    TraceExportMode, DEFAULT_OTLP_GRPC_ENDPOINT, DEFAULT_SERVICE_NAME,
};

#[derive(Parser, Debug)]
struct Cli {
    #[arg(long, default_value = DEFAULT_OTLP_GRPC_ENDPOINT)]
    endpoint: String,
    #[arg(long, default_value = DEFAULT_SERVICE_NAME)]
    service_name: String,
    #[arg(long, default_value = "otel-tracing-tree-request-1")]
    request_id: String,
    #[arg(long, default_value = "todo-style")]
    init_mode: String,
}

fn parse_init_mode(value: &str) -> Result<InitMode, Box<dyn Error>> {
    match value {
        "current" => Ok(InitMode::Current),
        "todo-style" => Ok(InitMode::TodoStyle),
        other => Err(format!("unsupported init mode: {other}").into()),
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let cli = Cli::parse();
    let init_mode = parse_init_mode(&cli.init_mode)?;

    let guards = init_observability_with_mode(
        &cli.endpoint,
        &cli.service_name,
        TraceExportMode::Batch,
        init_mode,
    )?;
    emit_tracing_tree_smoke(&cli.request_id).await;
    tokio::time::sleep(Duration::from_secs(5)).await;
    shutdown_observability(guards);

    Ok(())
}

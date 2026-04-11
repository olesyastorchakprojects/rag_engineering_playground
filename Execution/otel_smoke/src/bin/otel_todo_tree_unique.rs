use std::error::Error;
use std::time::Duration;

use clap::Parser;
use otel_smoke::{
    emit_tracing_tree_smoke_named, init_observability_todo_style, shutdown_observability,
    DEFAULT_OTLP_GRPC_ENDPOINT,
};

#[derive(Parser, Debug)]
struct Cli {
    #[arg(long, default_value = DEFAULT_OTLP_GRPC_ENDPOINT)]
    endpoint: String,
    #[arg(long, default_value = "otel-smoke-todo-tree-unique")]
    service_name: String,
    #[arg(long, default_value = "todo-tree-request-1")]
    request_id: String,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let cli = Cli::parse();

    let guards = init_observability_todo_style(&cli.endpoint, &cli.service_name)?;
    emit_tracing_tree_smoke_named(&cli.request_id).await;
    tokio::time::sleep(Duration::from_secs(10)).await;
    shutdown_observability(guards);

    Ok(())
}

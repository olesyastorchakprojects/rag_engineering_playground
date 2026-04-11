use std::error::Error;
use std::time::Duration;

use clap::Parser;
use otel_smoke::{init_observability_todo_style, shutdown_observability, DEFAULT_OTLP_GRPC_ENDPOINT};

#[derive(Parser, Debug)]
struct Cli {
    #[arg(long, default_value = DEFAULT_OTLP_GRPC_ENDPOINT)]
    endpoint: String,
    #[arg(long, default_value = "otel-smoke-todo-init-only")]
    service_name: String,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let cli = Cli::parse();
    let guards = init_observability_todo_style(&cli.endpoint, &cli.service_name)?;
    tokio::time::sleep(Duration::from_secs(10)).await;
    shutdown_observability(guards);
    Ok(())
}

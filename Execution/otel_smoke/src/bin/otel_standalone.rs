use std::error::Error;
use std::time::Duration;

use clap::Parser;
use otel_smoke::{
    emit_smoke_telemetry, init_observability, shutdown_observability, TraceExportMode,
    DEFAULT_OTLP_GRPC_ENDPOINT, DEFAULT_SERVICE_NAME,
};

#[derive(Parser, Debug)]
struct Cli {
    #[arg(long, default_value = DEFAULT_OTLP_GRPC_ENDPOINT)]
    endpoint: String,
    #[arg(long, default_value = DEFAULT_SERVICE_NAME)]
    service_name: String,
    #[arg(long, default_value = "otel-standalone-request-1")]
    request_id: String,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let cli = Cli::parse();

    let guards = init_observability(&cli.endpoint, &cli.service_name, TraceExportMode::Batch)?;
    emit_smoke_telemetry(&cli.request_id).await;
    tokio::time::sleep(Duration::from_secs(5)).await;
    shutdown_observability(guards);

    Ok(())
}

use std::error::Error;
use std::time::Duration;

use clap::Parser;
use otel_smoke::{
    init_observability, shutdown_observability, test_instrumented_span, TraceExportMode,
    DEFAULT_OTLP_GRPC_ENDPOINT,
};

#[derive(Parser, Debug)]
struct Cli {
    #[arg(long, default_value = DEFAULT_OTLP_GRPC_ENDPOINT)]
    endpoint: String,
    #[arg(long, default_value = "otel-smoke-current-exact")]
    service_name: String,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let cli = Cli::parse();

    let guards = init_observability(&cli.endpoint, &cli.service_name, TraceExportMode::Batch)?;

    {
        let span = tracing::info_span!(
            "current.init7",
            component = "otel_test",
            http_status_code = tracing::field::Empty,
        );
        let _enter = span.enter();
        span.record("http_status_code", 200);

        test_instrumented_span().await?;
    }

    tokio::time::sleep(Duration::from_secs(5)).await;
    shutdown_observability(guards);

    Ok(())
}

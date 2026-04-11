use std::error::Error;
use std::net::SocketAddr;

use axum::{routing::get, Router};
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
    #[arg(long, default_value = "127.0.0.1:3401")]
    addr: SocketAddr,
}

async fn smoke_handler() -> &'static str {
    emit_smoke_telemetry("otel-server-request-1").await;
    "ok"
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let cli = Cli::parse();
    let guards = init_observability(&cli.endpoint, &cli.service_name, TraceExportMode::Batch)?;

    let app = Router::new().route("/smoke", get(smoke_handler));
    let listener = tokio::net::TcpListener::bind(cli.addr).await?;

    let shutdown = async {
        let _ = tokio::signal::ctrl_c().await;
    };

    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown)
        .await?;

    shutdown_observability(guards);
    Ok(())
}

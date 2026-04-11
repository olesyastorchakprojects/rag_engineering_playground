use std::error::Error;
use std::time::Duration;

use clap::Parser;
use opentelemetry::global;
use opentelemetry::trace::{Span as _, Tracer as _};
use opentelemetry::KeyValue;
use otel_smoke::{
    init_observability_todo_style, shutdown_observability, test_instrumented_span,
    DEFAULT_OTLP_GRPC_ENDPOINT,
};

#[derive(Parser, Debug)]
struct Cli {
    #[arg(long, default_value = DEFAULT_OTLP_GRPC_ENDPOINT)]
    endpoint: String,
    #[arg(long, default_value = "otel-smoke-todo-exact")]
    service_name: String,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let cli = Cli::parse();

    let guards = init_observability_todo_style(&cli.endpoint, &cli.service_name)?;

    {
        let span = tracing::info_span!(
        "wtf3.init",
        component = "otel_test",
        http_status_code = tracing::field::Empty,
        );
        let _enter = span.enter();
        span.record("http_status_code", 200);

        test_instrumented_span().await?;
        //guards.tracer_provider.force_flush()?;
    }

    // let tracer = global::tracer("otel_smoke_diagnostic");
    // let mut span = tracer.start("observability.init.diagnostic");
    // span.set_attribute(KeyValue::new("diagnostic", "true"));
    // span.set_attribute(KeyValue::new("service.name", cli.service_name));
    // span.end();

    tokio::time::sleep(Duration::from_secs(5)).await;
    shutdown_observability(guards);

    Ok(())
}

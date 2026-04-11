use std::error::Error;
use std::time::{Duration, Instant};

use clap::Parser;
use opentelemetry::global;
use opentelemetry::metrics::{Counter, Histogram, Meter};
use opentelemetry::trace::TracerProvider as _;
use opentelemetry::{InstrumentationScope, KeyValue};
use opentelemetry_otlp::WithExportConfig;
use opentelemetry_sdk::Resource;
use opentelemetry_sdk::metrics::{PeriodicReader, SdkMeterProvider};
use opentelemetry_sdk::trace::{Sampler, SdkTracerProvider};
use tracing::{field, info, info_span};
use tracing_subscriber::{layer::SubscriberExt, EnvFilter, Registry};

const DEFAULT_ENDPOINT: &str = "http://localhost:4317";
const DEFAULT_SERVICE_NAME: &str = "rag-runtime-observability-smoke";
const DEFAULT_REQUEST_ID: &str = "smoke-request-1";

#[derive(Parser, Debug)]
struct Cli {
    #[arg(long, default_value = DEFAULT_ENDPOINT)]
    endpoint: String,
    #[arg(long, default_value = DEFAULT_SERVICE_NAME)]
    service_name: String,
    #[arg(long, default_value = DEFAULT_REQUEST_ID)]
    request_id: String,
    #[arg(long, default_value_t = 5000)]
    post_run_sleep_ms: u64,
}

struct ObservabilityGuards {
    tracer_provider: SdkTracerProvider,
    meter_provider: SdkMeterProvider,
}

impl ObservabilityGuards {
    fn shutdown(self) {
        if let Err(error) = self.tracer_provider.force_flush() {
            eprintln!("tracer force_flush error: {error}");
        }
        if let Err(error) = self.meter_provider.force_flush() {
            eprintln!("meter force_flush error: {error}");
        }
        if let Err(error) = self.tracer_provider.shutdown() {
            eprintln!("tracer shutdown error: {error}");
        }
        if let Err(error) = self.meter_provider.shutdown() {
            eprintln!("meter shutdown error: {error}");
        }
    }
}

struct SmokeMetrics {
    requests_total: Counter<u64>,
    request_duration_ms: Histogram<f64>,
    stage_duration_ms: Histogram<f64>,
}

impl SmokeMetrics {
    fn new() -> Self {
        let meter: Meter = global::meter_with_scope(
            InstrumentationScope::builder("otel-runtime-smoke")
                .with_version(env!("CARGO_PKG_VERSION"))
                .build(),
        );

        Self {
            requests_total: meter.u64_counter("rag_runtime_smoke_requests_total").build(),
            request_duration_ms: meter
                .f64_histogram("rag_runtime_smoke_request_duration_ms")
                .build(),
            stage_duration_ms: meter
                .f64_histogram("rag_runtime_smoke_stage_duration_ms")
                .build(),
        }
    }
}

fn build_resource(service_name: &str) -> Resource {
    Resource::builder()
        .with_service_name(service_name.to_string())
        .build()
}

fn init_observability(endpoint: &str, service_name: &str) -> Result<ObservabilityGuards, Box<dyn Error>> {
    let span_exporter = opentelemetry_otlp::SpanExporter::builder()
        .with_tonic()
        .with_endpoint(endpoint)
        .build()?;

    let tracer_provider = SdkTracerProvider::builder()
        .with_batch_exporter(span_exporter)
        .with_sampler(Sampler::AlwaysOn)
        .with_resource(build_resource(service_name))
        .build();

    let tracer = tracer_provider.tracer(service_name.to_string());
    let telemetry_layer = tracing_opentelemetry::OpenTelemetryLayer::new(tracer);

    let subscriber = Registry::default()
        .with(EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")))
        .with(telemetry_layer);

    tracing::subscriber::set_global_default(subscriber)?;
    global::set_tracer_provider(tracer_provider.clone());

    let metric_exporter = opentelemetry_otlp::MetricExporter::builder()
        .with_tonic()
        .with_endpoint(endpoint)
        .build()?;

    let meter_provider = SdkMeterProvider::builder()
        .with_reader(
            PeriodicReader::builder(metric_exporter)
                .with_interval(Duration::from_secs(2))
                .build(),
        )
        .with_resource(build_resource(service_name))
        .build();

    global::set_meter_provider(meter_provider.clone());

    Ok(ObservabilityGuards {
        tracer_provider,
        meter_provider,
    })
}

async fn run_stage(
    span_name: &'static str,
    module: &'static str,
    stage: &'static str,
    request_id: &str,
    sleep_ms: u64,
    metrics: &SmokeMetrics,
) {
    let stage_started = Instant::now();
    let span = match span_name {
        "input_validation" => info_span!(
            "input_validation",
            request_id = request_id,
            "span.module" = module,
            "span.stage" = stage,
            status = field::Empty
        ),
        "retrieval.embedding" => info_span!(
            "retrieval.embedding",
            request_id = request_id,
            "span.module" = module,
            "span.stage" = stage,
            status = field::Empty
        ),
        "retrieval.vector_search" => info_span!(
            "retrieval.vector_search",
            request_id = request_id,
            "span.module" = module,
            "span.stage" = stage,
            status = field::Empty
        ),
        "generation.chat" => info_span!(
            "generation.chat",
            request_id = request_id,
            "span.module" = module,
            "span.stage" = stage,
            status = field::Empty
        ),
        _ => unreachable!("unsupported span name"),
    };
    let _enter = span.enter();
    span.record("status", "ok");
    info!("stage started");
    tokio::time::sleep(Duration::from_millis(sleep_ms)).await;
    info!("stage completed");
    metrics.stage_duration_ms.record(
        stage_started.elapsed().as_secs_f64() * 1000.0,
        &[
            KeyValue::new("module", module),
            KeyValue::new("stage", stage),
            KeyValue::new("status", "ok"),
        ],
    );
}

async fn emit_runtime_shape_smoke(request_id: &str, metrics: &SmokeMetrics) {
    let request_started = Instant::now();
    let root = info_span!(
        "rag.request",
        request_id = request_id,
        "request.id" = request_id,
        "span.module" = "orchestration",
        "span.stage" = "request",
        status = field::Empty
    );

    let _root_guard = root.enter();
    root.record("status", "ok");
    info!("starting runtime-shaped smoke request");

    metrics.requests_total.add(
        1,
        &[
            KeyValue::new("module", "orchestration"),
            KeyValue::new("stage", "request"),
        ],
    );

    run_stage("input_validation", "input_validation", "input_validation", request_id, 20, metrics)
        .await;
    run_stage("retrieval.embedding", "retrieval", "retrieval", request_id, 40, metrics).await;
    run_stage(
        "retrieval.vector_search",
        "retrieval",
        "retrieval",
        request_id,
        20,
        metrics,
    )
    .await;
    run_stage("generation.chat", "generation", "generation", request_id, 30, metrics).await;

    metrics.request_duration_ms.record(
        request_started.elapsed().as_secs_f64() * 1000.0,
        &[
            KeyValue::new("module", "orchestration"),
            KeyValue::new("stage", "request"),
            KeyValue::new("status", "ok"),
        ],
    );
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let cli = Cli::parse();

    eprintln!("effective RUST_LOG={}", std::env::var("RUST_LOG").unwrap_or_else(|_| "<unset>".to_string()));
    eprintln!("endpoint={}", cli.endpoint);
    eprintln!("service_name={}", cli.service_name);
    eprintln!("request_id={}", cli.request_id);
    eprintln!("post_run_sleep_ms={}", cli.post_run_sleep_ms);

    let guards = init_observability(&cli.endpoint, &cli.service_name)?;
    let metrics = SmokeMetrics::new();

    emit_runtime_shape_smoke(&cli.request_id, &metrics).await;

    tokio::time::sleep(Duration::from_millis(cli.post_run_sleep_ms)).await;
    guards.shutdown();

    Ok(())
}

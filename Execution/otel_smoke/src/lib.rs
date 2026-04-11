use std::error::Error;
use std::time::Duration;

use opentelemetry::global;
use opentelemetry::metrics::Meter;
use opentelemetry::trace::{Span as _, TraceContextExt as _, Tracer as _, TracerProvider as _};
use opentelemetry::{Context, InstrumentationScope, KeyValue};
use opentelemetry_otlp::WithExportConfig;
use opentelemetry_sdk::metrics::{PeriodicReader, SdkMeterProvider};
use opentelemetry_sdk::trace::{BatchConfigBuilder, BatchSpanProcessor, Sampler, SdkTracerProvider};
use opentelemetry_sdk::Resource;
use tracing::{info, info_span};
use tracing_log::LogTracer;
use tracing_opentelemetry::layer as otel_layer;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt, EnvFilter, Registry};

pub const DEFAULT_OTLP_GRPC_ENDPOINT: &str = "http://localhost:4320";
pub const DEFAULT_SERVICE_NAME: &str = "rag-runtime-otel-smoke";

pub enum TraceExportMode {
    Simple,
    Batch,
}

#[derive(Clone, Copy, Debug)]
pub enum InitMode {
    Current,
    TodoStyle,
}

pub struct ObservabilityGuards {
    pub tracer_provider: SdkTracerProvider,
    pub meter_provider: SdkMeterProvider,
}

fn build_resource(service_name: &str) -> Resource {
    Resource::builder()
        .with_service_name(service_name.to_string())
        .build()
}

pub fn init_observability(
    endpoint: &str,
    service_name: &str,
    trace_export_mode: TraceExportMode,
) -> Result<ObservabilityGuards, Box<dyn Error>> {
    let _ = trace_export_mode;

    //LogTracer::init()?;

    let otlp_exporter = opentelemetry_otlp::SpanExporter::builder()
        .with_tonic()
        .with_endpoint(endpoint)
        .build()?;

    let tracer_provider = SdkTracerProvider::builder()
        .with_batch_exporter(otlp_exporter)
        .with_resource(build_resource(service_name))
        .with_sampler(Sampler::AlwaysOn)
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

pub fn init_observability_with_mode(
    endpoint: &str,
    service_name: &str,
    trace_export_mode: TraceExportMode,
    init_mode: InitMode,
) -> Result<ObservabilityGuards, Box<dyn Error>> {
    match init_mode {
        InitMode::Current => init_observability(endpoint, service_name, trace_export_mode),
        InitMode::TodoStyle => init_observability_todo_style(endpoint, service_name),
    }
}

pub fn init_observability_todo_style(
    endpoint: &str,
    service_name: &str,
) -> Result<ObservabilityGuards, Box<dyn Error>> {
    let _ = LogTracer::init();

    let otlp_exporter = opentelemetry_otlp::SpanExporter::builder()
        .with_tonic()
        .with_endpoint(endpoint)
        .build()?;

    let tracer_provider = SdkTracerProvider::builder()
        .with_batch_exporter(otlp_exporter)
        .with_resource(build_resource(service_name))
        .with_sampler(Sampler::AlwaysOn)
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

pub fn smoke_counter() -> opentelemetry::metrics::Counter<u64> {
    let meter: Meter = global::meter_with_scope(
        InstrumentationScope::builder("otel-smoke")
            .with_version(env!("CARGO_PKG_VERSION"))
            .build(),
    );
    meter.u64_counter("otel_smoke_requests_total").build()
}

#[tracing::instrument(
    name = "input_validation",
    skip_all,
    fields(
        request_id = request_id,
        span.module = "input_validation",
        span.stage = "input_validation",
        status = "ok"
    )
)]
async fn input_validation_stage(request_id: &str, root_context: Context) {
    let tracer = global::tracer("otel-smoke-direct");
    let mut span = tracer.start_with_context("input_validation", &root_context);
    span.set_attributes([
        KeyValue::new("request_id", request_id.to_string()),
        KeyValue::new("span.module", "input_validation"),
        KeyValue::new("span.stage", "input_validation"),
        KeyValue::new("status", "ok"),
    ]);
    println!(
        "direct input_validation span trace_id={} span_id={}",
        span.span_context().trace_id(),
        span.span_context().span_id()
    );

    tokio::task::yield_now().await;
    info!("validated request");
    span.end();
}

#[tracing::instrument(
    name = "generation.chat",
    skip_all,
    fields(
        request_id = request_id,
        span.module = "generation",
        span.stage = "generation",
        status = "ok"
    )
)]
async fn generation_stage(request_id: &str, root_context: Context) {
    let tracer = global::tracer("otel-smoke-direct");
    let mut span = tracer.start_with_context("generation.chat", &root_context);
    span.set_attributes([
        KeyValue::new("request_id", request_id.to_string()),
        KeyValue::new("span.module", "generation"),
        KeyValue::new("span.stage", "generation"),
        KeyValue::new("status", "ok"),
    ]);
    println!(
        "direct generation span trace_id={} span_id={}",
        span.span_context().trace_id(),
        span.span_context().span_id()
    );

    tokio::task::yield_now().await;
    info!("generated answer");
    span.end();
}

pub async fn emit_smoke_telemetry(request_id: &str) {
    let request_counter = smoke_counter();
    let direct_tracer = global::tracer("otel-smoke-direct");

    let root = info_span!(
        "rag.request",
        request_id = request_id,
        span.module = "orchestration",
        span.stage = "request",
        status = "ok"
    );

    let _root_guard = root.enter();
    info!("starting OTEL smoke request");

    let mut root_span = direct_tracer.start("rag.request");
    root_span.set_attributes([
        KeyValue::new("request_id", request_id.to_string()),
        KeyValue::new("span.module", "orchestration"),
        KeyValue::new("span.stage", "request"),
        KeyValue::new("status", "ok"),
    ]);
    println!(
        "direct root span trace_id={} span_id={}",
        root_span.span_context().trace_id(),
        root_span.span_context().span_id()
    );
    let root_context = Context::current_with_span(root_span);

    request_counter.add(
        1,
        &[
            KeyValue::new("module", "orchestration"),
            KeyValue::new("stage", "request"),
            KeyValue::new("status", "ok"),
        ],
    );

    input_validation_stage(request_id, root_context.clone()).await;
    generation_stage(request_id, root_context.clone()).await;

    root_context.span().end();
}

pub fn shutdown_observability(guards: ObservabilityGuards) {
    if let Err(error) = guards.tracer_provider.force_flush() {
        eprintln!("tracer force_flush error: {error}");
    }
    if let Err(error) = guards.meter_provider.force_flush() {
        eprintln!("meter force_flush error: {error}");
    }
    if let Err(error) = guards.tracer_provider.shutdown() {
        eprintln!("tracer shutdown error: {error}");
    }
    if let Err(error) = guards.meter_provider.shutdown() {
        eprintln!("meter shutdown error: {error}");
    }
}

#[tracing::instrument(name = "Service::session::add", skip_all)]
pub async fn test_instrumented_span() -> Result<(), Box<dyn Error>> {
    tracing::info!(session_id = "asdasd", "create session");
    Ok(())
}

#[tracing::instrument(
    name = "input_validation",
    skip_all,
    fields(
        request_id = request_id,
        span.module = "input_validation",
        span.stage = "input_validation",
        status = tracing::field::Empty
    )
)]
async fn tracing_input_validation_stage(request_id: &str) {
    tracing::Span::current().record("status", "ok");
    info!("validated request");
}

#[tracing::instrument(
    name = "generation.chat",
    skip_all,
    fields(
        request_id = request_id,
        span.module = "generation",
        span.stage = "generation",
        status = tracing::field::Empty
    )
)]
async fn tracing_generation_stage(request_id: &str) {
    tracing::Span::current().record("status", "ok");
    info!("generated answer");
}

pub async fn emit_tracing_tree_smoke(request_id: &str) {
    let request_counter = smoke_counter();

    let root = info_span!(
        "rag.request",
        request_id = tracing::field::Empty,
        span.module = "orchestration",
        span.stage = "request",
        status = tracing::field::Empty
    );
    root.record("request_id", request_id);
    root.record("status", "ok");

    let _enter = root.enter();
    info!("starting tracing tree smoke request");

    request_counter.add(
        1,
        &[
            KeyValue::new("module", "orchestration"),
            KeyValue::new("stage", "request"),
            KeyValue::new("status", "ok"),
        ],
    );

    tracing_input_validation_stage(request_id).await;
    tracing_generation_stage(request_id).await;
}

pub async fn emit_tracing_tree_smoke_named(request_id: &str) {
    let request_counter = smoke_counter();

    let root = info_span!(
        "todo_tree.root",
        request_id = tracing::field::Empty,
        span.module = "orchestration",
        span.stage = "request",
        status = tracing::field::Empty
    );
    root.record("request_id", request_id);
    root.record("status", "ok");

    let _enter = root.enter();
    info!("starting named tracing tree smoke request");

    request_counter.add(
        1,
        &[
            KeyValue::new("module", "orchestration"),
            KeyValue::new("stage", "request"),
            KeyValue::new("status", "ok"),
        ],
    );

    let validation = info_span!(
        "todo_tree.input_validation",
        request_id = tracing::field::Empty,
        span.module = "input_validation",
        span.stage = "input_validation",
        status = tracing::field::Empty
    );
    validation.record("request_id", request_id);
    validation.record("status", "ok");
    {
        let _enter = validation.enter();
        info!("validated request in named smoke span");
    }

    let generation = info_span!(
        "todo_tree.generation",
        request_id = tracing::field::Empty,
        span.module = "generation",
        span.stage = "generation",
        status = tracing::field::Empty
    );
    generation.record("request_id", request_id);
    generation.record("status", "ok");
    {
        let _enter = generation.enter();
        info!("generated answer in named smoke span");
    }
}

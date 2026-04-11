use std::sync::{Mutex, OnceLock};
use std::time::Duration;

use opentelemetry::KeyValue;
use opentelemetry::global;
use opentelemetry::metrics::{Counter, Histogram};
use opentelemetry::trace::TracerProvider;
use opentelemetry_otlp::WithExportConfig;
use opentelemetry_sdk::Resource;
use opentelemetry_sdk::metrics::{PeriodicReader, SdkMeterProvider};
use opentelemetry_sdk::trace::{
    BatchConfigBuilder, BatchSpanProcessor, Sampler, SdkTracerProvider,
};
use tracing_subscriber::{EnvFilter, Registry, layer::SubscriberExt};

use crate::config::ObservabilitySettings;
use crate::errors::ObservabilityError;
use crate::models::RetrievalQualityMetrics;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StatusLabel {
    Ok,
    Error,
}

impl StatusLabel {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Ok => "ok",
            Self::Error => "error",
        }
    }
}

#[derive(Debug, Clone)]
pub struct RequestLabels {
    pub module: &'static str,
    pub stage: &'static str,
    pub status: &'static str,
}

#[derive(Debug, Clone)]
pub struct StageLabels {
    pub module: &'static str,
    pub stage: &'static str,
    pub status: &'static str,
}

#[derive(Debug, Clone)]
pub struct DependencyLabels {
    pub module: &'static str,
    pub dependency: &'static str,
    pub status: &'static str,
}

#[derive(Debug, Default)]
struct MetricsHandles {
    requests_total: Option<Counter<u64>>,
    requests_failed_total: Option<Counter<u64>>,
    request_duration_ms: Option<Histogram<f64>>,
    stage_duration_ms: Option<Histogram<f64>>,
    dependency_duration_ms: Option<Histogram<f64>>,
    retrieval_empty_total: Option<Counter<u64>>,
    query_token_count: Option<Histogram<u64>>,
    retrieved_chunks_count: Option<Histogram<u64>>,
    generation_input_chunks_count: Option<Histogram<u64>>,
    generation_prompt_tokens: Option<Histogram<u64>>,
    generation_completion_tokens: Option<Histogram<u64>>,
    generation_total_tokens: Option<Histogram<u64>>,
    dependency_failures_total: Option<Counter<u64>>,
    retry_attempts_total: Option<Counter<u64>>,
    retriever_result_count: Option<Histogram<u64>>,
    retrieval_top1_score: Option<Histogram<f64>>,
    retrieval_topk_mean_score: Option<Histogram<f64>>,
    llm_prompt_tokens: Option<Histogram<u64>>,
    llm_completion_tokens: Option<Histogram<u64>>,
    llm_total_tokens: Option<Histogram<u64>>,
    llm_cost_total: Option<Histogram<f64>>,
}

fn duration_histogram_boundaries_ms() -> Vec<f64> {
    vec![
        0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0, 75.0, 100.0, 250.0, 500.0, 750.0, 1_000.0,
        1_500.0, 2_000.0, 2_500.0, 5_000.0, 7_500.0, 10_000.0, 15_000.0, 30_000.0, 45_000.0,
        60_000.0, 90_000.0, 120_000.0, 180_000.0,
    ]
}

impl MetricsHandles {
    fn from_meter(meter: &opentelemetry::metrics::Meter) -> Self {
        let duration_boundaries = duration_histogram_boundaries_ms();
        Self {
            requests_total: Some(meter.u64_counter("rag_requests_total").build()),
            requests_failed_total: Some(meter.u64_counter("rag_requests_failed_total").build()),
            request_duration_ms: Some(
                meter
                    .f64_histogram("rag_request_duration_ms")
                    .with_boundaries(duration_boundaries.clone())
                    .build(),
            ),
            stage_duration_ms: Some(
                meter
                    .f64_histogram("rag_stage_duration_ms")
                    .with_boundaries(duration_boundaries.clone())
                    .build(),
            ),
            dependency_duration_ms: Some(
                meter
                    .f64_histogram("rag_dependency_duration_ms")
                    .with_boundaries(duration_boundaries)
                    .build(),
            ),
            retrieval_empty_total: Some(meter.u64_counter("rag_retrieval_empty_total").build()),
            query_token_count: Some(meter.u64_histogram("rag_query_token_count").build()),
            retrieved_chunks_count: Some(meter.u64_histogram("rag_retrieved_chunks_count").build()),
            generation_input_chunks_count: Some(
                meter
                    .u64_histogram("rag_generation_input_chunks_count")
                    .build(),
            ),
            generation_prompt_tokens: Some(
                meter.u64_histogram("rag_generation_prompt_tokens").build(),
            ),
            generation_completion_tokens: Some(
                meter
                    .u64_histogram("rag_generation_completion_tokens")
                    .build(),
            ),
            generation_total_tokens: Some(
                meter.u64_histogram("rag_generation_total_tokens").build(),
            ),
            dependency_failures_total: Some(
                meter.u64_counter("rag_dependency_failures_total").build(),
            ),
            retry_attempts_total: Some(meter.u64_counter("rag_retry_attempts_total").build()),
            retriever_result_count: Some(meter.u64_histogram("rag_retriever_result_count").build()),
            retrieval_top1_score: Some(meter.f64_histogram("rag_retrieval_top1_score").build()),
            retrieval_topk_mean_score: Some(
                meter.f64_histogram("rag_retrieval_topk_mean_score").build(),
            ),
            llm_prompt_tokens: Some(meter.u64_histogram("rag_llm_prompt_tokens").build()),
            llm_completion_tokens: Some(meter.u64_histogram("rag_llm_completion_tokens").build()),
            llm_total_tokens: Some(meter.u64_histogram("rag_llm_total_tokens").build()),
            llm_cost_total: Some(meter.f64_histogram("rag_llm_cost_total").build()),
        }
    }
}

fn metrics_cell() -> &'static Mutex<MetricsHandles> {
    static METRICS: OnceLock<Mutex<MetricsHandles>> = OnceLock::new();
    METRICS.get_or_init(|| Mutex::new(MetricsHandles::default()))
}

fn replace_metrics(handles: MetricsHandles) {
    let mut guard = metrics_cell()
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner());
    *guard = handles;
}

fn with_metrics<T>(f: impl FnOnce(&MetricsHandles) -> T) -> T {
    let guard = metrics_cell()
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner());
    f(&guard)
}

pub struct ObservabilityRuntime {
    tracing_guard: Option<TracingGuard>,
    metrics_guard: Option<MetricsGuard>,
}

pub struct TracingGuard {
    provider: SdkTracerProvider,
}

pub struct MetricsGuard {
    provider: SdkMeterProvider,
}

fn build_resource(service_name: &str) -> Resource {
    Resource::builder()
        .with_service_name(service_name.to_string())
        .build()
}

impl Drop for TracingGuard {
    fn drop(&mut self) {
        let _ = self.provider.shutdown();
    }
}

impl Drop for MetricsGuard {
    fn drop(&mut self) {
        let _ = self.provider.shutdown();
    }
}

impl ObservabilityRuntime {
    pub fn initialize(settings: &ObservabilitySettings) -> Result<Self, ObservabilityError> {
        let tracing_guard = if settings.tracing_enabled {
            Some(init_tracing(settings)?)
        } else {
            None
        };

        let metrics_guard = if settings.metrics_enabled {
            let guard = init_metrics(settings)?;
            let meter = global::meter("rag_runtime");
            replace_metrics(MetricsHandles::from_meter(&meter));
            Some(guard)
        } else {
            replace_metrics(MetricsHandles::default());
            None
        };

        Ok(Self {
            tracing_guard,
            metrics_guard,
        })
    }

    pub fn flush(&self) {
        if let Some(guard) = &self.tracing_guard {
            let _ = guard.provider.force_flush();
        }
        if let Some(guard) = &self.metrics_guard {
            let _ = guard.provider.force_flush();
        }
    }

    pub fn request_labels(&self, status: StatusLabel) -> RequestLabels {
        request_labels(status)
    }

    pub fn stage_labels(
        &self,
        module: &'static str,
        stage: &'static str,
        status: StatusLabel,
    ) -> StageLabels {
        stage_labels(module, stage, status)
    }

    pub fn dependency_labels(
        &self,
        module: &'static str,
        dependency: &'static str,
        status: StatusLabel,
    ) -> DependencyLabels {
        dependency_labels(module, dependency, status)
    }

    pub fn record_request_open(&self) {}

    pub fn record_request_failure(&self) {
        record_request_close(0.0, StatusLabel::Error);
    }

    pub fn record_request_close(&self, duration_ms: f64) {
        record_request_close(duration_ms, StatusLabel::Ok);
    }

    pub fn record_retrieval_empty(&self) {
        record_retrieval_empty();
    }

    pub fn record_retrieved_chunk_count(&self, count: usize) {
        record_retrieved_chunk_count(count);
    }

    pub fn record_query_token_count(&self, count: usize) {
        record_query_token_count(count);
    }

    pub fn record_generation_input_chunk_count(&self, count: usize) {
        record_generation_input_chunk_count(count);
    }

    pub fn record_retry_attempt(&self, dependency: &'static str) {
        record_retry_attempt(dependency);
    }

    #[cfg(test)]
    pub fn disabled_for_tests() -> Self {
        replace_metrics(MetricsHandles::default());
        Self {
            tracing_guard: None,
            metrics_guard: None,
        }
    }
}

pub(crate) fn request_labels(status: StatusLabel) -> RequestLabels {
    RequestLabels {
        module: "orchestration",
        stage: "request",
        status: status.as_str(),
    }
}

pub(crate) fn stage_labels(
    module: &'static str,
    stage: &'static str,
    status: StatusLabel,
) -> StageLabels {
    StageLabels {
        module,
        stage,
        status: status.as_str(),
    }
}

pub(crate) fn dependency_labels(
    module: &'static str,
    dependency: &'static str,
    status: StatusLabel,
) -> DependencyLabels {
    DependencyLabels {
        module,
        dependency,
        status: status.as_str(),
    }
}

pub(crate) fn mark_span_ok() {
    let span = tracing::Span::current();
    span.record("status", "ok");
}

pub(crate) fn record_request_close(duration_ms: f64, status: StatusLabel) {
    with_metrics(|metrics| {
        let labels = request_metric_labels();
        if let Some(counter) = &metrics.requests_total {
            counter.add(1, &labels);
        }
        if status == StatusLabel::Error {
            if let Some(counter) = &metrics.requests_failed_total {
                counter.add(1, &labels);
            }
        }
        if let Some(histogram) = &metrics.request_duration_ms {
            histogram.record(duration_ms, &request_duration_labels(status));
        }
    });
}

pub(crate) fn record_stage_close(
    module: &'static str,
    stage: &'static str,
    duration_ms: f64,
    status: StatusLabel,
) {
    with_metrics(|metrics| {
        if let Some(histogram) = &metrics.stage_duration_ms {
            histogram.record(duration_ms, &stage_duration_labels(module, stage, status));
        }
    });
}

pub(crate) fn record_reranking_stage_close(
    reranker_kind: &'static str,
    duration_ms: f64,
    status: StatusLabel,
) {
    let _ = reranker_kind;
    record_stage_close("reranking", "reranking", duration_ms, status);
}

pub(crate) fn record_dependency_close(
    module: &'static str,
    stage: &'static str,
    dependency: &'static str,
    duration_ms: f64,
    status: StatusLabel,
) {
    with_metrics(|metrics| {
        if let Some(histogram) = &metrics.dependency_duration_ms {
            histogram.record(
                duration_ms,
                &dependency_duration_labels(module, stage, dependency, status),
            );
        }
        if status == StatusLabel::Error {
            if let Some(counter) = &metrics.dependency_failures_total {
                counter.add(1, &dependency_counter_labels(module, stage, dependency));
            }
        }
    });
}

pub(crate) fn record_retrieval_empty() {
    with_metrics(|metrics| {
        if let Some(counter) = &metrics.retrieval_empty_total {
            counter.add(1, &stage_counter_labels("retrieval", "retrieval"));
        }
    });
}

pub(crate) fn record_query_token_count(count: usize) {
    with_metrics(|metrics| {
        if let Some(histogram) = &metrics.query_token_count {
            histogram.record(
                count as u64,
                &stage_counter_labels("input_validation", "input_validation"),
            );
        }
    });
}

pub(crate) fn record_retrieved_chunk_count(count: usize) {
    with_metrics(|metrics| {
        if let Some(histogram) = &metrics.retrieved_chunks_count {
            histogram.record(
                count as u64,
                &stage_counter_labels("retrieval", "retrieval"),
            );
        }
    });
}

pub(crate) fn record_generation_input_chunk_count(count: usize) {
    with_metrics(|metrics| {
        if let Some(histogram) = &metrics.generation_input_chunks_count {
            histogram.record(
                count as u64,
                &stage_counter_labels("generation", "generation"),
            );
        }
    });
}

pub(crate) fn record_generation_prompt_tokens(
    prompt_tokens: usize,
    provider: &'static str,
    model: &str,
) {
    with_metrics(|metrics| {
        if let Some(histogram) = &metrics.generation_prompt_tokens {
            histogram.record(
                prompt_tokens as u64,
                &stage_counter_labels("generation", "generation"),
            );
        }
        if let Some(histogram) = &metrics.llm_prompt_tokens {
            histogram.record(
                prompt_tokens as u64,
                &llm_labels("generation", "generation", provider, Some(model)),
            );
        }
    });
}

pub(crate) fn record_generation_completion_tokens(
    completion_tokens: usize,
    total_tokens: usize,
    provider: &'static str,
    model: &str,
) {
    with_metrics(|metrics| {
        if let Some(histogram) = &metrics.generation_completion_tokens {
            histogram.record(
                completion_tokens as u64,
                &stage_counter_labels("generation", "generation"),
            );
        }
        if let Some(histogram) = &metrics.generation_total_tokens {
            histogram.record(
                total_tokens as u64,
                &stage_counter_labels("generation", "generation"),
            );
        }
        if let Some(histogram) = &metrics.llm_completion_tokens {
            histogram.record(
                completion_tokens as u64,
                &llm_labels("generation", "generation", provider, Some(model)),
            );
        }
        if let Some(histogram) = &metrics.llm_total_tokens {
            histogram.record(
                total_tokens as u64,
                &llm_labels("generation", "generation", provider, Some(model)),
            );
        }
    });
}

pub(crate) fn record_generation_cost_total(
    total_cost_usd: f64,
    provider: &'static str,
    model: &str,
) {
    with_metrics(|metrics| {
        if let Some(histogram) = &metrics.llm_cost_total {
            histogram.record(
                total_cost_usd,
                &llm_labels("generation", "generation", provider, Some(model)),
            );
        }
    });
}

pub(crate) fn record_retry_attempt(dependency: &'static str) {
    let (module, stage) = match dependency {
        "chat" => ("generation", "generation"),
        "rerank" => ("reranking", "reranking"),
        "input_validation.tokenizer" => ("startup", "input_validation_init"),
        "generation.tokenizer" => ("startup", "generation_init"),
        _ => ("retrieval", "retrieval"),
    };
    with_metrics(|metrics| {
        if let Some(counter) = &metrics.retry_attempts_total {
            counter.add(1, &dependency_counter_labels(module, stage, dependency));
        }
    });
}

pub(crate) fn record_retry_attempts(dependency: &'static str, count: usize) {
    for _ in 0..count {
        record_retry_attempt(dependency);
    }
}

/// Records retrieval-quality metric attributes onto the `retrieval.vector_search` span.
///
/// All scalar metrics are recorded unconditionally.
/// `first_relevant_rank_soft` and `first_relevant_rank_strict` are recorded only when `Some`.
pub(crate) fn record_retrieval_quality_attributes(
    span: &tracing::Span,
    metrics: &RetrievalQualityMetrics,
) {
    span.record("retrieval_recall_soft", metrics.recall_soft as f64);
    span.record("retrieval_recall_strict", metrics.recall_strict as f64);
    span.record("retrieval_rr_soft", metrics.rr_soft as f64);
    span.record("retrieval_rr_strict", metrics.rr_strict as f64);
    span.record("retrieval_ndcg", metrics.ndcg as f64);
    span.record(
        "retrieval_num_relevant_soft",
        metrics.num_relevant_soft as i64,
    );
    span.record(
        "retrieval_num_relevant_strict",
        metrics.num_relevant_strict as i64,
    );
    if let Some(rank) = metrics.first_relevant_rank_soft {
        span.record("retrieval_first_relevant_rank_soft", rank as i64);
    }
    if let Some(rank) = metrics.first_relevant_rank_strict {
        span.record("retrieval_first_relevant_rank_strict", rank as i64);
    }
}

/// Records reranking-quality metric attributes onto the `reranking.rank` span.
///
/// Attribute names and semantics are identical to `record_retrieval_quality_attributes`.
pub(crate) fn record_reranking_quality_attributes(
    span: &tracing::Span,
    metrics: &RetrievalQualityMetrics,
) {
    span.record("context_recall_soft", metrics.recall_soft as f64);
    span.record("context_recall_strict", metrics.recall_strict as f64);
    span.record("context_rr_soft", metrics.rr_soft as f64);
    span.record("context_rr_strict", metrics.rr_strict as f64);
    span.record("context_ndcg", metrics.ndcg as f64);
    span.record(
        "context_num_relevant_soft",
        metrics.num_relevant_soft as i64,
    );
    span.record(
        "context_num_relevant_strict",
        metrics.num_relevant_strict as i64,
    );
    if let Some(rank) = metrics.first_relevant_rank_soft {
        span.record("context_first_relevant_rank_soft", rank as i64);
    }
    if let Some(rank) = metrics.first_relevant_rank_strict {
        span.record("context_first_relevant_rank_strict", rank as i64);
    }
}

/// Records retrieval-quality aggregate attributes onto the `rag.request` root span.
///
/// - `retrieval_context_loss_*` — emitted only when both metric bundles are `Some`.
/// - `first_relevant_rank_retrieval_*` / `first_relevant_rank_context_*` — emitted only when the
///   underlying `first_relevant_rank` field is `Some(...)`.
/// - `num_relevant_in_retrieval_topk_*` / `num_relevant_in_context_topk_*` — emitted whenever
///   the respective metric bundle is `Some`.
pub(crate) fn record_request_retrieval_quality_aggregates(
    span: &tracing::Span,
    retrieval_metrics: Option<&RetrievalQualityMetrics>,
    reranking_metrics: Option<&RetrievalQualityMetrics>,
) {
    if let (Some(ret), Some(rer)) = (retrieval_metrics, reranking_metrics) {
        span.record(
            "summary_retrieval_context_loss_soft",
            (ret.recall_soft - rer.recall_soft) as f64,
        );
        span.record(
            "summary_retrieval_context_loss_strict",
            (ret.recall_strict - rer.recall_strict) as f64,
        );
    }

    if let Some(ret) = retrieval_metrics {
        if let Some(rank) = ret.first_relevant_rank_soft {
            span.record("summary_first_relevant_rank_retrieval_soft", rank as i64);
        }
        if let Some(rank) = ret.first_relevant_rank_strict {
            span.record("summary_first_relevant_rank_retrieval_strict", rank as i64);
        }
        span.record(
            "summary_num_relevant_in_retrieval_topk_soft",
            ret.num_relevant_soft as i64,
        );
        span.record(
            "summary_num_relevant_in_retrieval_topk_strict",
            ret.num_relevant_strict as i64,
        );
    }

    if let Some(rer) = reranking_metrics {
        if let Some(rank) = rer.first_relevant_rank_soft {
            span.record("summary_first_relevant_rank_context_soft", rank as i64);
        }
        if let Some(rank) = rer.first_relevant_rank_strict {
            span.record("summary_first_relevant_rank_context_strict", rank as i64);
        }
        span.record(
            "summary_num_relevant_in_context_topk_soft",
            rer.num_relevant_soft as i64,
        );
        span.record(
            "summary_num_relevant_in_context_topk_strict",
            rer.num_relevant_strict as i64,
        );
    }
}

pub(crate) fn record_retriever_semantic_metrics(scores: &[f32]) {
    with_metrics(|metrics| {
        if let Some(histogram) = &metrics.retriever_result_count {
            histogram.record(
                scores.len() as u64,
                &stage_counter_labels("retrieval", "retrieval"),
            );
        }
        if let Some(first) = scores.first() {
            if let Some(histogram) = &metrics.retrieval_top1_score {
                histogram.record(
                    *first as f64,
                    &stage_counter_labels("retrieval", "retrieval"),
                );
            }
            if let Some(histogram) = &metrics.retrieval_topk_mean_score {
                let mean =
                    scores.iter().map(|score| *score as f64).sum::<f64>() / scores.len() as f64;
                histogram.record(mean, &stage_counter_labels("retrieval", "retrieval"));
            }
        }
    });
}

fn stage_counter_labels(module: &'static str, stage: &'static str) -> [KeyValue; 2] {
    [
        KeyValue::new("module", module),
        KeyValue::new("stage", stage),
    ]
}

fn request_metric_labels() -> [KeyValue; 2] {
    stage_counter_labels("orchestration", "request")
}

fn request_duration_labels(status: StatusLabel) -> [KeyValue; 3] {
    [
        KeyValue::new("module", "orchestration"),
        KeyValue::new("stage", "request"),
        KeyValue::new("status", status.as_str()),
    ]
}

fn stage_duration_labels(
    module: &'static str,
    stage: &'static str,
    status: StatusLabel,
) -> [KeyValue; 3] {
    [
        KeyValue::new("module", module),
        KeyValue::new("stage", stage),
        KeyValue::new("status", status.as_str()),
    ]
}

fn dependency_duration_labels(
    module: &'static str,
    stage: &'static str,
    dependency: &'static str,
    status: StatusLabel,
) -> [KeyValue; 4] {
    [
        KeyValue::new("module", module),
        KeyValue::new("stage", stage),
        KeyValue::new("dependency", dependency),
        KeyValue::new("status", status.as_str()),
    ]
}

fn dependency_counter_labels(
    module: &'static str,
    stage: &'static str,
    dependency: &'static str,
) -> [KeyValue; 3] {
    [
        KeyValue::new("module", module),
        KeyValue::new("stage", stage),
        KeyValue::new("dependency", dependency),
    ]
}

fn llm_labels(
    module: &'static str,
    stage: &'static str,
    provider: &'static str,
    model: Option<&str>,
) -> [KeyValue; 4] {
    [
        KeyValue::new("module", module),
        KeyValue::new("stage", stage),
        KeyValue::new("provider", provider),
        KeyValue::new("model", model.unwrap_or("unknown").to_string()),
    ]
}

pub(crate) fn ordered_page_locator(page_start: i64, page_end: i64) -> String {
    if page_start == page_end {
        format!("page:{page_start}")
    } else {
        format!("pages:{page_start}-{page_end}")
    }
}

fn init_tracing(settings: &ObservabilitySettings) -> Result<TracingGuard, ObservabilityError> {
    let otlp_exporter = opentelemetry_otlp::SpanExporter::builder()
        .with_tonic()
        .with_endpoint(&settings.tracing_endpoint)
        .build()
        .map_err(|error| ObservabilityError::Initialization {
            message: format!("failed to build trace exporter: {error}"),
        })?;

    let batch_processor = BatchSpanProcessor::builder(otlp_exporter)
        .with_batch_config(
            BatchConfigBuilder::default()
                .with_scheduled_delay(Duration::from_millis(
                    settings.trace_batch_scheduled_delay_ms,
                ))
                .build(),
        )
        .build();

    let tracer_provider = SdkTracerProvider::builder()
        .with_span_processor(batch_processor)
        .with_sampler(Sampler::AlwaysOn)
        .with_resource(build_resource("rag_runtime"))
        .build();

    let tracer = tracer_provider.tracer("rag_runtime".to_string());
    let telemetry_layer = tracing_opentelemetry::OpenTelemetryLayer::new(tracer);

    let subscriber = Registry::default()
        .with(EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")))
        .with(telemetry_layer);

    tracing::subscriber::set_global_default(subscriber).map_err(|error| {
        ObservabilityError::Initialization {
            message: format!("failed to install global tracing subscriber: {error}"),
        }
    })?;
    global::set_tracer_provider(tracer_provider.clone());
    Ok(TracingGuard {
        provider: tracer_provider,
    })
}

fn init_metrics(settings: &ObservabilitySettings) -> Result<MetricsGuard, ObservabilityError> {
    let exporter = opentelemetry_otlp::MetricExporter::builder()
        .with_tonic()
        .with_endpoint(&settings.metrics_endpoint)
        .build()
        .map_err(|error| ObservabilityError::Initialization {
            message: format!("failed to build metric exporter: {error}"),
        })?;
    let provider = SdkMeterProvider::builder()
        .with_reader(
            PeriodicReader::builder(exporter)
                .with_interval(Duration::from_millis(settings.metrics_export_interval_ms))
                .build(),
        )
        .with_resource(build_resource("rag_runtime"))
        .build();
    global::set_meter_provider(provider.clone());
    Ok(MetricsGuard { provider })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_support::disabled_observability_settings;

    #[test]
    fn initialization_succeeds_when_disabled() {
        let runtime = ObservabilityRuntime::initialize(&disabled_observability_settings()).unwrap();
        runtime.record_request_open();
        runtime.record_request_failure();
        runtime.record_request_close(1.0);
    }

    #[test]
    fn request_label_construction_returns_required_keys() {
        let runtime = ObservabilityRuntime::disabled_for_tests();
        let labels = runtime.request_labels(StatusLabel::Ok);
        assert_eq!(labels.module, "orchestration");
        assert_eq!(labels.stage, "request");
        assert_eq!(labels.status, "ok");
    }

    #[test]
    fn stage_label_construction_returns_required_keys() {
        let runtime = ObservabilityRuntime::disabled_for_tests();
        let labels = runtime.stage_labels("retrieval", "retrieval", StatusLabel::Error);
        assert_eq!(labels.module, "retrieval");
        assert_eq!(labels.stage, "retrieval");
        assert_eq!(labels.status, "error");
    }

    #[test]
    fn dependency_label_construction_returns_required_keys() {
        let runtime = ObservabilityRuntime::disabled_for_tests();
        let labels = runtime.dependency_labels("generation", "chat", StatusLabel::Ok);
        assert_eq!(labels.module, "generation");
        assert_eq!(labels.dependency, "chat");
        assert_eq!(labels.status, "ok");
    }

    #[test]
    fn status_label_maps_to_exact_strings() {
        assert_eq!(StatusLabel::Ok.as_str(), "ok");
        assert_eq!(StatusLabel::Error.as_str(), "error");
    }

    #[test]
    fn metric_recording_methods_do_not_panic_when_disabled() {
        let runtime = ObservabilityRuntime::disabled_for_tests();
        runtime.record_request_open();
        runtime.record_request_failure();
        runtime.record_request_close(42.0);
        runtime.record_retrieval_empty();
        runtime.record_query_token_count(2);
        runtime.record_retrieved_chunk_count(1);
        runtime.record_generation_input_chunk_count(1);
        runtime.record_retry_attempt("chat");
        record_stage_close("generation", "generation", 1.0, StatusLabel::Ok);
        record_dependency_close(
            "retrieval",
            "retrieval",
            "embedding",
            1.0,
            StatusLabel::Error,
        );
        record_generation_prompt_tokens(5, "ollama", "model");
        record_generation_completion_tokens(3, 8, "ollama", "model");
        record_generation_cost_total(0.01, "ollama", "model");
        record_retriever_semantic_metrics(&[0.9, 0.7]);
    }

    #[test]
    fn request_labels_can_be_error_status() {
        let runtime = ObservabilityRuntime::disabled_for_tests();
        let labels = runtime.request_labels(StatusLabel::Error);
        assert_eq!(labels.status, "error");
    }

    #[tokio::test]
    async fn initialization_with_tracing_enabled_returns_runtime() {
        let mut settings = disabled_observability_settings();
        settings.tracing_enabled = true;
        settings.tracing_endpoint = "not-a-valid-endpoint".to_string();
        let result = ObservabilityRuntime::initialize(&settings);
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn initialization_with_metrics_enabled_returns_runtime() {
        let mut settings = disabled_observability_settings();
        settings.metrics_enabled = true;
        settings.metrics_endpoint = "not-a-valid-endpoint".to_string();
        let result = ObservabilityRuntime::initialize(&settings);
        assert!(result.is_ok());
    }

    #[test]
    fn disabled_runtime_has_no_guards() {
        let runtime = ObservabilityRuntime::disabled_for_tests();
        assert!(runtime.tracing_guard.is_none());
        assert!(runtime.metrics_guard.is_none());
    }

    #[test]
    fn page_locator_uses_compact_contract_format() {
        assert_eq!(ordered_page_locator(2, 2), "page:2");
        assert_eq!(ordered_page_locator(2, 4), "pages:2-4");
    }

    #[test]
    fn retrieval_quality_attributes_do_not_panic_on_disabled_runtime() {
        let _runtime = ObservabilityRuntime::disabled_for_tests();
        let span = tracing::info_span!(
            "test.retrieval.vector_search",
            retrieval_recall_soft = tracing::field::Empty,
            retrieval_recall_strict = tracing::field::Empty,
            retrieval_rr_soft = tracing::field::Empty,
            retrieval_rr_strict = tracing::field::Empty,
            retrieval_ndcg = tracing::field::Empty,
            retrieval_num_relevant_soft = tracing::field::Empty,
            retrieval_num_relevant_strict = tracing::field::Empty,
            retrieval_first_relevant_rank_soft = tracing::field::Empty,
            retrieval_first_relevant_rank_strict = tracing::field::Empty,
            context_recall_soft = tracing::field::Empty,
            context_recall_strict = tracing::field::Empty,
            context_rr_soft = tracing::field::Empty,
            context_rr_strict = tracing::field::Empty,
            context_ndcg = tracing::field::Empty,
            context_num_relevant_soft = tracing::field::Empty,
            context_num_relevant_strict = tracing::field::Empty,
            context_first_relevant_rank_soft = tracing::field::Empty,
            context_first_relevant_rank_strict = tracing::field::Empty,
        );
        let metrics = crate::models::RetrievalQualityMetrics {
            evaluated_k: 12,
            recall_soft: 0.75,
            recall_strict: 0.5,
            rr_soft: 1.0,
            rr_strict: 0.5,
            ndcg: 0.8,
            first_relevant_rank_soft: Some(1),
            first_relevant_rank_strict: None,
            num_relevant_soft: 3,
            num_relevant_strict: 2,
        };
        record_retrieval_quality_attributes(&span, &metrics);
        record_reranking_quality_attributes(&span, &metrics);
    }

    #[test]
    fn request_aggregates_do_not_panic_when_both_metrics_present() {
        let _runtime = ObservabilityRuntime::disabled_for_tests();
        let span = tracing::info_span!(
            "test.rag.request",
            summary_retrieval_context_loss_soft = tracing::field::Empty,
            summary_retrieval_context_loss_strict = tracing::field::Empty,
            summary_first_relevant_rank_retrieval_soft = tracing::field::Empty,
            summary_first_relevant_rank_retrieval_strict = tracing::field::Empty,
            summary_first_relevant_rank_context_soft = tracing::field::Empty,
            summary_first_relevant_rank_context_strict = tracing::field::Empty,
            summary_num_relevant_in_retrieval_topk_soft = tracing::field::Empty,
            summary_num_relevant_in_retrieval_topk_strict = tracing::field::Empty,
            summary_num_relevant_in_context_topk_soft = tracing::field::Empty,
            summary_num_relevant_in_context_topk_strict = tracing::field::Empty,
        );
        let ret = crate::models::RetrievalQualityMetrics {
            evaluated_k: 12,
            recall_soft: 0.75,
            recall_strict: 0.5,
            rr_soft: 1.0,
            rr_strict: 0.5,
            ndcg: 0.8,
            first_relevant_rank_soft: Some(1),
            first_relevant_rank_strict: None,
            num_relevant_soft: 3,
            num_relevant_strict: 2,
        };
        let rer = crate::models::RetrievalQualityMetrics {
            evaluated_k: 4,
            recall_soft: 0.5,
            recall_strict: 0.25,
            rr_soft: 1.0,
            rr_strict: 0.0,
            ndcg: 0.6,
            first_relevant_rank_soft: None,
            first_relevant_rank_strict: None,
            num_relevant_soft: 2,
            num_relevant_strict: 1,
        };
        record_request_retrieval_quality_aggregates(&span, Some(&ret), Some(&rer));
        record_request_retrieval_quality_aggregates(&span, None, None);
        record_request_retrieval_quality_aggregates(&span, Some(&ret), None);
    }
}

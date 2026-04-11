use std::env;
use std::path::{Path, PathBuf};

use config::{Config, File};
use jsonschema::draft202012;
use serde::Deserialize;
use serde_json::Value;

use crate::errors::RagRuntimeError;

const ROOT_ENV_FILE: &str = ".env";

#[derive(Debug, Clone, PartialEq)]
pub struct Settings {
    pub pipeline: PipelineSettings,
    pub input_validation: InputValidationSettings,
    pub retrieval: RetrievalSettings,
    pub generation: GenerationSettings,
    pub reranking: RerankingSettings,
    pub observability: ObservabilitySettings,
    pub request_capture: RequestCaptureSettings,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
pub struct PipelineSettings {
    pub config_version: String,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
pub struct InputValidationSettings {
    pub max_query_tokens: usize,
    pub tokenizer_source: String,
    pub reject_empty_query: bool,
    pub trim_whitespace: bool,
    pub collapse_internal_whitespace: bool,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
pub struct RetrySettings {
    pub max_attempts: usize,
    pub backoff: RetryBackoff,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum RetryBackoff {
    Exponential,
}

#[derive(Debug, Clone, PartialEq)]
pub struct RetrievalSettings {
    pub kind: RetrievalKind,
    pub ollama_url: String,
    pub qdrant_url: String,
    pub retriever_version: String,
    pub top_k: usize,
    pub score_threshold: f32,
    pub embedding_retry: RetrySettings,
    pub qdrant_retry: RetrySettings,
    pub ingest: RetrievalIngest,
}

#[derive(Debug, Clone, Copy, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum RetrievalKind {
    Dense,
    Hybrid,
}

#[derive(Debug, Clone, PartialEq)]
pub enum RetrievalIngest {
    Dense(DenseRetrievalIngest),
    Hybrid(HybridRetrievalIngest),
}

#[derive(Debug, Clone, PartialEq)]
pub struct DenseRetrievalIngest {
    pub embedding_model_name: String,
    pub embedding_dimension: usize,
    pub qdrant_collection_name: String,
    pub qdrant_vector_name: String,
    pub corpus_version: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct HybridRetrievalIngest {
    pub embedding_model_name: String,
    pub embedding_dimension: usize,
    pub qdrant_collection_name: String,
    pub dense_vector_name: String,
    pub sparse_vector_name: String,
    pub corpus_version: String,
    pub tokenizer_library: String,
    pub tokenizer_source: String,
    pub tokenizer_revision: Option<String>,
    pub preprocessing_kind: String,
    pub lowercase: bool,
    pub min_token_length: usize,
    pub vocabulary_path: String,
    pub strategy: RetrievalStrategy,
}

#[derive(Debug, Clone, PartialEq)]
pub enum RetrievalStrategy {
    BagOfWords(BagOfWordsRetrievalStrategy),
    Bm25Like(Bm25LikeRetrievalStrategy),
}

#[derive(Debug, Clone, PartialEq)]
pub struct BagOfWordsRetrievalStrategy {
    pub version: String,
    pub query_weighting: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Bm25LikeRetrievalStrategy {
    pub version: String,
    pub query_weighting: String,
    pub k1: f32,
    pub b: f32,
    pub idf_smoothing: String,
    pub term_stats_path: String,
}

impl RetrievalSettings {
    pub fn embedding_model_name(&self) -> &str {
        self.ingest.embedding_model_name()
    }

    pub fn embedding_dimension(&self) -> usize {
        self.ingest.embedding_dimension()
    }

    pub fn qdrant_collection_name(&self) -> &str {
        self.ingest.qdrant_collection_name()
    }

    pub fn corpus_version(&self) -> &str {
        self.ingest.corpus_version()
    }
}

impl RetrievalIngest {
    pub fn embedding_model_name(&self) -> &str {
        match self {
            Self::Dense(settings) => &settings.embedding_model_name,
            Self::Hybrid(settings) => &settings.embedding_model_name,
        }
    }

    pub fn embedding_dimension(&self) -> usize {
        match self {
            Self::Dense(settings) => settings.embedding_dimension,
            Self::Hybrid(settings) => settings.embedding_dimension,
        }
    }

    pub fn qdrant_collection_name(&self) -> &str {
        match self {
            Self::Dense(settings) => &settings.qdrant_collection_name,
            Self::Hybrid(settings) => &settings.qdrant_collection_name,
        }
    }

    pub fn corpus_version(&self) -> &str {
        match self {
            Self::Dense(settings) => &settings.corpus_version,
            Self::Hybrid(settings) => &settings.corpus_version,
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct GenerationSettings {
    pub transport: TransportSettings,
    pub tokenizer_source: String,
    pub temperature: f32,
    pub max_context_chunks: usize,
    pub max_prompt_tokens: usize,
    pub retry: RetrySettings,
}

impl GenerationSettings {
    pub fn transport_model_name(&self) -> &str {
        match &self.transport {
            TransportSettings::Ollama(s) => &s.model_name,
            TransportSettings::OpenAi(s) => &s.model_name,
        }
    }

    pub fn transport_url(&self) -> &str {
        match &self.transport {
            TransportSettings::Ollama(s) => &s.url,
            TransportSettings::OpenAi(s) => &s.url,
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub enum TransportSettings {
    Ollama(OllamaTransportSettings),
    OpenAi(OpenAiTransportSettings),
}

#[derive(Debug, Clone, PartialEq)]
pub struct OllamaTransportSettings {
    pub url: String,
    pub model_name: String,
    pub timeout_sec: u64,
    pub input_cost_per_million_tokens: f64,
    pub output_cost_per_million_tokens: f64,
}

#[derive(Debug, Clone, PartialEq)]
pub struct OpenAiTransportSettings {
    pub url: String,
    pub api_key: String,
    pub model_name: String,
    pub timeout_sec: u64,
    pub input_cost_per_million_tokens: f64,
    pub output_cost_per_million_tokens: f64,
}

#[derive(Debug, Clone, Copy, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum RerankerKind {
    PassThrough,
    Heuristic,
    CrossEncoder,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
pub struct HeuristicWeights {
    pub retrieval_score: f32,
    pub query_term_coverage: f32,
    pub phrase_match_bonus: f32,
    pub title_section_match_bonus: f32,
}

#[derive(Debug, Clone, PartialEq)]
pub struct RerankingSettings {
    pub reranker: RerankerSettings,
    pub candidate_k: usize,
    pub final_k: usize,
}

#[derive(Debug, Clone, PartialEq)]
pub enum RerankerSettings {
    PassThrough,
    Heuristic(HeuristicRerankerSettings),
    CrossEncoder(CrossEncoderRerankerSettings),
}

#[derive(Debug, Clone, PartialEq)]
pub struct HeuristicRerankerSettings {
    pub weights: HeuristicWeights,
}

#[derive(Debug, Clone, PartialEq)]
pub struct CrossEncoderRerankerSettings {
    pub transport: CrossEncoderTransportSettings,
}

#[derive(Debug, Clone, PartialEq)]
pub enum CrossEncoderTransportSettings {
    MixedbreadAi(MixedbreadAiCrossEncoderTransportSettings),
    VoyageAi(VoyageAiCrossEncoderTransportSettings),
}

#[derive(Debug, Clone, PartialEq)]
pub struct MixedbreadAiCrossEncoderTransportSettings {
    pub url: String,
    pub model_name: String,
    pub batch_size: usize,
    pub timeout_sec: u64,
    pub cost_per_million_tokens: f64,
    pub tokenizer_source: String,
    pub max_attempts: usize,
    pub backoff: RetryBackoff,
}

#[derive(Debug, Clone, PartialEq)]
pub struct VoyageAiCrossEncoderTransportSettings {
    pub url: String,
    pub api_key: String,
    pub model_name: String,
    pub batch_size: usize,
    pub timeout_sec: u64,
    pub cost_per_million_tokens: f64,
    pub max_attempts: usize,
    pub backoff: RetryBackoff,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
pub struct ObservabilitySettings {
    pub tracing_enabled: bool,
    pub metrics_enabled: bool,
    pub tracing_endpoint: String,
    pub metrics_endpoint: String,
    pub trace_batch_scheduled_delay_ms: u64,
    pub metrics_export_interval_ms: u64,
}

#[derive(Debug, Clone, PartialEq)]
pub struct RequestCaptureSettings {
    pub postgres_url: String,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
struct RuntimeFileSettings {
    pipeline: PipelineSettings,
    input_validation: InputValidationSettings,
    retrieval: RuntimeRetrievalSettings,
    generation: RuntimeGenerationSettings,
    reranking: RuntimeRerankingSettings,
    observability: RuntimeObservabilitySettings,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
struct RuntimeRetrievalSettings {
    kind: RetrievalKind,
    retriever_version: String,
    top_k: usize,
    score_threshold: f32,
    embedding_retry: RetrySettings,
    qdrant_retry: RetrySettings,
}

#[derive(Debug, Clone, Copy, Deserialize, PartialEq)]
enum TransportKind {
    #[serde(rename = "ollama")]
    Ollama,
    #[serde(rename = "openai")]
    OpenAi,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
struct RuntimeGenerationSettings {
    transport_kind: TransportKind,
    tokenizer_source: String,
    temperature: f32,
    max_context_chunks: usize,
    max_prompt_tokens: usize,
    retry: RetrySettings,
    #[serde(default)]
    ollama: Option<RuntimeOllamaTransportSettings>,
    #[serde(default)]
    openai: Option<RuntimeOpenAiTransportSettings>,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
struct RuntimeOllamaTransportSettings {
    model_name: String,
    timeout_sec: u64,
    #[serde(default)]
    input_cost_per_million_tokens: f64,
    #[serde(default)]
    output_cost_per_million_tokens: f64,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
struct RuntimeOpenAiTransportSettings {
    model_name: String,
    timeout_sec: u64,
    #[serde(default)]
    input_cost_per_million_tokens: f64,
    #[serde(default)]
    output_cost_per_million_tokens: f64,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
struct RuntimeRerankingSettings {
    kind: RerankerKind,
    weights: HeuristicWeights,
    #[serde(default)]
    cross_encoder: Option<RuntimeCrossEncoderSettings>,
}

#[derive(Debug, Clone, Copy, Deserialize, PartialEq)]
enum CrossEncoderTransportKind {
    #[serde(rename = "mixedbread-ai")]
    MixedbreadAi,
    #[serde(rename = "voyageai")]
    VoyageAi,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
struct RuntimeCrossEncoderSettings {
    transport_kind: CrossEncoderTransportKind,
    #[serde(rename = "mixedbread-ai", default)]
    mixedbread_ai: Option<RuntimeMixedbreadAiCrossEncoderSettings>,
    #[serde(default)]
    voyageai: Option<RuntimeVoyageAiCrossEncoderSettings>,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
struct RuntimeMixedbreadAiCrossEncoderSettings {
    model_name: String,
    batch_size: usize,
    timeout_sec: u64,
    #[serde(default)]
    cost_per_million_tokens: f64,
    tokenizer_source: String,
    max_attempts: usize,
    backoff: RetryBackoff,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
struct RuntimeVoyageAiCrossEncoderSettings {
    model_name: String,
    batch_size: usize,
    timeout_sec: u64,
    #[serde(default)]
    cost_per_million_tokens: f64,
    max_attempts: usize,
    backoff: RetryBackoff,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
struct RuntimeObservabilitySettings {
    tracing_enabled: bool,
    metrics_enabled: bool,
    trace_batch_scheduled_delay_ms: u64,
    metrics_export_interval_ms: u64,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
struct DenseIngestSettings {
    pipeline: IngestPipelineSettings,
    embedding: IngestEmbeddingSettings,
    qdrant: DenseIngestQdrantSettings,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
struct IngestPipelineSettings {
    corpus_version: String,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
struct IngestEmbeddingSettings {
    model: IngestEmbeddingModelSettings,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
struct IngestEmbeddingModelSettings {
    name: String,
    dimension: usize,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
struct DenseIngestQdrantSettings {
    collection: DenseIngestQdrantCollectionSettings,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
struct DenseIngestQdrantCollectionSettings {
    name: String,
    vector_name: String,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
struct HybridIngestSettings {
    pipeline: IngestPipelineSettings,
    embedding: IngestEmbeddingSettings,
    sparse: HybridSparseSettings,
    qdrant: HybridIngestQdrantSettings,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
struct HybridSparseSettings {
    strategy: HybridSparseStrategySelector,
    tokenizer: HybridSparseTokenizerSettings,
    preprocessing: HybridSparsePreprocessingSettings,
    #[serde(default)]
    bag_of_words: Option<HybridBagOfWordsSettings>,
    #[serde(default)]
    bm25_like: Option<HybridBm25LikeSettings>,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
struct HybridSparseStrategySelector {
    kind: HybridSparseStrategyKind,
    version: String,
}

#[derive(Debug, Clone, Copy, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
enum HybridSparseStrategyKind {
    BagOfWords,
    Bm25Like,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
struct HybridSparseTokenizerSettings {
    library: String,
    source: String,
    #[serde(default)]
    revision: Option<String>,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
struct HybridSparsePreprocessingSettings {
    kind: String,
    lowercase: bool,
    min_token_length: usize,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
struct HybridBagOfWordsSettings {
    query: String,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
struct HybridBm25LikeSettings {
    query: String,
    k1: f32,
    b: f32,
    idf_smoothing: String,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
struct HybridIngestQdrantSettings {
    collection: HybridIngestQdrantCollectionSettings,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
struct HybridIngestQdrantCollectionSettings {
    name: String,
    dense_vector_name: String,
    sparse_vector_name: String,
}

pub async fn load_settings(
    rag_runtime_config_path: impl AsRef<Path>,
    ingest_config_path: impl AsRef<Path>,
) -> Result<Settings, RagRuntimeError> {
    let rag_runtime_config_path = rag_runtime_config_path.as_ref();
    let ingest_config_path = ingest_config_path.as_ref();

    load_root_env_once()?;
    validate_toml_against_schema(
        rag_runtime_config_path,
        &default_rag_runtime_schema_path(),
        "rag_runtime config",
    )
    .await?;
    let runtime_file_settings: RuntimeFileSettings = Config::builder()
        .add_source(File::from(rag_runtime_config_path))
        .build()
        .map_err(|error| {
            RagRuntimeError::startup(format!("failed to read rag_runtime.toml: {error}"))
        })?
        .try_deserialize()
        .map_err(|error| {
            RagRuntimeError::startup(format!(
                "failed to deserialize rag_runtime.toml into typed settings: {error}"
            ))
        })?;

    validate_toml_against_schema(
        ingest_config_path,
        &ingest_config_schema_path_for_kind(runtime_file_settings.retrieval.kind),
        "ingest config",
    )
    .await?;

    let qdrant_url = non_empty_env("QDRANT_URL")?;
    let tracing_endpoint = non_empty_env("TRACING_ENDPOINT")?;
    let metrics_endpoint = non_empty_env("METRICS_ENDPOINT")?;
    let postgres_url = non_empty_env("POSTGRES_URL")?;
    let reranking = build_reranking_settings(
        runtime_file_settings.reranking,
        runtime_file_settings.retrieval.top_k,
        runtime_file_settings.generation.max_context_chunks,
    )?;
    let ingest = build_retrieval_ingest(runtime_file_settings.retrieval.kind, ingest_config_path)?;
    let generation = build_generation_settings(runtime_file_settings.generation)?;
    let ollama_url = non_empty_env("OLLAMA_URL")?;

    Ok(Settings {
        pipeline: runtime_file_settings.pipeline,
        input_validation: runtime_file_settings.input_validation,
        retrieval: RetrievalSettings {
            kind: runtime_file_settings.retrieval.kind,
            ollama_url,
            qdrant_url,
            retriever_version: runtime_file_settings.retrieval.retriever_version,
            top_k: runtime_file_settings.retrieval.top_k,
            score_threshold: runtime_file_settings.retrieval.score_threshold,
            embedding_retry: runtime_file_settings.retrieval.embedding_retry,
            qdrant_retry: runtime_file_settings.retrieval.qdrant_retry,
            ingest,
        },
        generation,
        reranking,
        observability: ObservabilitySettings {
            tracing_enabled: runtime_file_settings.observability.tracing_enabled,
            metrics_enabled: runtime_file_settings.observability.metrics_enabled,
            tracing_endpoint,
            metrics_endpoint,
            trace_batch_scheduled_delay_ms: runtime_file_settings
                .observability
                .trace_batch_scheduled_delay_ms,
            metrics_export_interval_ms: runtime_file_settings
                .observability
                .metrics_export_interval_ms,
        },
        request_capture: RequestCaptureSettings { postgres_url },
    })
}

fn build_reranking_settings(
    runtime: RuntimeRerankingSettings,
    candidate_k: usize,
    final_k: usize,
) -> Result<RerankingSettings, RagRuntimeError> {
    let reranker = match runtime.kind {
        RerankerKind::PassThrough => RerankerSettings::PassThrough,
        RerankerKind::Heuristic => RerankerSettings::Heuristic(HeuristicRerankerSettings {
            weights: runtime.weights,
        }),
        RerankerKind::CrossEncoder => {
            let cross_encoder = runtime.cross_encoder.ok_or_else(|| {
                RagRuntimeError::startup(
                    "reranking.kind=cross_encoder requires the [reranking.cross_encoder] subtree",
                )
            })?;
            let transport = match cross_encoder.transport_kind {
                CrossEncoderTransportKind::MixedbreadAi => {
                    let mixedbread = cross_encoder.mixedbread_ai.ok_or_else(|| {
                        RagRuntimeError::startup(
                            "reranking.cross_encoder.transport_kind=mixedbread-ai requires the [reranking.cross_encoder.mixedbread-ai] subtree",
                        )
                    })?;
                    if mixedbread.model_name.trim().is_empty() {
                        return Err(RagRuntimeError::startup(
                            "reranking.cross_encoder.mixedbread-ai.model_name must be non-empty",
                        ));
                    }
                    if mixedbread.tokenizer_source.trim().is_empty() {
                        return Err(RagRuntimeError::startup(
                            "reranking.cross_encoder.mixedbread-ai.tokenizer_source must be non-empty",
                        ));
                    }
                    CrossEncoderTransportSettings::MixedbreadAi(
                        MixedbreadAiCrossEncoderTransportSettings {
                            url: non_empty_env("RERANKER_ENDPOINT")?,
                            model_name: mixedbread.model_name,
                            batch_size: mixedbread.batch_size,
                            timeout_sec: mixedbread.timeout_sec,
                            cost_per_million_tokens: mixedbread.cost_per_million_tokens,
                            tokenizer_source: mixedbread.tokenizer_source,
                            max_attempts: mixedbread.max_attempts,
                            backoff: mixedbread.backoff,
                        },
                    )
                }
                CrossEncoderTransportKind::VoyageAi => {
                    let voyageai = cross_encoder.voyageai.ok_or_else(|| {
                        RagRuntimeError::startup(
                            "reranking.cross_encoder.transport_kind=voyageai requires the [reranking.cross_encoder.voyageai] subtree",
                        )
                    })?;
                    if voyageai.model_name.trim().is_empty() {
                        return Err(RagRuntimeError::startup(
                            "reranking.cross_encoder.voyageai.model_name must be non-empty",
                        ));
                    }
                    CrossEncoderTransportSettings::VoyageAi(VoyageAiCrossEncoderTransportSettings {
                        url: non_empty_env("VOYAGEAI_RERANK_URL")?,
                        api_key: non_empty_env("VOYAGEAI_API_KEY")?,
                        model_name: voyageai.model_name,
                        batch_size: voyageai.batch_size,
                        timeout_sec: voyageai.timeout_sec,
                        cost_per_million_tokens: voyageai.cost_per_million_tokens,
                        max_attempts: voyageai.max_attempts,
                        backoff: voyageai.backoff,
                    })
                }
            };
            RerankerSettings::CrossEncoder(CrossEncoderRerankerSettings { transport })
        }
    };

    Ok(RerankingSettings {
        reranker,
        candidate_k,
        final_k,
    })
}

fn build_generation_settings(
    runtime: RuntimeGenerationSettings,
) -> Result<GenerationSettings, RagRuntimeError> {
    let transport = match runtime.transport_kind {
        TransportKind::Ollama => {
            let ollama = runtime.ollama.ok_or_else(|| {
                RagRuntimeError::startup(
                    "generation.transport_kind=ollama requires the [generation.ollama] subtree",
                )
            })?;
            if ollama.model_name.trim().is_empty() {
                return Err(RagRuntimeError::startup(
                    "generation.ollama.model_name must be non-empty",
                ));
            }
            TransportSettings::Ollama(OllamaTransportSettings {
                url: non_empty_env("OLLAMA_URL")?,
                model_name: ollama.model_name,
                timeout_sec: ollama.timeout_sec,
                input_cost_per_million_tokens: ollama.input_cost_per_million_tokens,
                output_cost_per_million_tokens: ollama.output_cost_per_million_tokens,
            })
        }
        TransportKind::OpenAi => {
            let openai = runtime.openai.ok_or_else(|| {
                RagRuntimeError::startup(
                    "generation.transport_kind=openai requires the [generation.openai] subtree",
                )
            })?;
            if openai.model_name.trim().is_empty() {
                return Err(RagRuntimeError::startup(
                    "generation.openai.model_name must be non-empty",
                ));
            }
            TransportSettings::OpenAi(OpenAiTransportSettings {
                url: non_empty_env("OPENAI_COMPATIBLE_URL")?,
                api_key: non_empty_env("TOGETHER_API_KEY")?,
                model_name: openai.model_name,
                timeout_sec: openai.timeout_sec,
                input_cost_per_million_tokens: openai.input_cost_per_million_tokens,
                output_cost_per_million_tokens: openai.output_cost_per_million_tokens,
            })
        }
    };

    Ok(GenerationSettings {
        transport,
        tokenizer_source: runtime.tokenizer_source,
        temperature: runtime.temperature,
        max_context_chunks: runtime.max_context_chunks,
        max_prompt_tokens: runtime.max_prompt_tokens,
        retry: runtime.retry,
    })
}

fn non_empty_env(key: &str) -> Result<String, RagRuntimeError> {
    let value = env::var(key).map_err(|_| {
        RagRuntimeError::startup(format!("missing required environment variable {key}"))
    })?;
    if value.trim().is_empty() {
        return Err(RagRuntimeError::startup(format!(
            "environment variable {key} must be non-empty"
        )));
    }
    Ok(value)
}

fn load_root_env_once() -> Result<(), RagRuntimeError> {
    if env::var("RAG_RUNTIME_SKIP_DOTENV")
        .map(|value| value == "1")
        .unwrap_or(false)
    {
        return Ok(());
    }
    match dotenvy::from_filename(ROOT_ENV_FILE) {
        Ok(_) => Ok(()),
        Err(dotenvy::Error::Io(error)) if error.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(error) => Err(RagRuntimeError::startup(format!(
            "failed to load repository env file .env: {error}"
        ))),
    }
}

async fn validate_toml_against_schema(
    config_path: &Path,
    schema_path: &Path,
    label: &str,
) -> Result<(), RagRuntimeError> {
    let config_text = tokio::fs::read_to_string(config_path)
        .await
        .map_err(|error| {
            RagRuntimeError::startup(format!(
                "failed to read {label} {}: {error}",
                config_path.display()
            ))
        })?;
    let config_toml: toml::Value = toml::from_str(&config_text).map_err(|error| {
        RagRuntimeError::startup(format!(
            "failed to parse {label} {}: {error}",
            config_path.display()
        ))
    })?;
    let config_json = serde_json::to_value(config_toml).map_err(|error| {
        RagRuntimeError::startup(format!(
            "failed to convert {label} {} to json value: {error}",
            config_path.display()
        ))
    })?;
    let schema_json = read_json_file(schema_path).await?;
    let validator = draft202012::new(&schema_json).map_err(|error| {
        RagRuntimeError::startup(format!(
            "failed to compile json schema {}: {error}",
            schema_path.display()
        ))
    })?;
    if let Err(error) = validator.validate(&config_json) {
        return Err(RagRuntimeError::startup(format!(
            "{label} {} failed schema validation: {error}",
            config_path.display()
        )));
    }
    Ok(())
}

async fn read_json_file(path: &Path) -> Result<Value, RagRuntimeError> {
    let text = tokio::fs::read_to_string(path).await.map_err(|error| {
        RagRuntimeError::startup(format!("failed to read json {}: {error}", path.display()))
    })?;
    serde_json::from_str(&text).map_err(|error| {
        RagRuntimeError::startup(format!("failed to parse json {}: {error}", path.display()))
    })
}

pub fn default_rag_runtime_config_path() -> PathBuf {
    repo_root_from_cwd().join("Execution/rag_runtime/rag_runtime.toml")
}

pub fn default_rag_runtime_schema_path() -> PathBuf {
    repo_root_from_cwd().join("Execution/rag_runtime/schemas/rag_runtime_config.schema.json")
}

pub fn default_ingest_config_path() -> PathBuf {
    repo_root_from_cwd().join("Execution/ingest/dense/ingest.toml")
}

pub fn default_ingest_config_schema_path() -> PathBuf {
    repo_root_from_cwd().join("Execution/ingest/schemas/dense_ingest_config.schema.json")
}

pub fn ingest_config_schema_path_for_kind(kind: RetrievalKind) -> PathBuf {
    match kind {
        RetrievalKind::Dense => {
            repo_root_from_cwd().join("Execution/ingest/schemas/dense_ingest_config.schema.json")
        }
        RetrievalKind::Hybrid => {
            repo_root_from_cwd().join("Execution/ingest/schemas/hybrid_ingest_config.schema.json")
        }
    }
}

pub fn default_request_capture_schema_path() -> PathBuf {
    repo_root_from_cwd().join("Execution/rag_runtime/schemas/request_capture.schema.json")
}

fn repo_root_from_cwd() -> PathBuf {
    let mut current = env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    loop {
        if current.join("Specification").is_dir() && current.join("Execution").is_dir() {
            return current;
        }
        if !current.pop() {
            return env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
        }
    }
}

fn build_retrieval_ingest(
    kind: RetrievalKind,
    ingest_config_path: &Path,
) -> Result<RetrievalIngest, RagRuntimeError> {
    match kind {
        RetrievalKind::Dense => {
            let ingest_settings: DenseIngestSettings = Config::builder()
                .add_source(File::from(ingest_config_path))
                .build()
                .map_err(|error| {
                    RagRuntimeError::startup(format!("failed to read ingest config: {error}"))
                })?
                .try_deserialize()
                .map_err(|error| {
                    RagRuntimeError::startup(format!(
                        "failed to deserialize ingest config into DenseRetrievalIngest: {error}"
                    ))
                })?;
            Ok(RetrievalIngest::Dense(DenseRetrievalIngest {
                embedding_model_name: ingest_settings.embedding.model.name,
                embedding_dimension: ingest_settings.embedding.model.dimension,
                qdrant_collection_name: ingest_settings.qdrant.collection.name,
                qdrant_vector_name: ingest_settings.qdrant.collection.vector_name,
                corpus_version: ingest_settings.pipeline.corpus_version,
            }))
        }
        RetrievalKind::Hybrid => {
            let ingest_settings: HybridIngestSettings = Config::builder()
                .add_source(File::from(ingest_config_path))
                .build()
                .map_err(|error| {
                    RagRuntimeError::startup(format!("failed to read ingest config: {error}"))
                })?
                .try_deserialize()
                .map_err(|error| {
                    RagRuntimeError::startup(format!(
                        "failed to deserialize ingest config into HybridRetrievalIngest: {error}"
                    ))
                })?;
            let strategy = build_retrieval_strategy(&ingest_settings)?;
            Ok(RetrievalIngest::Hybrid(HybridRetrievalIngest {
                embedding_model_name: ingest_settings.embedding.model.name,
                embedding_dimension: ingest_settings.embedding.model.dimension,
                qdrant_collection_name: ingest_settings.qdrant.collection.name,
                dense_vector_name: ingest_settings.qdrant.collection.dense_vector_name,
                sparse_vector_name: ingest_settings.qdrant.collection.sparse_vector_name,
                corpus_version: ingest_settings.pipeline.corpus_version,
                tokenizer_library: ingest_settings.sparse.tokenizer.library,
                tokenizer_source: ingest_settings.sparse.tokenizer.source,
                tokenizer_revision: ingest_settings.sparse.tokenizer.revision,
                preprocessing_kind: ingest_settings.sparse.preprocessing.kind,
                lowercase: ingest_settings.sparse.preprocessing.lowercase,
                min_token_length: ingest_settings.sparse.preprocessing.min_token_length,
                vocabulary_path: "Execution/ingest/hybrid/artifacts/vocabularies".to_string(),
                strategy,
            }))
        }
    }
}

fn build_retrieval_strategy(
    ingest_settings: &HybridIngestSettings,
) -> Result<RetrievalStrategy, RagRuntimeError> {
    match ingest_settings.sparse.strategy.kind {
        HybridSparseStrategyKind::BagOfWords => {
            let bag_of_words = ingest_settings.sparse.bag_of_words.as_ref().ok_or_else(|| {
                RagRuntimeError::startup(
                    "retrieval.kind=hybrid and sparse.strategy.kind=bag_of_words require sparse.bag_of_words",
                )
            })?;
            Ok(RetrievalStrategy::BagOfWords(BagOfWordsRetrievalStrategy {
                version: ingest_settings.sparse.strategy.version.clone(),
                query_weighting: bag_of_words.query.clone(),
            }))
        }
        HybridSparseStrategyKind::Bm25Like => {
            let bm25_like = ingest_settings.sparse.bm25_like.as_ref().ok_or_else(|| {
                RagRuntimeError::startup(
                    "retrieval.kind=hybrid and sparse.strategy.kind=bm25_like require sparse.bm25_like",
                )
            })?;
            Ok(RetrievalStrategy::Bm25Like(Bm25LikeRetrievalStrategy {
                version: ingest_settings.sparse.strategy.version.clone(),
                query_weighting: bm25_like.query.clone(),
                k1: bm25_like.k1,
                b: bm25_like.b,
                idf_smoothing: bm25_like.idf_smoothing.clone(),
                term_stats_path: "Execution/ingest/hybrid/artifacts/term_stats".to_string(),
            }))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    use tempfile::tempdir;

    use crate::test_support::env_lock;

    fn set_env_var(key: &str, value: &str) {
        unsafe { env::set_var(key, value) };
    }

    fn remove_env_var(key: &str) {
        unsafe { env::remove_var(key) };
    }

    fn write_file(path: &Path, text: &str) {
        fs::write(path, text).expect("write file");
    }

    fn clear_required_env() {
        remove_env_var("OLLAMA_URL");
        remove_env_var("QDRANT_URL");
        remove_env_var("RERANKER_ENDPOINT");
        remove_env_var("POSTGRES_URL");
        remove_env_var("TRACING_ENDPOINT");
        remove_env_var("METRICS_ENDPOINT");
        set_env_var("RAG_RUNTIME_SKIP_DOTENV", "1");
    }

    fn sample_runtime_config(max_context_chunks: usize) -> String {
        format!(
            r#"[pipeline]
config_version = "v1"

[input_validation]
max_query_tokens = 128
tokenizer_source = "Qwen/Qwen3-Embedding-0.6B"
reject_empty_query = true
trim_whitespace = true
collapse_internal_whitespace = true

[retrieval]
kind = "dense"
retriever_version = "v1"
top_k = 3
score_threshold = 0.2

[retrieval.embedding_retry]
max_attempts = 3
backoff = "exponential"

[retrieval.qdrant_retry]
max_attempts = 3
backoff = "exponential"

[generation]
transport_kind = "ollama"
tokenizer_source = "Qwen/Qwen2.5-1.5B-Instruct"
temperature = 0.0
max_context_chunks = {max_context_chunks}
max_prompt_tokens = 28672

[generation.retry]
max_attempts = 3
backoff = "exponential"

[generation.ollama]
model_name = "model"
timeout_sec = 90
input_cost_per_million_tokens = 0.0
output_cost_per_million_tokens = 0.0

[generation.openai]
model_name = "openai/gpt-oss-20b"
timeout_sec = 90
input_cost_per_million_tokens = 0.0
output_cost_per_million_tokens = 0.0

[reranking]
kind = "pass_through"

[reranking.weights]
retrieval_score = 1.0
query_term_coverage = 1.0
phrase_match_bonus = 1.0
title_section_match_bonus = 1.0

[reranking.cross_encoder]
transport_kind = "mixedbread-ai"

[reranking.cross_encoder.mixedbread-ai]
model_name = "mixedbread-ai/mxbai-rerank-base-v2"
batch_size = 12
timeout_sec = 120
cost_per_million_tokens = 0.0
tokenizer_source = "mixedbread-ai/mxbai-rerank-base-v2"
max_attempts = 3
backoff = "exponential"

[reranking.cross_encoder.voyageai]
model_name = "rerank-2.5"
batch_size = 12
timeout_sec = 120
cost_per_million_tokens = 0.0
max_attempts = 3
backoff = "exponential"

[observability]
tracing_enabled = true
metrics_enabled = true
trace_batch_scheduled_delay_ms = 2000
metrics_export_interval_ms = 1000
"#
        )
    }

    fn sample_ingest_config() -> &'static str {
        r#"[pipeline]
name = "dense_ingest"
chunk_schema_version = 1
ingest_config_version = "v1"
corpus_version = "v1"
chunking_strategy = "structural"

[embedding.model]
name = "qwen3-embedding:0.6b"
dimension = 1024

[embedding.input]
text_source = "chunk.text"

[embedding.transport]
timeout_sec = 60
max_batch_size = 1

[embedding.retry]
max_attempts = 3
backoff = "exponential"

[qdrant.collection]
name = "chunks_dense_qwen3"
distance = "Cosine"
vector_name = "default"
create_if_missing = true

[qdrant.point_id]
strategy = "uuid5(chunk.chunk_id)"
namespace_uuid = "05a17c2f-4ee5-5c40-ab34-99631356c9b3"
format = "canonical_uuid"

[qdrant.transport]
timeout_sec = 30
upsert_batch_size = 64

[qdrant.retry]
max_attempts = 3
backoff = "exponential"

[idempotency]
strategy = "field_tuple_hash"
fingerprint_fields = ["content_hash"]
on_fingerprint_change = "log_and_skip"
on_metadata_change = "update_changed_fields"

[logging]
failed_chunk_log_path = "out/ingest_failed_chunks.jsonl"
skipped_chunk_log_path = "out/ingest_skipped_chunks.jsonl"
"#
    }

    fn sample_hybrid_ingest_config(strategy_kind: &str) -> String {
        let strategy_block = match strategy_kind {
            "bag_of_words" => {
                r#"[sparse.bag_of_words]
document = "term_frequency"
query = "binary_presence"
"#
            }
            "bm25_like" => {
                r#"[sparse.bm25_like]
document = "bm25_document_weight"
query = "bm25_query_weight"
k1 = 1.2
b = 0.75
idf_smoothing = "standard"
"#
            }
            _ => panic!("unsupported strategy_kind"),
        };

        format!(
            r#"[pipeline]
name = "hybrid_ingest"
chunk_schema_version = 1
ingest_config_version = "v1"
corpus_version = "v1"
chunking_strategy = "structural"

[embedding.model]
name = "qwen3-embedding:0.6b"
dimension = 1024

[embedding.input]
text_source = "chunk.text"

[embedding.transport]
timeout_sec = 60
max_batch_size = 1

[embedding.retry]
max_attempts = 3
backoff = "exponential"

[sparse.strategy]
kind = "{strategy_kind}"
version = "v1"

[sparse.input]
text_source = "chunk.text"

[sparse.tokenizer]
library = "tokenizers"
source = "Qwen/Qwen3-Embedding-0.6B"

[sparse.preprocessing]
kind = "basic_word_v1"
lowercase = true
min_token_length = 2

{strategy_block}
[artifacts]
manifest_path = "Execution/ingest/hybrid/artifacts/manifests/run_manifest.json"

[qdrant.collection]
name = "chunks_hybrid_structural_qwen3"
distance = "Cosine"
dense_vector_name = "dense"
sparse_vector_name = "sparse"
create_if_missing = true

[qdrant.point_id]
strategy = "uuid5(chunk.chunk_id)"
namespace_uuid = "05a17c2f-4ee5-5c40-ab34-99631356c9b3"
format = "canonical_uuid"

[qdrant.transport]
timeout_sec = 30
upsert_batch_size = 64

[qdrant.retry]
max_attempts = 3
backoff = "exponential"

[idempotency]
strategy = "field_tuple_hash"
fingerprint_fields = ["content_hash"]
on_fingerprint_change = "log_and_skip"
on_metadata_change = "update_changed_fields"

[logging]
failed_chunk_log_path = "Execution/ingest/hybrid/artifacts/logs/failed.jsonl"
skipped_chunk_log_path = "Execution/ingest/hybrid/artifacts/logs/skipped.jsonl"
"#
        )
    }

    #[tokio::test]
    async fn valid_configs_and_env_produce_merged_settings() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        clear_required_env();
        let dir = tempdir().unwrap();
        let runtime = dir.path().join("rag_runtime.toml");
        let ingest = dir.path().join("ingest.toml");
        let runtime_schema = dir.path().join("rag_runtime_config.schema.json");
        let ingest_schema = dir.path().join("dense_ingest_config.schema.json");

        write_file(&runtime, &sample_runtime_config(5));
        write_file(
            &runtime_schema,
            &fs::read_to_string(default_rag_runtime_schema_path()).unwrap(),
        );
        write_file(&ingest, sample_ingest_config());
        write_file(
            &ingest_schema,
            &fs::read_to_string(default_ingest_config_schema_path()).unwrap(),
        );

        set_env_var("OLLAMA_URL", "http://ollama.test");
        set_env_var("QDRANT_URL", "http://qdrant.test");
        set_env_var("RERANKER_ENDPOINT", "http://reranker.test");
        set_env_var(
            "POSTGRES_URL",
            "postgres://postgres:postgres@localhost:5432/rag_eval",
        );
        set_env_var("TRACING_ENDPOINT", "http://trace.test");
        set_env_var("METRICS_ENDPOINT", "http://metrics.test");

        let settings = load_settings(&runtime, &ingest).await.unwrap();
        assert_eq!(settings.retrieval.kind, RetrievalKind::Dense);
        match &settings.retrieval.ingest {
            RetrievalIngest::Dense(ingest) => {
                assert_eq!(ingest.embedding_model_name, "qwen3-embedding:0.6b");
                assert_eq!(ingest.embedding_dimension, 1024);
                assert_eq!(ingest.qdrant_collection_name, "chunks_dense_qwen3");
            }
            RetrievalIngest::Hybrid(_) => panic!("expected dense retrieval ingest"),
        }
        assert_eq!(
            settings.generation.tokenizer_source,
            "Qwen/Qwen2.5-1.5B-Instruct"
        );
        assert_eq!(settings.generation.max_prompt_tokens, 28672);
        assert_eq!(settings.generation.retry.max_attempts, 3);
        assert_eq!(settings.generation.retry.backoff, RetryBackoff::Exponential);
        match &settings.generation.transport {
            TransportSettings::Ollama(transport) => {
                assert_eq!(transport.url, "http://ollama.test");
                assert_eq!(transport.model_name, "model");
                assert_eq!(transport.timeout_sec, 90);
            }
            TransportSettings::OpenAi(_) => panic!("expected ollama transport"),
        }
        assert!(matches!(
            settings.reranking.reranker,
            RerankerSettings::PassThrough
        ));
        assert_eq!(settings.reranking.candidate_k, 3);
        assert_eq!(settings.reranking.final_k, 5);
        assert_eq!(settings.observability.tracing_endpoint, "http://trace.test");
        clear_required_env();
        remove_env_var("RAG_RUNTIME_SKIP_DOTENV");
    }

    #[tokio::test]
    async fn hybrid_ingest_config_produces_typed_hybrid_retrieval_settings() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        clear_required_env();
        let dir = tempdir().unwrap();
        let runtime = dir.path().join("rag_runtime.toml");
        let ingest = dir.path().join("ingest.toml");

        write_file(
            &runtime,
            &sample_runtime_config(5).replace("kind = \"dense\"", "kind = \"hybrid\""),
        );
        write_file(&ingest, &sample_hybrid_ingest_config("bm25_like"));

        set_env_var("OLLAMA_URL", "http://ollama.test");
        set_env_var("QDRANT_URL", "http://qdrant.test");
        set_env_var("RERANKER_ENDPOINT", "http://reranker.test");
        set_env_var(
            "POSTGRES_URL",
            "postgres://postgres:postgres@localhost:5432/rag_eval",
        );
        set_env_var("TRACING_ENDPOINT", "http://trace.test");
        set_env_var("METRICS_ENDPOINT", "http://metrics.test");

        let settings = load_settings(&runtime, &ingest).await.unwrap();
        assert_eq!(settings.retrieval.kind, RetrievalKind::Hybrid);
        match &settings.retrieval.ingest {
            RetrievalIngest::Hybrid(ingest) => {
                assert_eq!(ingest.embedding_model_name, "qwen3-embedding:0.6b");
                assert_eq!(ingest.embedding_dimension, 1024);
                assert_eq!(
                    ingest.qdrant_collection_name,
                    "chunks_hybrid_structural_qwen3"
                );
                assert_eq!(ingest.dense_vector_name, "dense");
                assert_eq!(ingest.sparse_vector_name, "sparse");
                assert_eq!(
                    ingest.vocabulary_path,
                    "Execution/ingest/hybrid/artifacts/vocabularies"
                );
                match &ingest.strategy {
                    RetrievalStrategy::Bm25Like(strategy) => {
                        assert_eq!(strategy.version, "v1");
                        assert_eq!(strategy.query_weighting, "bm25_query_weight");
                        assert_eq!(
                            strategy.term_stats_path,
                            "Execution/ingest/hybrid/artifacts/term_stats"
                        );
                    }
                    RetrievalStrategy::BagOfWords(_) => panic!("expected bm25-like strategy"),
                }
            }
            RetrievalIngest::Dense(_) => panic!("expected hybrid retrieval ingest"),
        }

        clear_required_env();
        remove_env_var("RAG_RUNTIME_SKIP_DOTENV");
    }

    #[tokio::test]
    async fn heuristic_reranking_settings_are_loaded_and_derived_from_existing_limits() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        clear_required_env();
        let dir = tempdir().unwrap();
        let runtime = dir.path().join("rag_runtime.toml");
        let ingest = dir.path().join("ingest.toml");
        let runtime_schema = dir.path().join("rag_runtime_config.schema.json");
        let ingest_schema = dir.path().join("dense_ingest_config.schema.json");

        let runtime_config = sample_runtime_config(7)
            .replace("kind = \"pass_through\"", "kind = \"heuristic\"")
            .replace("top_k = 3", "top_k = 4")
            .replace("max_context_chunks = 7", "max_context_chunks = 12")
            .replace("retrieval_score = 1.0", "retrieval_score = 0.7")
            .replace("query_term_coverage = 1.0", "query_term_coverage = 0.15")
            .replace("phrase_match_bonus = 1.0", "phrase_match_bonus = 0.1")
            .replace(
                "title_section_match_bonus = 1.0",
                "title_section_match_bonus = 0.05",
            );

        write_file(&runtime, &runtime_config);
        write_file(
            &runtime_schema,
            &fs::read_to_string(default_rag_runtime_schema_path()).unwrap(),
        );
        write_file(&ingest, sample_ingest_config());
        write_file(
            &ingest_schema,
            &fs::read_to_string(default_ingest_config_schema_path()).unwrap(),
        );

        set_env_var("OLLAMA_URL", "http://ollama.test");
        set_env_var("QDRANT_URL", "http://qdrant.test");
        set_env_var("RERANKER_ENDPOINT", "http://reranker.test");
        set_env_var(
            "POSTGRES_URL",
            "postgres://postgres:postgres@localhost:5432/rag_eval",
        );
        set_env_var("TRACING_ENDPOINT", "http://trace.test");
        set_env_var("METRICS_ENDPOINT", "http://metrics.test");

        let settings = load_settings(&runtime, &ingest).await.unwrap();
        let heuristic = match &settings.reranking.reranker {
            RerankerSettings::Heuristic(heuristic) => heuristic,
            other => panic!("expected heuristic reranker, got {other:?}"),
        };
        assert_eq!(settings.reranking.candidate_k, 4);
        assert_eq!(settings.reranking.final_k, 12);
        assert_eq!(heuristic.weights.retrieval_score, 0.7);
        assert_eq!(heuristic.weights.query_term_coverage, 0.15);
        assert_eq!(heuristic.weights.phrase_match_bonus, 0.1);
        assert_eq!(heuristic.weights.title_section_match_bonus, 0.05);

        clear_required_env();
        remove_env_var("RAG_RUNTIME_SKIP_DOTENV");
    }

    #[tokio::test]
    async fn cross_encoder_settings_are_loaded_from_toml_and_env() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        clear_required_env();
        let dir = tempdir().unwrap();
        let runtime = dir.path().join("rag_runtime.toml");
        let ingest = dir.path().join("ingest.toml");
        let runtime_schema = dir.path().join("rag_runtime_config.schema.json");
        let ingest_schema = dir.path().join("dense_ingest_config.schema.json");

        let runtime_config =
            sample_runtime_config(4).replace("kind = \"pass_through\"", "kind = \"cross_encoder\"");

        write_file(&runtime, &runtime_config);
        write_file(
            &runtime_schema,
            &fs::read_to_string(default_rag_runtime_schema_path()).unwrap(),
        );
        write_file(&ingest, sample_ingest_config());
        write_file(
            &ingest_schema,
            &fs::read_to_string(default_ingest_config_schema_path()).unwrap(),
        );

        set_env_var("OLLAMA_URL", "http://ollama.test");
        set_env_var("QDRANT_URL", "http://qdrant.test");
        set_env_var("RERANKER_ENDPOINT", "http://reranker.test");
        set_env_var(
            "POSTGRES_URL",
            "postgres://postgres:postgres@localhost:5432/rag_eval",
        );
        set_env_var("TRACING_ENDPOINT", "http://trace.test");
        set_env_var("METRICS_ENDPOINT", "http://metrics.test");

        let settings = load_settings(&runtime, &ingest).await.unwrap();
        let cross_encoder = match &settings.reranking.reranker {
            RerankerSettings::CrossEncoder(cross_encoder) => cross_encoder,
            other => panic!("expected cross encoder reranker, got {other:?}"),
        };
        match &cross_encoder.transport {
            CrossEncoderTransportSettings::MixedbreadAi(transport) => {
                assert_eq!(transport.model_name, "mixedbread-ai/mxbai-rerank-base-v2");
                assert_eq!(transport.url, "http://reranker.test");
                assert_eq!(transport.batch_size, 12);
                assert_eq!(transport.timeout_sec, 120);
                assert_eq!(transport.max_attempts, 3);
                assert_eq!(
                    transport.tokenizer_source,
                    "mixedbread-ai/mxbai-rerank-base-v2"
                );
            }
            other => panic!("expected mixedbread transport, got {other:?}"),
        }

        clear_required_env();
        remove_env_var("RAG_RUNTIME_SKIP_DOTENV");
    }

    #[tokio::test]
    async fn missing_required_env_causes_startup_failure() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        clear_required_env();
        let dir = tempdir().unwrap();
        let runtime = dir.path().join("rag_runtime.toml");
        let ingest = dir.path().join("ingest.toml");
        write_file(&runtime, &sample_runtime_config(5));
        write_file(&ingest, sample_ingest_config());

        let error = load_settings(&runtime, &ingest).await.unwrap_err();
        assert!(matches!(error, RagRuntimeError::Startup { .. }));
        remove_env_var("RAG_RUNTIME_SKIP_DOTENV");
    }

    #[tokio::test]
    async fn schema_invalid_runtime_config_causes_startup_failure() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        clear_required_env();
        let dir = tempdir().unwrap();
        let runtime = dir.path().join("rag_runtime.toml");
        let ingest = dir.path().join("ingest.toml");
        write_file(&runtime, "[pipeline]\nconfig_version = \"v1\"\n");
        write_file(&ingest, sample_ingest_config());

        set_env_var("OLLAMA_URL", "http://ollama.test");
        set_env_var("QDRANT_URL", "http://qdrant.test");
        set_env_var("RERANKER_ENDPOINT", "http://reranker.test");
        set_env_var("TRACING_ENDPOINT", "http://trace.test");
        set_env_var("METRICS_ENDPOINT", "http://metrics.test");

        let error = load_settings(&runtime, &ingest).await.unwrap_err();
        assert!(matches!(error, RagRuntimeError::Startup { .. }));
        clear_required_env();
        remove_env_var("RAG_RUNTIME_SKIP_DOTENV");
    }

    #[tokio::test]
    async fn openai_generation_transport_loads_only_active_env_vars() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        clear_required_env();
        let dir = tempdir().unwrap();
        let runtime = dir.path().join("rag_runtime.toml");
        let ingest = dir.path().join("ingest.toml");

        let runtime_config = sample_runtime_config(5)
            .replace("transport_kind = \"ollama\"", "transport_kind = \"openai\"");
        write_file(&runtime, &runtime_config);
        write_file(&ingest, sample_ingest_config());

        set_env_var("OLLAMA_URL", "http://ollama.test");
        set_env_var("OPENAI_COMPATIBLE_URL", "https://api.together.xyz");
        set_env_var("TOGETHER_API_KEY", "test-key");
        set_env_var("QDRANT_URL", "http://qdrant.test");
        set_env_var("RERANKER_ENDPOINT", "http://reranker.test");
        set_env_var(
            "POSTGRES_URL",
            "postgres://postgres:postgres@localhost:5432/rag_eval",
        );
        set_env_var("TRACING_ENDPOINT", "http://trace.test");
        set_env_var("METRICS_ENDPOINT", "http://metrics.test");

        let settings = load_settings(&runtime, &ingest).await.unwrap();
        match &settings.generation.transport {
            TransportSettings::OpenAi(transport) => {
                assert_eq!(transport.url, "https://api.together.xyz");
                assert_eq!(transport.api_key, "test-key");
                assert_eq!(transport.model_name, "openai/gpt-oss-20b");
                assert_eq!(transport.timeout_sec, 90);
            }
            TransportSettings::Ollama(_) => panic!("expected openai transport"),
        }

        clear_required_env();
        remove_env_var("RAG_RUNTIME_SKIP_DOTENV");
    }

    #[tokio::test]
    async fn top_k_above_max_context_chunks_is_allowed_for_reranking() {
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        clear_required_env();
        let dir = tempdir().unwrap();
        let runtime = dir.path().join("rag_runtime.toml");
        let ingest = dir.path().join("ingest.toml");
        write_file(&runtime, &sample_runtime_config(2));
        write_file(&ingest, sample_ingest_config());

        set_env_var("OLLAMA_URL", "http://ollama.test");
        set_env_var("QDRANT_URL", "http://qdrant.test");
        set_env_var("RERANKER_ENDPOINT", "http://reranker.test");
        set_env_var("TRACING_ENDPOINT", "http://trace.test");
        set_env_var("METRICS_ENDPOINT", "http://metrics.test");
        set_env_var(
            "POSTGRES_URL",
            "postgres://postgres:postgres@postgres.test:5432/rag_eval",
        );

        let settings = load_settings(&runtime, &ingest).await.unwrap();
        assert_eq!(settings.retrieval.top_k, 3);
        assert_eq!(settings.generation.max_context_chunks, 2);
        assert_eq!(settings.reranking.candidate_k, 3);
        assert_eq!(settings.reranking.final_k, 2);
        clear_required_env();
        remove_env_var("RAG_RUNTIME_SKIP_DOTENV");
    }

    #[test]
    fn default_config_path_helpers_return_contract_paths() {
        assert!(
            default_rag_runtime_config_path().ends_with("Execution/rag_runtime/rag_runtime.toml")
        );
        assert!(default_ingest_config_path().ends_with("Execution/ingest/dense/ingest.toml"));
        assert!(
            default_rag_runtime_schema_path()
                .ends_with("Execution/rag_runtime/schemas/rag_runtime_config.schema.json")
        );
    }

    #[tokio::test]
    async fn read_json_file_reports_invalid_json() {
        let dir = tempdir().unwrap();
        let file = dir.path().join("broken.json");
        write_file(&file, "{");
        let error = read_json_file(&file).await.unwrap_err();
        assert!(matches!(error, RagRuntimeError::Startup { .. }));
    }

    #[tokio::test]
    async fn validate_toml_against_schema_reports_parse_error() {
        let dir = tempdir().unwrap();
        let config = dir.path().join("config.toml");
        let schema = dir.path().join("schema.json");
        write_file(&config, "not = [valid");
        write_file(
            &schema,
            r#"{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"object"}"#,
        );
        let error = validate_toml_against_schema(&config, &schema, "test config")
            .await
            .unwrap_err();
        assert!(matches!(error, RagRuntimeError::Startup { .. }));
    }
}

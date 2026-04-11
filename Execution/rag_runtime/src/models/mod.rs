use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct UserRequest {
    pub query: String,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
pub struct ValidatedUserRequest {
    pub query: String,
    pub input_token_count: usize,
    pub trim_whitespace_applied: bool,
    pub collapse_internal_whitespace_applied: bool,
    pub normalized_query_length: usize,
    pub tokenizer_source: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct IngestMetadata {
    pub embedding_model: Option<String>,
    pub embedding_model_dimension: Option<usize>,
    pub ingest_config_version: Option<String>,
    pub ingested_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Chunk {
    pub schema_version: i64,
    pub doc_id: String,
    pub chunk_id: String,
    pub url: String,
    pub document_title: String,
    pub section_title: Option<String>,
    #[serde(default)]
    pub section_path: Vec<String>,
    pub chunk_index: i64,
    pub page_start: i64,
    pub page_end: i64,
    #[serde(default)]
    pub tags: Vec<String>,
    pub content_hash: String,
    pub chunking_version: String,
    pub chunk_created_at: String,
    pub text: String,
    pub ingest: Option<IngestMetadata>,
}

impl Chunk {
    pub fn validate(&self) -> Result<(), String> {
        if self.schema_version != 1 {
            return Err(format!(
                "chunk schema_version must be 1, got {}",
                self.schema_version
            ));
        }
        if self.doc_id.trim().is_empty() {
            return Err("chunk doc_id must be non-empty".to_string());
        }
        if self.chunk_id.trim().is_empty() {
            return Err("chunk chunk_id must be non-empty".to_string());
        }
        if self.url.trim().is_empty() {
            return Err("chunk url must be non-empty".to_string());
        }
        if self.document_title.trim().is_empty() {
            return Err("chunk document_title must be non-empty".to_string());
        }
        if self.chunk_index < 0 {
            return Err(format!(
                "chunk chunk_index must be >= 0, got {}",
                self.chunk_index
            ));
        }
        if self.page_start < 1 {
            return Err(format!(
                "chunk page_start must be >= 1, got {}",
                self.page_start
            ));
        }
        if self.page_end < self.page_start {
            return Err(format!(
                "chunk page_end must be >= page_start, got {} < {}",
                self.page_end, self.page_start
            ));
        }
        if self.content_hash.trim().is_empty() {
            return Err("chunk content_hash must be non-empty".to_string());
        }
        if self.chunking_version.trim().is_empty() {
            return Err("chunk chunking_version must be non-empty".to_string());
        }
        if self.chunk_created_at.trim().is_empty() {
            return Err("chunk chunk_created_at must be non-empty".to_string());
        }
        if self.text.is_empty() {
            return Err("chunk text must be non-empty".to_string());
        }
        Ok(())
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct GradedChunkRelevance {
    pub chunk_id: Uuid,
    pub score: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct GoldenRetrievalTargets {
    pub soft_positive_chunk_ids: Vec<Uuid>,
    pub strict_positive_chunk_ids: Vec<Uuid>,
    pub graded_relevance: Vec<GradedChunkRelevance>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct RetrievalQualityMetrics {
    pub evaluated_k: usize,
    pub recall_soft: f32,
    pub recall_strict: f32,
    pub rr_soft: f32,
    pub rr_strict: f32,
    pub ndcg: f32,
    pub first_relevant_rank_soft: Option<usize>,
    pub first_relevant_rank_strict: Option<usize>,
    pub num_relevant_soft: usize,
    pub num_relevant_strict: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct RetrievedChunk {
    pub chunk: Chunk,
    pub score: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct RetrievalOutput {
    pub chunks: Vec<RetrievedChunk>,
    pub metrics: Option<RetrievalQualityMetrics>,
    pub chunking_strategy: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct RerankedChunk {
    pub chunk: Chunk,
    pub retrieval_score: f32,
    pub rerank_score: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct RerankedRetrievalOutput {
    pub chunks: Vec<RerankedChunk>,
    pub metrics: Option<RetrievalQualityMetrics>,
    pub total_tokens: Option<usize>,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "PascalCase")]
pub enum RerankerKind {
    PassThrough,
    Heuristic,
    CrossEncoder,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "PascalCase")]
pub enum RetrieverKind {
    Dense,
    Hybrid,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct HeuristicWeights {
    pub retrieval_score: f32,
    pub query_term_coverage: f32,
    pub phrase_match_bonus: f32,
    pub title_section_match_bonus: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct CrossEncoderConfig {
    pub model_name: String,
    pub url: String,
    pub total_tokens: Option<usize>,
    pub cost_per_million_tokens: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(tag = "kind")]
pub enum RerankerConfig {
    PassThrough {
        final_k: usize,
    },
    Heuristic {
        final_k: usize,
        weights: HeuristicWeights,
    },
    CrossEncoder {
        final_k: usize,
        cross_encoder: CrossEncoderConfig,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(tag = "kind")]
pub enum RetrieverStrategyConfig {
    #[serde(rename = "bag_of_words")]
    BagOfWords {
        version: String,
        query_weighting: String,
    },
    #[serde(rename = "bm25_like")]
    Bm25Like {
        version: String,
        query_weighting: String,
        k1: f32,
        b: f32,
        idf_smoothing: String,
        term_stats_path: String,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(tag = "kind")]
pub enum RetrieverConfig {
    Dense {
        embedding_model_name: String,
        embedding_endpoint: String,
        embedding_dimension: usize,
        qdrant_collection_name: String,
        qdrant_vector_name: String,
        score_threshold: f32,
        corpus_version: String,
        chunking_strategy: String,
    },
    Hybrid {
        embedding_model_name: String,
        embedding_endpoint: String,
        embedding_dimension: usize,
        qdrant_collection_name: String,
        dense_vector_name: String,
        sparse_vector_name: String,
        score_threshold: f32,
        corpus_version: String,
        chunking_strategy: String,
        tokenizer_library: String,
        tokenizer_source: String,
        tokenizer_revision: Option<String>,
        preprocessing_kind: String,
        lowercase: bool,
        min_token_length: usize,
        vocabulary_path: String,
        strategy: RetrieverStrategyConfig,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct GenerationConfig {
    pub model: String,
    pub model_endpoint: String,
    pub temperature: f32,
    pub max_context_chunks: usize,
    pub input_cost_per_million_tokens: f64,
    pub output_cost_per_million_tokens: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct GenerationRequest {
    pub query: String,
    pub chunks: Vec<RetrievedChunk>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct GenerationResponse {
    pub answer: String,
    pub prompt_tokens: usize,
    pub completion_tokens: usize,
    pub total_tokens: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct UserResponse {
    pub answer: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct RetrievalResultItem {
    pub chunk_id: String,
    pub document_id: String,
    pub locator: String,
    pub retrieval_score: f32,
    pub rerank_score: f32,
    pub selected_for_generation: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct RequestCapture {
    pub runtime_run_id: String,
    pub request_id: String,
    pub trace_id: String,
    pub received_at: DateTime<Utc>,
    pub raw_query: String,
    pub normalized_query: String,
    pub input_token_count: usize,
    pub pipeline_config_version: String,
    pub corpus_version: String,
    pub retriever_version: String,
    pub retriever_kind: RetrieverKind,
    pub retriever_config: RetrieverConfig,
    pub embedding_model: String,
    pub prompt_template_id: String,
    pub prompt_template_version: String,
    pub generation_model: String,
    pub generation_config: GenerationConfig,
    pub reranker_kind: RerankerKind,
    pub reranker_config: Option<RerankerConfig>,
    pub top_k_requested: usize,
    pub retrieval_results: Vec<RetrievalResultItem>,
    pub final_answer: String,
    pub prompt_tokens: usize,
    pub completion_tokens: usize,
    pub total_tokens: usize,
    pub retrieval_stage_metrics: Option<RetrievalQualityMetrics>,
    pub reranking_stage_metrics: Option<RetrievalQualityMetrics>,
}

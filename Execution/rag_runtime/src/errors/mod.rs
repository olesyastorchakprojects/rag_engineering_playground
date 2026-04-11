use thiserror::Error;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ErrorCategory {
    Startup,
    Runtime,
}

#[derive(Debug, Error)]
pub enum InputValidationError {
    #[error("query is empty after normalization")]
    EmptyQuery,
    #[error("query token count {actual} exceeds max_query_tokens {max_allowed}")]
    QueryTooLong { actual: usize, max_allowed: usize },
    #[error("failed to initialize input-validation tokenizer: {message}")]
    TokenizerInitialization { message: String },
}

impl InputValidationError {
    pub fn error_type(&self) -> &'static str {
        match self {
            Self::EmptyQuery => "input_validation.empty_query",
            Self::QueryTooLong { .. } => "input_validation.query_too_long",
            Self::TokenizerInitialization { .. } => "input_validation.tokenizer_initialization",
        }
    }
}

#[derive(Debug, Error)]
pub enum RetrievalError {
    #[error("retrieval configuration is invalid: {message}")]
    InvalidConfiguration { message: String },
    #[error("embedding request failed: {message}")]
    EmbeddingRequest { message: String },
    #[error("embedding response validation failed: {message}")]
    EmbeddingResponseValidation { message: String },
    #[error("embedding dimension mismatch: expected {expected}, got {actual}")]
    EmbeddingDimensionMismatch { expected: usize, actual: usize },
    #[error("sparse tokenizer initialization failed: {message}")]
    SparseTokenizerInitialization { message: String },
    #[error("retrieval artifact load failed: {message}")]
    ArtifactLoad { message: String },
    #[error("retrieval artifact validation failed: {message}")]
    ArtifactValidation { message: String },
    #[error("sparse query construction failed: {message}")]
    SparseQueryConstruction { message: String },
    #[error("sparse query vector is empty after normalization and vocabulary lookup")]
    EmptySparseQueryVector,
    #[error("hybrid query request construction failed: {message}")]
    QueryConstruction { message: String },
    #[error("qdrant request failed: {message}")]
    QdrantRequest { message: String },
    #[error("qdrant response validation failed: {message}")]
    QdrantResponseValidation { message: String },
    #[error("chunk payload mapping failed: {message}")]
    PayloadMapping { message: String },
    #[error("retrieval metrics computation failed: {message}")]
    MetricsComputation { message: String },
}

impl RetrievalError {
    pub fn error_type(&self) -> &'static str {
        match self {
            Self::InvalidConfiguration { .. } => "retrieval.invalid_configuration",
            Self::EmbeddingRequest { .. } => "retrieval.embedding_request",
            Self::EmbeddingResponseValidation { .. } => "retrieval.embedding_response_validation",
            Self::EmbeddingDimensionMismatch { .. } => "retrieval.embedding_dimension_mismatch",
            Self::SparseTokenizerInitialization { .. } => {
                "retrieval.sparse_tokenizer_initialization"
            }
            Self::ArtifactLoad { .. } => "retrieval.artifact_load",
            Self::ArtifactValidation { .. } => "retrieval.artifact_validation",
            Self::SparseQueryConstruction { .. } => "retrieval.sparse_query_construction",
            Self::EmptySparseQueryVector => "retrieval.empty_sparse_query_vector",
            Self::QueryConstruction { .. } => "retrieval.query_construction",
            Self::QdrantRequest { .. } => "retrieval.qdrant_request",
            Self::QdrantResponseValidation { .. } => "retrieval.qdrant_response_validation",
            Self::PayloadMapping { .. } => "retrieval.payload_mapping",
            Self::MetricsComputation { .. } => "retrieval.metrics_computation",
        }
    }
}

#[derive(Debug, Error)]
pub enum GenerationError {
    #[error("generation input is invalid: {message}")]
    InvalidInput { message: String },
    #[error("generation chunk limit exceeded: actual {actual}, max_allowed {max_allowed}")]
    ChunkLimitExceeded { actual: usize, max_allowed: usize },
    #[error("generation prompt token limit exceeded: actual {actual}, max_allowed {max_allowed}")]
    PromptTokenLimitExceeded { actual: usize, max_allowed: usize },
    #[error("generation request failed: {message}")]
    RequestFailure { message: String },
    #[error("generation response validation failed: {message}")]
    ResponseValidation { message: String },
    #[error("failed to initialize generation tokenizer: {message}")]
    TokenizerInitialization { message: String },
    #[error("generation unexpected internal state: {message}")]
    UnexpectedInternalState { message: String },
}

impl GenerationError {
    pub fn error_type(&self) -> &'static str {
        match self {
            Self::InvalidInput { .. } => "generation.invalid_input",
            Self::ChunkLimitExceeded { .. } => "generation.chunk_limit_exceeded",
            Self::PromptTokenLimitExceeded { .. } => "generation.prompt_token_limit_exceeded",
            Self::RequestFailure { .. } => "generation.request_failure",
            Self::ResponseValidation { .. } => "generation.response_validation",
            Self::TokenizerInitialization { .. } => "generation.tokenizer_initialization",
            Self::UnexpectedInternalState { .. } => "generation.unexpected_internal_state",
        }
    }
}

#[derive(Debug, Error)]
pub enum RerankingError {
    #[error("reranking configuration is invalid: {message}")]
    InvalidConfiguration { message: String },
    #[error("reranking internal state is invalid: {message}")]
    InternalState { message: String },
    #[error("reranking candidate transformation failed: {message}")]
    CandidateTransformation { message: String },
    #[error("reranking service request failed: status {status}, message: {message}")]
    ServiceRequest { status: u16, message: String },
    #[error("reranking service warming: {message}")]
    Warmup { message: String },
    #[error("reranking service response validation failed: {message}")]
    ServiceResponseValidation { message: String },
    #[error("reranking metrics computation failed: {message}")]
    MetricsComputation { message: String },
}

impl RerankingError {
    pub fn error_type(&self) -> &'static str {
        match self {
            Self::InvalidConfiguration { .. } => "reranking.invalid_configuration",
            Self::InternalState { .. } => "reranking.internal_state",
            Self::CandidateTransformation { .. } => "reranking.candidate_transformation",
            Self::ServiceRequest { .. } => "reranking.service_request",
            Self::Warmup { .. } => "reranking.warmup",
            Self::ServiceResponseValidation { .. } => "reranking.service_response_validation",
            Self::MetricsComputation { .. } => "reranking.metrics_computation",
        }
    }

    pub fn is_retryable(&self) -> bool {
        match self {
            Self::Warmup { .. } => true,
            Self::ServiceRequest { status, .. } => {
                *status == 0 || *status == 429 || (500..600).contains(status)
            }
            Self::InvalidConfiguration { .. }
            | Self::InternalState { .. }
            | Self::CandidateTransformation { .. }
            | Self::ServiceResponseValidation { .. }
            | Self::MetricsComputation { .. } => false,
        }
    }
}

#[derive(Debug, Error)]
pub enum OrchestrationError {
    #[error("retrieval returned no chunks")]
    EmptyRetrievalOutput,
    #[error("reranking returned no chunks")]
    EmptyRerankedOutput,
    #[error("batch question not found in golden retrieval companion file: {question:?}")]
    BatchQuestionMissingFromGoldenCompanion { question: String },
    #[error("unexpected internal orchestration state: {message}")]
    UnexpectedState { message: String },
}

impl OrchestrationError {
    pub fn error_type(&self) -> &'static str {
        match self {
            Self::EmptyRetrievalOutput => "orchestration.empty_retrieval_output",
            Self::EmptyRerankedOutput => "orchestration.empty_reranked_output",
            Self::BatchQuestionMissingFromGoldenCompanion { .. } => {
                "orchestration.batch_question_missing_from_golden_companion"
            }
            Self::UnexpectedState { .. } => "orchestration.unexpected_state",
        }
    }
}

#[derive(Debug, Error)]
pub enum RequestCaptureStoreError {
    #[error("request-capture validation failed: {message}")]
    Validation { message: String },
    #[error("request-capture serialization failed: {message}")]
    Serialization { message: String },
    #[error("request-capture database connection failed: {message}")]
    Connection { message: String },
    #[error("request-capture insert execution failed: {message}")]
    InsertExecution { message: String },
    #[error("request-capture duplicate request id: {request_id}")]
    DuplicateRequestId { request_id: String },
    #[error("request-capture unexpected internal state: {message}")]
    Internal { message: String },
}

impl RequestCaptureStoreError {
    pub fn error_type(&self) -> &'static str {
        match self {
            Self::Validation { .. } => "request_capture_store.validation",
            Self::Serialization { .. } => "request_capture_store.serialization",
            Self::Connection { .. } => "request_capture_store.connection",
            Self::InsertExecution { .. } => "request_capture_store.insert_execution",
            Self::DuplicateRequestId { .. } => "request_capture_store.duplicate_request_id",
            Self::Internal { .. } => "request_capture_store.internal",
        }
    }
}

#[derive(Debug, Error)]
pub enum ObservabilityError {
    #[error("observability initialization failed: {message}")]
    Initialization { message: String },
}

impl ObservabilityError {
    pub fn error_type(&self) -> &'static str {
        match self {
            Self::Initialization { .. } => "observability.initialization",
        }
    }
}

#[derive(Debug, Error)]
pub enum RagRuntimeError {
    #[error("startup error: {message}")]
    Startup { message: String },
    #[error(transparent)]
    InputValidation(#[from] InputValidationError),
    #[error(transparent)]
    Retrieval(#[from] RetrievalError),
    #[error(transparent)]
    Reranking(#[from] RerankingError),
    #[error(transparent)]
    Generation(#[from] GenerationError),
    #[error(transparent)]
    Orchestration(#[from] OrchestrationError),
    #[error(transparent)]
    RequestCaptureStore(#[from] RequestCaptureStoreError),
    #[error(transparent)]
    Observability(#[from] ObservabilityError),
}

impl RagRuntimeError {
    pub fn startup(message: impl Into<String>) -> Self {
        Self::Startup {
            message: message.into(),
        }
    }

    pub fn category(&self) -> ErrorCategory {
        match self {
            Self::Startup { .. } | Self::Observability(_) => ErrorCategory::Startup,
            Self::InputValidation(_)
            | Self::Retrieval(_)
            | Self::Reranking(_)
            | Self::Generation(_)
            | Self::Orchestration(_)
            | Self::RequestCaptureStore(_) => ErrorCategory::Runtime,
        }
    }

    pub fn error_type(&self) -> &'static str {
        match self {
            Self::Startup { .. } => "rag_runtime.startup",
            Self::InputValidation(error) => error.error_type(),
            Self::Retrieval(error) => error.error_type(),
            Self::Reranking(error) => error.error_type(),
            Self::Generation(error) => error.error_type(),
            Self::Orchestration(error) => error.error_type(),
            Self::RequestCaptureStore(error) => error.error_type(),
            Self::Observability(error) => error.error_type(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn startup_error_constructor_returns_startup_variant() {
        let error = RagRuntimeError::startup("boom");
        assert!(matches!(error, RagRuntimeError::Startup { .. }));
        assert_eq!(error.error_type(), "rag_runtime.startup");
    }

    #[test]
    fn error_types_are_stable() {
        assert_eq!(
            InputValidationError::EmptyQuery.error_type(),
            "input_validation.empty_query"
        );
        assert_eq!(
            RetrievalError::QdrantRequest {
                message: "x".to_string()
            }
            .error_type(),
            "retrieval.qdrant_request"
        );
        assert_eq!(
            RerankingError::InvalidConfiguration {
                message: "x".to_string()
            }
            .error_type(),
            "reranking.invalid_configuration"
        );
        assert!(
            RerankingError::Warmup {
                message: "x".to_string()
            }
            .is_retryable()
        );
        assert_eq!(
            GenerationError::RequestFailure {
                message: "x".to_string()
            }
            .error_type(),
            "generation.request_failure"
        );
        assert_eq!(
            OrchestrationError::EmptyRetrievalOutput.error_type(),
            "orchestration.empty_retrieval_output"
        );
        assert_eq!(
            OrchestrationError::EmptyRerankedOutput.error_type(),
            "orchestration.empty_reranked_output"
        );
        assert_eq!(
            ObservabilityError::Initialization {
                message: "x".to_string()
            }
            .error_type(),
            "observability.initialization"
        );
    }
}

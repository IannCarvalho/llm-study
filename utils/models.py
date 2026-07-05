"""
Pydantic Models - Type-safe data schemas

Centralized data structures for validation and serialization.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class SeverityLevel(str, Enum):
    """Vulnerability severity levels."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class VulnerabilityType(str, Enum):
    """Common vulnerability types."""
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    CSRF = "csrf"
    RCE = "rce"
    AUTH_BYPASS = "auth_bypass"
    MEMORY = "memory"
    CRYPTO = "crypto"
    OTHER = "other"


# ============================================================================
# CVE MODELS
# ============================================================================

class CVEMetadata(BaseModel):
    """CVE metadata."""
    cve_id: str
    severity: SeverityLevel
    cvss_score: float = Field(ge=0.0, le=10.0)
    affected_versions: List[str] = []
    cvss_vector: Optional[str] = None
    published_date: Optional[str] = None
    vulnerability_type: VulnerabilityType = VulnerabilityType.OTHER

    class Config:
        use_enum_values = False


class CVEData(BaseModel):
    """Complete CVE record with metadata and description."""
    id: str
    severity: SeverityLevel
    score: float = Field(ge=0.0, le=10.0)
    description: str
    affected_versions: List[str] = []
    cvss_vector: str
    metadata: Dict[str, Any] = {}

    class Config:
        use_enum_values = False

    @validator("description")
    def description_not_empty(cls, v):
        """Ensure description is not empty."""
        if not v or not v.strip():
            raise ValueError("Description cannot be empty")
        return v


# ============================================================================
# VULNERABILITY & DOCUMENT MODELS
# ============================================================================

class VulnerabilityMetadata(BaseModel):
    """Metadata for a vulnerability document."""
    severity: SeverityLevel
    type: VulnerabilityType
    cve_id: Optional[str] = None
    tags: List[str] = []

    class Config:
        use_enum_values = False


class Vulnerability(BaseModel):
    """Vulnerability document for indexing."""
    id: str
    text: str
    metadata: VulnerabilityMetadata

    class Config:
        use_enum_values = False


class Document(BaseModel):
    """Generic document for indexing."""
    id: str
    content: str
    metadata: Dict[str, Any] = {}
    source: Optional[str] = None


# ============================================================================
# SEARCH & RETRIEVAL MODELS
# ============================================================================

class SearchResult(BaseModel):
    """Single search result."""
    id: str
    content: str
    score: float = Field(ge=0.0, le=1.0)
    metadata: Dict[str, Any] = {}
    source: Optional[str] = None
    retrieval_method: Optional[str] = None  # "bm25", "semantic", "hybrid"


class SearchResults(BaseModel):
    """Collection of search results."""
    query: str
    results: List[SearchResult]
    total_results: int
    search_method: str
    elapsed_time: float = 0.0  # seconds
    metadata: Dict[str, Any] = {}


class RankingResult(BaseModel):
    """Result from a ranking operation."""
    document_id: str
    content: str
    rank: int
    score: float
    source_method: str  # "bm25", "semantic", etc.


# ============================================================================
# RAG PIPELINE MODELS
# ============================================================================

class RAGContext(BaseModel):
    """Context for RAG generation."""
    query: str
    retrieved_documents: List[Document]
    context_text: str
    source_indices: List[int] = []


class RAGResponse(BaseModel):
    """Response from RAG pipeline."""
    query: str
    context: str
    response: str
    retrieved_documents: List[SearchResult]
    model: str
    elapsed_time: float = 0.0


class RAGConfig(BaseModel):
    """Configuration for RAG pipeline."""
    retriever: str = "hybrid"  # "bm25", "semantic", "hybrid"
    top_k: int = 3
    model: str = "mistral"
    temperature: float = 0.7
    max_tokens: int = 512


# ============================================================================
# AGENTIC MODELS
# ============================================================================

class ToolCall(BaseModel):
    """Parsed tool call from LLM output."""
    tool_name: str
    tool_input: str
    raw_output: str


class Message(BaseModel):
    """Chat message."""
    role: str  # "user", "assistant", "system"
    content: str


class ConversationTurn(BaseModel):
    """Single turn in a conversation."""
    user_message: str
    assistant_message: str
    tools_used: List[ToolCall] = []
    metadata: Dict[str, Any] = {}


# ============================================================================
# EMBEDDING MODELS
# ============================================================================

class EmbeddingResult(BaseModel):
    """Result from embedding operation."""
    text: str
    embedding: List[float]
    model: str
    dimension: int


class BatchEmbeddingResult(BaseModel):
    """Results from batch embedding operation."""
    texts: List[str]
    embeddings: List[List[float]]
    model: str
    dimension: int
    total_texts: int
    elapsed_time: float = 0.0


# ============================================================================
# LLM RESPONSE MODELS
# ============================================================================

class LLMResponse(BaseModel):
    """Response from LLM."""
    content: str
    model: str
    tokens_used: Optional[int] = None
    finish_reason: Optional[str] = None


class StreamChunk(BaseModel):
    """Chunk from streaming LLM response."""
    content: str
    index: int
    is_final: bool = False


__all__ = [
    # Enums
    "SeverityLevel",
    "VulnerabilityType",
    # CVE Models
    "CVEData",
    "CVEMetadata",
    # Vulnerability Models
    "Vulnerability",
    "VulnerabilityMetadata",
    "Document",
    # Search Models
    "SearchResult",
    "SearchResults",
    "RankingResult",
    # RAG Models
    "RAGContext",
    "RAGResponse",
    "RAGConfig",
    # Agentic Models
    "ToolCall",
    "Message",
    "ConversationTurn",
    # Embedding Models
    "EmbeddingResult",
    "BatchEmbeddingResult",
    # LLM Models
    "LLMResponse",
    "StreamChunk",
]

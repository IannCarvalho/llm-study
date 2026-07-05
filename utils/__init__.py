"""
Utilities Package - Centralized shared infrastructure

Provides reusable components for AI applications:
- config: Centralized configuration management
- constants: Application constants
- models: Pydantic data models for type safety
- logging: Centralized logging setup
- llm_client: Unified LLM interface (Ollama/OpenAI)
- agentic_utils: Agentic patterns, shared data
- data_loader: JSON data loading with caching
- prompts: System prompts for agentic patterns
- semantic_embeddings: True semantic embeddings (SentenceTransformers)
- chunking_utils: Document splitting strategies

Usage (both styles work):
    from utils import get_llm_client, get_config
    from utils.data_loader import load_cves, search_cves
    from utils.models import CVEData, Vulnerability
    from utils import embed_text, chunk_text

Lazy loading: Imports are deferred until first access, avoiding 
unsupported dependency cascade (e.g., can use chunking without LLM deps).

Modern Retrieval Strategy:
  - BM25: For keyword/exact search (from hybrid_search.py)
  - embed_text/embed_texts: For meaning-based search (neural)
  - Hybrid: Combine both for production-grade systems
"""

# Lazy imports - only import what's needed
def __getattr__(name):
    """Lazy load utilities on demand."""
    _lazy_imports = {
        # Configuration
        'get_config': ('config', 'get_config'),
        'get_settings': ('config', 'get_settings'),
        'Settings': ('config', 'Settings'),
        # Constants
        'COLLECTION_NAME_VULNERABILITIES': ('constants', 'COLLECTION_NAME_VULNERABILITIES'),
        'DEFAULT_TOP_K': ('constants', 'DEFAULT_TOP_K'),
        'RRF_K': ('constants', 'RRF_K'),
        # Models
        'CVEData': ('models', 'CVEData'),
        'SearchResult': ('models', 'SearchResult'),
        'RAGResponse': ('models', 'RAGResponse'),
        # Logging
        'get_logger': ('logging', 'get_logger'),
        'get_app_logger': ('logging', 'get_app_logger'),
        'setup_logging': ('logging', 'setup_logging'),
        # LLM Client
        'LLMClient': ('llm_client', 'LLMClient'),
        'get_llm_client': ('llm_client', 'get_llm_client'),
        'reset_llm_client': ('llm_client', 'reset_llm_client'),
        # Agentic Utils
        'get_cve_documents': ('agentic_utils', 'get_cve_documents'),
        # Data Loader
        'load_cves': ('data_loader', 'load_cves'),
        'get_cve_by_id': ('data_loader', 'get_cve_by_id'),
        'search_cves': ('data_loader', 'search_cves'),
        # Semantic Embeddings
        'embed_text': ('semantic_embeddings', 'embed_text'),
        'embed_texts': ('semantic_embeddings', 'embed_texts'),
        # Chunking Utils
        'chunk_text': ('chunking_utils', 'chunk_text'),
    }
    
    if name in _lazy_imports:
        module_name, attr_name = _lazy_imports[name]
        from importlib import import_module
        module = import_module(f'.{module_name}', __name__)
        return getattr(module, attr_name)
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Configuration
    "get_config",
    "get_settings",
    "Settings",
    # Constants
    "COLLECTION_NAME_VULNERABILITIES",
    "DEFAULT_TOP_K",
    "RRF_K",
    # Models
    "CVEData",
    "SearchResult",
    "RAGResponse",
    # Logging
    "get_logger",
    "get_app_logger",
    # LLM
    "LLMClient",
    "get_llm_client",
    "reset_llm_client",
    # Agentic
    "get_cve_documents",
    # Data
    "load_cves",
    "get_cve_by_id",
    "search_cves",
    # Embedding
    "embed_text",
    "embed_texts",
    # Chunking
    "chunk_text",
]

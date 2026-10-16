"""
Hybrid Search: Combining Keyword and Semantic Search

Hybrid search combines two retrieval methods:
- Keyword search (BM25): Finds exact word matches using statistical ranking
- Semantic search (Embeddings): Finds meaning-based matches using neural networks

This script demonstrates Reciprocal Rank Fusion (RRF), a simple and effective
method to combine results from both approaches. RRF rewards documents that rank
high in either method, creating a balanced final ranking.

Now using the refactored search engine architecture with unified interface.
"""

from utils.search import BM25Search, SemanticSearch, HybridSearch
from utils.data_loader import get_cve_documents
from utils.logging import get_logger

logger = get_logger(__name__)


def main():
    """Demonstrate hybrid search with unified search engine interface."""
    
    # Get CVE documents
    cve_docs = get_cve_documents()
    documents = [
        {
            "id": cve_id,
            "content": text,
            "metadata": {}
        }
        for cve_id, text in cve_docs.items()
    ]
    
    query = "buffer overflow instruction pointer"
    
    print("=" * 70)
    print("Hybrid Search: BM25 (Keyword) + Semantic (Embeddings)")
    print("Combination Method: Reciprocal Rank Fusion (RRF)")
    print("=" * 70)
    
    print(f'\nQuery: "{query}"')
    print("-" * 70)
    
    # Initialize search engines
    bm25_engine = BM25Search()
    semantic_engine = SemanticSearch()
    hybrid_engine = HybridSearch()
    
    # Perform searches
    bm25_results = bm25_engine.search(query, documents, top_k=2)
    semantic_results = semantic_engine.search(query, documents, top_k=2)
    hybrid_results = hybrid_engine.search(query, documents, top_k=2)
    
    # Display results
    print("\n  BM25 (Keyword) Results:")
    if bm25_results:
        for i, result in enumerate(bm25_results, 1):
            print(f"    {i}. {result.id} (score: {result.score:.4f})")
    else:
        print("    (no results)")
    
    print("\n  Semantic (Embeddings) Results:")
    if semantic_results:
        for i, result in enumerate(semantic_results, 1):
            print(f"    {i}. {result.id} (score: {result.score:.4f})")
    else:
        print("    (no results)")
    
    print("\n  RRF Combined Results:")
    if hybrid_results:
        for i, result in enumerate(hybrid_results, 1):
            print(f"    {i}. {result.id} (RRF score: {result.score:.4f})")
    else:
        print("    (no results)")

if __name__ == "__main__":
    main()

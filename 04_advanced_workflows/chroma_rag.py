"""
Chroma RAG: Local Vector Database for Rapid Prototyping

Chroma is a lightweight, embedded vector database perfect for MVPs.
Zero setup, runs locally, excellent for quick RAG implementation.

Installation: pip install chromadb

This example demonstrates the refactored RAG pipeline architecture.
Now using centralized abstractions and configuration.
"""

from utils.agentic_utils import QUERY
from utils.rag_pipeline import ChromaRAGPipeline
from utils.prompts import RAG_SYSTEM
from utils.data_loader import load_cves
from utils.logging import get_logger

logger = get_logger(__name__)


def main():
    """Run Chroma RAG pipeline with refactored architecture."""
    
    # Initialize RAG pipeline (handles Chroma setup automatically)
    rag = ChromaRAGPipeline(
        collection_name="vulnerabilities",
        search_method="hybrid",
        top_k=3
    )
    
    # Load and index documents (only if empty)
    if rag.count_documents() == 0:
        cves = load_cves()
        documents = [
            {
                "id": cve.id,
                "text": cve.description,
                "metadata": {"severity": cve.severity, "score": cve.score}
            }
            for cve in cves
        ]
        rag.add_documents(documents)
        logger.info(f"Indexed {len(documents)} CVE documents")
    else:
        logger.info(f"Collection already has {rag.count_documents()} documents")
    
    print(f"\n{'='*70}")
    print(f"Query: '{QUERY}'")
    print(f"{'='*70}\n")
    
    # Generate RAG response
    response = rag.generate_rag_response(
        query=QUERY,
        system_prompt=RAG_SYSTEM
    )
    
    # Display results
    print("Retrieved Documents:")
    print("-" * 70)
    for i, doc in enumerate(response.retrieved_documents, 1):
        print(f"\n{i}. {doc.id} (similarity: {doc.score:.4f})")
        print(f"   {doc.content[:100]}...")
    
    print(f"\n{'='*70}")
    print("RAG Context:")
    print("-" * 70)
    print(response.context)
    
    print(f"\n{'='*70}")
    print("LLM Response:")
    print("-" * 70)
    print(response.response)
    
    print(f"\n{'='*70}")
    print(f"Execution time: {response.elapsed_time:.2f}s")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()

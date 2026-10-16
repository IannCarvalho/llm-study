"""
Pinecone RAG: Production-Grade Vector Database

Pinecone is a managed, scalable vector database ideal for production RAG systems.

Setup:
    1. pip install pinecone
    2. Add PINECONE_API_KEY to .env
    3. Create index via Pinecone console
"""

from pinecone import Pinecone

from utils.agentic_utils import QUERY
from utils.config import get_config
from utils.data_loader import load_cves
from utils.llm_client import get_llm_client
from utils.prompts import RAG_SYSTEM
from utils.semantic_embeddings import embed_text, embed_texts


def main():
    """Run Pinecone RAG pipeline."""
    api_key = get_config().pinecone_api_key
    if not api_key:
        print("Error: PINECONE_API_KEY not configured in .env")
        print("Get it from: https://www.pinecone.io")
        return
    
    pc = Pinecone(api_key=api_key)
    index = pc.Index("llm-study")
    
    print("Connected to Pinecone\n")
    
    # Generate real embeddings for documents
    print("Generating real embeddings (all-MiniLM-L6-v2)...")
    cves = load_cves()
    cve_texts = [cve.description for cve in cves]
    embeddings = embed_texts(cve_texts)
    
    # Create documents with real embeddings
    cves_with_embeddings = [
        {
            "id": cve.id,
            "text": cve.description,
            "embedding": embeddings[i].tolist(),
            "metadata": {"severity": cve.severity, "score": cve.score}
        }
        for i, cve in enumerate(cves)
    ]
    
    # Upsert vectors to index
    print(f"Upserting documents with real embeddings ({embeddings.shape[1]}-dim)...")
    vectors_to_upsert = [
        (cve["id"], cve["embedding"], cve["metadata"]) 
        for cve in cves_with_embeddings
    ]
    index.upsert(vectors=vectors_to_upsert)
    print(f"Upserted {len(cves_with_embeddings)} documents\n")
    
    # Generate real embedding for query
    query_embedding = embed_text(QUERY).tolist()
    
    print(f"Query: '{QUERY}'")
    print("-" * 70)
    
    results = index.query(
        vector=query_embedding, top_k=1, include_metadata=True
    )

    print(f"Found: {results}\n")

    print("\nRetrieved Documents:")
    
    # Build context from search results
    context_lines = []
    for match in results["matches"]:
        doc_id = match["id"]
        doc = next((cve.description for cve in cves if cve.id == doc_id), "")
        if doc:
            context_lines.append(doc)
    
    context = "\n".join(context_lines)
    
    # Create RAG prompt using centralized template
    prompt = RAG_SYSTEM.format(context=context, query=QUERY)
    
    print("Prompt sent to LLM:\n")
    print(prompt)
    print("\n" + "="*70)
    print("LLM Response:\n")
    
    llm_client = get_llm_client(temperature=0.7)
    response = llm_client.generate(prompt, max_tokens=256)
    print(response)


if __name__ == "__main__":
    main()

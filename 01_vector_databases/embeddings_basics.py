"""
Keyword Search Basics: BM25 Retrieval

BM25 (Best Matching 25) is the industry-standard algorithm for keyword-based 
(sparse) search. It's an evolution of TF-IDF that includes:

- Term Frequency saturation: Words don't increase score linearly
- Inverse Document Frequency: Rewards rare, relevant words  
- Document length normalization: Prevents bias toward longer documents
- Parameters k1 and b: Fine-tune frequency saturation and length impact

BM25 is more robust than TF-IDF and used by search engines like Elasticsearch.

This example demonstrates BM25 with real CVE data.
Data source: Real CVEs from cves.json.
"""

from rank_bm25 import BM25Okapi
from utils.agentic_utils import get_cve_documents
import re


def tokenize(text: str) -> list[str]:
    """Simple tokenizer: lowercase and split into words."""
    return re.findall(r"\w+", text.lower())


if __name__ == "__main__":
    print("="*70)
    print("Keyword Search: BM25 Algorithm")
    print("="*70)
    
    # Part 1: Index documents
    print("\nPart 1: Indexing CVE Database with BM25")
    print("-"*70)
    
    cve_docs = get_cve_documents()
    sample_texts = list(cve_docs.values())
    sample_ids = list(cve_docs.keys())
    
    # Tokenize documents
    tokenized_docs = [tokenize(text) for text in sample_texts]
    
    # Create BM25 index
    bm25 = BM25Okapi(tokenized_docs)
    
    for i, cve_id in enumerate(sample_ids):
        print(f"\n{cve_id}:")
        print(f"  Tokens: {len(tokenized_docs[i])}")
        print(f"  Content preview: {sample_texts[i][:20]}...")
    
    # Part 2: Search query
    print("\n\nPart 2: Searching with BM25")
    print("-"*70)
    
    query = "buffer overflow instruction pointer"
    print(f"\nQuery: \"{query}\"")
    
    tokenized_query = tokenize(query)
    scores = bm25.get_scores(tokenized_query)
    top_idx = scores.argmax()
    
    print(f"  1. {sample_ids[top_idx]}")
    print(f"     Content: {sample_texts[top_idx][:20]}...")



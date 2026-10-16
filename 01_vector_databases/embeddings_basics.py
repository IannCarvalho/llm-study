"""
Keyword Search vs. Embeddings: BM25 first, then semantic similarity

BM25 (Best Matching 25) is the industry-standard algorithm for keyword-based
(sparse) search. It's an evolution of TF-IDF that includes:

- Term Frequency saturation: Words don't increase score linearly
- Inverse Document Frequency: Rewards rare, relevant words
- Document length normalization: Prevents bias toward longer documents
- Parameters k1 and b: Fine-tune frequency saturation and length impact

BM25 is more robust than TF-IDF and used by search engines like Elasticsearch.

Embeddings (dense vectors) compare meaning instead of exact words: Part 3 ranks
the same documents by cosine similarity, so the two approaches can be compared
side by side (hybrid_search.py then combines them with RRF).

This example demonstrates both on the project's CVE base (cves.json, synthetic
records).
"""

import numpy as np
from rank_bm25 import BM25Okapi

from utils.data_loader import get_cve_documents
from utils.text import tokenize

PREVIEW_CHARS = 60


def preview(document: str) -> str:
    """First characters of the document's Description line (the readable part)."""
    for line in document.splitlines():
        if line.startswith("Description: "):
            return line[len("Description: "):][:PREVIEW_CHARS]
    return document[:PREVIEW_CHARS]


def cosine_similarities(query_vector: np.ndarray, doc_vectors: np.ndarray) -> np.ndarray:
    """Cosine similarity between one query vector and each document vector."""
    norms = np.linalg.norm(doc_vectors, axis=1) * np.linalg.norm(query_vector)
    return doc_vectors @ query_vector / np.where(norms == 0, 1.0, norms)


def main() -> None:
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
        print(f"  Content preview: {preview(sample_texts[i])}...")

    # Part 2: Search query
    print("\n\nPart 2: Searching with BM25")
    print("-"*70)

    query = "buffer overflow instruction pointer"
    print(f"\nQuery: \"{query}\"")

    tokenized_query = tokenize(query)
    scores = bm25.get_scores(tokenized_query)
    top_idx = scores.argmax()

    print(f"  1. {sample_ids[top_idx]}")
    print(f"     Content: {preview(sample_texts[top_idx])}...")

    # Part 3: same documents, ranked by meaning (embeddings + cosine similarity)
    print("\n\nPart 3: Semantic search with embeddings (all-MiniLM-L6-v2)")
    print("-"*70)
    paraphrase = "attackers can guess the secret keys because the randomness is poor"
    try:
        from utils.semantic_embeddings import embed_text, embed_texts

        doc_vectors = embed_texts(sample_texts)
        for text in (query, paraphrase):
            bm25_best = sample_ids[int(bm25.get_scores(tokenize(text)).argmax())]
            sims = cosine_similarities(embed_text(text), doc_vectors)
            ranking = sorted(zip(sample_ids, sims, strict=True), key=lambda pair: -pair[1])
            print(f"\nQuery: \"{text}\"")
            print(f"  BM25 top-1:      {bm25_best}")
            for rank, (cve_id, sim) in enumerate(ranking, 1):
                print(f"  Embeddings #{rank}:   {cve_id} (cosine {sim:.3f})")
    except Exception as exc:  # noqa: BLE001 - e.g. offline and the model is not cached
        print(f"Embedding model unavailable ({exc}); Parts 1-2 above still ran.")


if __name__ == "__main__":
    main()

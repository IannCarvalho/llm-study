"""
Offline RAG Metrics — Evaluating Retrieval Without an LLM

This script measures the *retrieval* half of a RAG pipeline using deterministic,
reference-based metrics that need no LLM (so it runs without Ollama):

- precision@k: of the top-k documents returned by the retriever, how many are
  actually relevant to the query (according to a small ground-truth set).
- groundedness proxy: a cheap, LLM-free signal for "is the answer supported by
  the retrieved context?". Here we approximate it as the fraction of the query's
  content terms that appear in the retrieved documents (lexical term overlap).
  It is a *proxy*: it does not understand meaning, but it is deterministic,
  instant, and catches the obvious failure mode of retrieving off-topic docs.

The retriever under test is the project's hybrid engine
(`create_search_engine('hybrid')`) running over `get_cve_documents()`. The same
inputs always yield the same ranking, so the reported numbers are reproducible.
"""


from utils.data_loader import get_cve_documents
from utils.search import as_search_documents, create_search_engine
from utils.text import content_terms

# ---------------------------------------------------------------------------
# Evaluation set
# ---------------------------------------------------------------------------
# Each case is a query plus the set of CVE ids a correct retriever should return.
# The ground truth is derived from the dataset itself (3 CVEs: an RCE, a SQL
# injection, and a cryptographic weakness), so the labels are not guesses.
EVAL_CASES = [
    {
        "query": "buffer overflow remote code execution in the request handler",
        "relevant_ids": {"CVE-2024-1234"},
    },
    {
        "query": "sql injection bypass authentication login form",
        "relevant_ids": {"CVE-2024-5678"},
    },
    {
        "query": "weak random number generator cryptographic key",
        "relevant_ids": {"CVE-2024-9012"},
    },
]

# Terms that carry no topical signal — excluded from the groundedness proxy so a
# query is not judged "grounded" just because stopwords appear in every document.
_STOPWORDS: set[str] = {
    "a", "an", "and", "the", "in", "on", "of", "to", "for", "with", "by",
    "is", "are", "be", "at", "or", "from", "into",
}


def _content_terms(text: str) -> set[str]:
    """Content-bearing terms: tokens minus this module's stopwords and pure numbers."""
    return content_terms(text, _STOPWORDS)


def precision_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """
    Fraction of the top-k retrieved documents that are relevant.

    Args:
        retrieved_ids: document ids in rank order (best first).
        relevant_ids: the ground-truth relevant ids for the query.
        k: cutoff rank.

    Returns:
        Hits-in-top-k / k, in [0.0, 1.0]. Dividing by k (not by the number
        actually returned) is the standard definition and keeps short result
        lists from being flattered.
    """
    if k <= 0:
        return 0.0
    top_k = retrieved_ids[:k]
    hits = sum(1 for doc_id in top_k if doc_id in relevant_ids)
    return hits / k


def groundedness_proxy(query: str, retrieved_docs: list[str]) -> float:
    """
    LLM-free groundedness signal: term overlap between the query and the pooled
    retrieved context.

    Returns the fraction of the query's content terms that are present somewhere
    in the retrieved documents. 1.0 means every topical term in the query is
    covered by the context; 0.0 means none is (a strong hint the retrieval is
    off-topic and any generated answer would be ungrounded).
    """
    query_terms = _content_terms(query)
    if not query_terms:
        return 0.0

    context_terms: set[str] = set()
    for doc in retrieved_docs:
        context_terms |= _content_terms(doc)

    covered = query_terms & context_terms
    return len(covered) / len(query_terms)


def build_documents() -> list[dict]:
    """Adapt get_cve_documents() {id: text} into the retriever's doc shape."""
    return as_search_documents(get_cve_documents())


def main() -> None:
    """Run the offline RAG evaluation over every case and print a report."""
    documents = build_documents()
    doc_by_id = {d["id"]: d["content"] for d in documents}

    if not documents:
        print("No CVE documents available — cannot run RAG metrics.")
        return

    k = 1  # dataset has one relevant CVE per query, so precision@1 is the tightest bar
    engine = create_search_engine("hybrid")

    print("=" * 70)
    print("Offline RAG Metrics (deterministic, no LLM / no Ollama required)")
    print(f"Corpus: {len(documents)} CVE documents | metric cutoff: k={k}")
    print("=" * 70)

    precisions: list[float] = []
    groundedness_scores: list[float] = []

    for case in EVAL_CASES:
        query = case["query"]
        relevant = case["relevant_ids"]

        results = engine.search(query, documents, top_k=max(k, 3))
        retrieved_ids = [r.id for r in results]
        retrieved_texts = [doc_by_id[r.id] for r in results if r.id in doc_by_id]

        p_at_k = precision_at_k(retrieved_ids, relevant, k)
        grounded = groundedness_proxy(query, retrieved_texts)

        precisions.append(p_at_k)
        groundedness_scores.append(grounded)

        print(f'\nQuery: "{query}"')
        print(f"  Expected relevant: {sorted(relevant)}")
        print(f"  Retrieved (ranked): {retrieved_ids}")
        print(f"  precision@{k}:        {p_at_k:.2f}")
        print(f"  groundedness proxy:  {grounded:.2f}  (query terms covered by context)")

    n = len(EVAL_CASES)
    print("\n" + "-" * 70)
    print("Aggregate")
    print(f"  mean precision@{k}:       {sum(precisions) / n:.2f}")
    print(f"  mean groundedness proxy: {sum(groundedness_scores) / n:.2f}")
    print("-" * 70)


if __name__ == "__main__":
    main()

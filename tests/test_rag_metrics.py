"""
Deterministic tests for 06_evals/rag_metrics.py.

Covers the two offline, LLM-free metrics:
- precision_at_k: known 1.0 / 0.0 / partial cases.
- groundedness_proxy: term-overlap coverage and its monotonicity (adding a
  document that covers more query terms can only raise the score, never lower
  it).

The retriever-backed main() is intentionally NOT exercised here: it builds a
hybrid search engine (semantic embeddings would download a model), which the
golden rule excludes. We test only the pure functions.
"""

from conftest import load_module

rag_metrics = load_module("06_evals/rag_metrics.py", "rag_metrics")


# ---------------------------------------------------------------------------
# precision_at_k
# ---------------------------------------------------------------------------
def test_precision_at_k_perfect():
    """Every retrieved doc in the top-k is relevant -> 1.0."""
    retrieved = ["a", "b", "c"]
    relevant = {"a", "b", "c"}
    assert rag_metrics.precision_at_k(retrieved, relevant, k=3) == 1.0


def test_precision_at_k_zero():
    """None of the top-k are relevant -> 0.0."""
    retrieved = ["x", "y", "z"]
    relevant = {"a", "b"}
    assert rag_metrics.precision_at_k(retrieved, relevant, k=3) == 0.0


def test_precision_at_k_partial():
    """Two of three top-k are relevant -> 2/3."""
    retrieved = ["a", "x", "b"]
    relevant = {"a", "b"}
    assert rag_metrics.precision_at_k(retrieved, relevant, k=3) == 2 / 3


def test_precision_at_k_respects_cutoff():
    """Hits below the cutoff k do not count."""
    retrieved = ["x", "y", "a"]  # the only relevant hit is at rank 3
    relevant = {"a"}
    # Only the top-2 are considered, neither is relevant.
    assert rag_metrics.precision_at_k(retrieved, relevant, k=2) == 0.0


def test_precision_at_k_divides_by_k_not_result_count():
    """Standard definition divides by k even if fewer docs were returned."""
    retrieved = ["a"]  # one relevant doc returned
    relevant = {"a"}
    # 1 hit / k=2 = 0.5, not 1.0.
    assert rag_metrics.precision_at_k(retrieved, relevant, k=2) == 0.5


def test_precision_at_k_nonpositive_k_is_zero():
    assert rag_metrics.precision_at_k(["a"], {"a"}, k=0) == 0.0
    assert rag_metrics.precision_at_k(["a"], {"a"}, k=-1) == 0.0


# ---------------------------------------------------------------------------
# groundedness_proxy
# ---------------------------------------------------------------------------
def test_groundedness_proxy_full_coverage():
    """All query content terms appear in the context -> 1.0."""
    query = "buffer overflow remote execution"
    docs = ["a buffer overflow enabling remote code execution in the handler"]
    assert rag_metrics.groundedness_proxy(query, docs) == 1.0


def test_groundedness_proxy_no_coverage():
    """No query content term appears in the context -> 0.0."""
    query = "buffer overflow"
    docs = ["banana bread recipe with sugar and eggs"]
    assert rag_metrics.groundedness_proxy(query, docs) == 0.0


def test_groundedness_proxy_partial_coverage():
    """Half the query's content terms are covered -> 0.5."""
    query = "buffer overflow"  # two content terms
    docs = ["only the buffer is mentioned here"]
    assert rag_metrics.groundedness_proxy(query, docs) == 0.5


def test_groundedness_proxy_monotonic_in_context():
    """
    Adding a document that covers an additional query term can only raise the
    score (monotonic non-decreasing in the retrieved context).
    """
    query = "buffer overflow injection"
    partial = ["mentions buffer only"]
    fuller = ["mentions buffer only", "now also overflow and injection appear"]
    low = rag_metrics.groundedness_proxy(query, partial)
    high = rag_metrics.groundedness_proxy(query, fuller)
    assert high >= low
    assert high == 1.0 and low < 1.0


def test_groundedness_proxy_empty_query_is_zero():
    """A query with only stopwords has no content terms -> 0.0."""
    assert rag_metrics.groundedness_proxy("the and of to", ["anything here"]) == 0.0


def test_groundedness_proxy_ignores_stopwords_and_digits():
    """Stopwords and pure numbers are not content terms."""
    # 'the' is a stopword, '2024' is a pure digit -> neither counts; only
    # 'overflow' is a content term and it is covered.
    assert rag_metrics.groundedness_proxy("the overflow 2024", ["an overflow"]) == 1.0

"""
Cross-Encoder Reranking: The Production Step After Hybrid Search

Hybrid search (BM25 + semantic, fused with RRF) gives a fast, cheap first-stage
ranking. In production you rarely stop there: you take its top-k candidates and
*rerank* them with a cross-encoder — a model that reads the (query, document)
pair jointly and scores true relevance, instead of comparing two independently
produced embeddings. It is slower per pair, which is exactly why it runs only on
the handful of candidates the first stage already narrowed down.

This script shows that two-stage pipeline over the CVE dataset:

    1. First stage: create_search_engine("hybrid").search(...) returns top-k.
    2. Rerank:      a cross-encoder re-scores those same k candidates.
    3. Compare:     the BEFORE (hybrid) and AFTER (reranked) orderings side by
                    side, so you can see the reranker pull the most relevant
                    document up.

To make the effect visible on this tiny CVE corpus, the candidate pool is
seeded with a couple of clearly-labelled "distractor" passages (ids prefixed
`DISTRACTOR-`): keyword-stuffed text that repeats the query's words but carries
no real vulnerability. A lexical first stage is fooled into ranking them high;
the cross-encoder, reading each (query, document) pair jointly, sees they are
empty and demotes them below the real CVE. That is the production failure mode
reranking exists to fix.

Graceful degradation (runs with no network, no heavy dependency):
    If `sentence-transformers` is not installed — or the cross-encoder model
    cannot be loaded (e.g. no network to download it) — the script does NOT
    crash. It falls back to a dependency-free, deterministic reranker that
    scores each candidate by query<->document content-term overlap (the same
    lexical signal used by 06_evals/rag_metrics.py). The fallback is clearly
    labelled in the output so it is never mistaken for the real model.

Reranking is about *retrieval*, not *generation*: no LLM / Ollama is required.

Run from the repository root:

    python -m 04_advanced_workflows.reranking

Optional (real cross-encoder, downloads a small model on first run):

    pip install sentence-transformers
"""


from utils.data_loader import get_cve_documents
from utils.logging import get_logger
from utils.models import SearchResult
from utils.search import create_search_engine
from utils.text import content_terms

logger = get_logger(__name__)

# A lightweight, widely used cross-encoder trained on MS MARCO passage ranking.
CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Query used for the before/after demonstration. The genuinely relevant answer
# is the RCE CVE (CVE-2024-1234).
DEMO_QUERY = "attacker runs arbitrary commands remotely by overflowing the request buffer"

# First stage returns this many candidates; the reranker reorders exactly them.
TOP_K = 10

# Labelled distractor passages added to the candidate pool ALONGSIDE the real
# CVE corpus. They are deliberately keyword-stuffed with the query's own terms
# but carry no real vulnerability context, so a lexical/first-stage ranker is
# fooled into ranking them near the top. A cross-encoder reads each
# (query, document) pair jointly and sees they are empty, demoting them below
# the real CVE — which is exactly the failure mode reranking exists to fix.
# This is the realistic production shape: the first stage hands over a candidate
# set that mixes true hits with keyword-matched near-misses. These are clearly
# marked (ids prefixed "DISTRACTOR-") and never confused with real CVEs.
DISTRACTORS: list[dict] = [
    {
        "id": "DISTRACTOR-keyword-stuffed",
        "content": (
            "remote code execution buffer overflow arbitrary commands request "
            "remote arbitrary commands overflow buffer request remote execution. "
            "This passage only repeats the query's keywords and describes no "
            "actual vulnerability, software, or exploit."
        ),
        "metadata": {"note": "term-overlap decoy, no real content"},
    },
    {
        "id": "DISTRACTOR-off-topic",
        "content": (
            "A tutorial on how to overflow a measuring cup with buffer solution: "
            "run the tap so water commands the brim and arbitrary spillage flows "
            "remotely from the request to fill it. Kitchen chemistry, not security."
        ),
        "metadata": {"note": "lexical overlap, wrong domain"},
    },
]


# ---------------------------------------------------------------------------
# Deterministic, dependency-free fallback reranker
# ---------------------------------------------------------------------------
# Terms with no topical signal — excluded so a document is not judged relevant
# just because stopwords co-occur with the query.
_STOPWORDS: set[str] = {
    "a", "an", "and", "the", "in", "on", "of", "to", "for", "with", "by",
    "is", "are", "be", "at", "or", "from", "into", "that", "this", "it",
}


def _content_terms(text: str) -> set[str]:
    """Content-bearing terms: tokens minus this module's stopwords and pure numbers."""
    return content_terms(text, _STOPWORDS)


def _overlap_score(query: str, document: str) -> float:
    """
    Fraction of the query's content terms present in the document, in [0, 1].

    A deterministic proxy for relevance: it does not understand meaning, but it
    is instant, needs no model, and reproduces exactly across runs — which is
    what makes it a usable stand-in when the cross-encoder is unavailable.
    """
    query_terms = _content_terms(query)
    if not query_terms:
        return 0.0
    doc_terms = _content_terms(document)
    return len(query_terms & doc_terms) / len(query_terms)


# ---------------------------------------------------------------------------
# Reranker selection
# ---------------------------------------------------------------------------
def load_cross_encoder():
    """
    Try to load the real cross-encoder.

    Returns the loaded CrossEncoder instance, or None if sentence-transformers
    is not installed or the model cannot be loaded (e.g. no network). Never
    raises — the caller treats None as "use the deterministic fallback".
    """
    try:
        from sentence_transformers import CrossEncoder
    except ImportError:
        logger.info("sentence-transformers not installed; using fallback reranker.")
        return None

    try:
        return CrossEncoder(CROSS_ENCODER_MODEL)
    except Exception as exc:  # offline, download failure, corrupted cache, ...
        logger.info(f"Could not load cross-encoder model ({exc}); using fallback reranker.")
        return None


def rerank(
    query: str,
    candidates: list[SearchResult],
    cross_encoder,
) -> tuple[list[tuple[SearchResult, float]], bool]:
    """
    Rerank first-stage candidates by relevance to the query.

    Args:
        query: the search query.
        candidates: first-stage (hybrid) results, best-first.
        cross_encoder: a loaded CrossEncoder, or None to use the fallback.

    Returns:
        (ranked, used_cross_encoder) where `ranked` is the candidates paired
        with their rerank score, sorted best-first, and `used_cross_encoder`
        tells which scorer produced the ordering.
    """
    if cross_encoder is not None:
        pairs = [(query, c.content) for c in candidates]
        scores = cross_encoder.predict(pairs)
        scored = [(c, float(s)) for c, s in zip(candidates, scores)]
        used_cross_encoder = True
    else:
        scored = [(c, _overlap_score(query, c.content)) for c in candidates]
        used_cross_encoder = False

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored, used_cross_encoder


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------
def _short(result: SearchResult) -> str:
    """One-line, id-prefixed preview of a result's content."""
    first_line = result.content.strip().splitlines()[0] if result.content.strip() else ""
    return f"{result.id}  {first_line[:60]}"


def print_side_by_side(
    before: list[SearchResult],
    after: list[tuple[SearchResult, float]],
    used_cross_encoder: bool,
) -> None:
    """Print the hybrid ordering next to the reranked ordering."""
    scorer = "cross-encoder" if used_cross_encoder else "fallback (term overlap)"
    print(f"\n{'='*78}")
    print(f"BEFORE (hybrid first stage)        vs.        AFTER (reranked: {scorer})")
    print(f"{'='*78}")

    for rank in range(len(before)):
        b = before[rank]
        a_result, a_score = after[rank]
        moved = "  <= promoted" if a_result.id != b.id else ""
        print(f"{rank + 1:>2}. {b.id:<16}   ->   {a_result.id:<16} "
              f"score={a_score:.4f}{moved}")

    print(f"{'-'*78}")
    top_before = before[0].id if before else "(none)"
    top_after = after[0][0].id if after else "(none)"
    if top_before != top_after:
        print(f"Reranker changed the #1 result: {top_before} -> {top_after}")
    else:
        print(f"Reranker kept the #1 result: {top_after}")
    print(f"{'='*78}")


def main() -> None:
    """Run hybrid search, rerank its top-k, and show the before/after ranking."""
    documents = [
        {"id": cve_id, "content": text, "metadata": {}}
        for cve_id, text in get_cve_documents().items()
    ]

    if not documents:
        print("No CVE documents available — cannot run reranking demo.")
        return

    # Add labelled, keyword-stuffed distractors to the candidate pool so the
    # first stage has realistic near-misses to be fooled by. The real CVEs
    # remain the only genuinely relevant documents.
    documents = documents + DISTRACTORS

    print("=" * 78)
    print("Cross-Encoder Reranking (two-stage retrieval, no LLM required)")
    print(f"Corpus: {len(documents)} documents "
          f"({len(documents) - len(DISTRACTORS)} real CVEs + "
          f"{len(DISTRACTORS)} labelled distractors) | first-stage top_k: {TOP_K}")
    print("=" * 78)
    print(f'\nQuery: "{DEMO_QUERY}"')
    print("Genuinely relevant answer: CVE-2024-1234 (the RCE vulnerability).")

    # Stage 1: hybrid first-stage retrieval.
    engine = create_search_engine("hybrid")
    hybrid_results = engine.search(DEMO_QUERY, documents, top_k=TOP_K)

    if not hybrid_results:
        print("Hybrid search returned no candidates — nothing to rerank.")
        return

    # Stage 2: rerank exactly those candidates.
    cross_encoder = load_cross_encoder()
    reranked, used_cross_encoder = rerank(DEMO_QUERY, hybrid_results, cross_encoder)

    if not used_cross_encoder:
        print("\n[fallback] sentence-transformers / cross-encoder unavailable — "
              "reranking with deterministic query<->document term overlap.")

    print_side_by_side(hybrid_results, reranked, used_cross_encoder)


if __name__ == "__main__":
    main()

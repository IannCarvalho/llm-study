"""
Deterministic tests for 04_advanced_workflows/reranking.py.

Tests ONLY the dependency-free pieces: the term-overlap scorer, content-term
extraction, and the fallback rerank path (cross_encoder=None). The real
cross-encoder is NOT loaded or downloaded here — that is excluded by the golden
rule. We pass cross_encoder=None directly so no network/model is touched.
"""

from conftest import load_module

reranking = load_module("04_advanced_workflows/reranking.py", "reranking")

# SearchResult is the candidate shape rerank() consumes.
from utils.models import SearchResult


# ---------------------------------------------------------------------------
# _overlap_score
# ---------------------------------------------------------------------------
def test_overlap_score_full():
    assert reranking._overlap_score("buffer overflow", "a buffer overflow bug") == 1.0


def test_overlap_score_zero():
    assert reranking._overlap_score("buffer overflow", "banana bread recipe") == 0.0


def test_overlap_score_partial():
    # 'buffer' present, 'overflow' absent -> 1 of 2 content terms.
    assert reranking._overlap_score("buffer overflow", "only the buffer here") == 0.5


def test_overlap_score_empty_query_is_zero():
    # Only stopwords -> no content terms -> 0.0, never a division error.
    assert reranking._overlap_score("the and of", "anything at all") == 0.0


def test_overlap_score_is_deterministic():
    q, d = "remote code execution overflow", "remote overflow in the code path"
    assert reranking._overlap_score(q, d) == reranking._overlap_score(q, d)


# ---------------------------------------------------------------------------
# _content_terms
# ---------------------------------------------------------------------------
def test_content_terms_drops_stopwords_and_digits():
    terms = reranking._content_terms("the buffer overflow in 2024")
    assert "buffer" in terms
    assert "overflow" in terms
    assert "the" not in terms   # stopword
    assert "in" not in terms    # stopword
    assert "2024" not in terms  # pure digit


def test_content_terms_lowercases():
    assert reranking._content_terms("Buffer OVERFLOW") == {"buffer", "overflow"}


# ---------------------------------------------------------------------------
# rerank fallback (cross_encoder=None)
# ---------------------------------------------------------------------------
def _cand(doc_id, content, score=0.5):
    return SearchResult(id=doc_id, content=content, score=score, retrieval_method="hybrid")


def test_rerank_fallback_uses_overlap_and_reports_no_cross_encoder():
    candidates = [
        _cand("REAL", "remote code execution buffer overflow in the request handler"),
        _cand("DECOY", "banana bread kitchen recipe with sugar"),
    ]
    ranked, used_cross_encoder = reranking.rerank(
        "remote code execution buffer overflow", candidates, cross_encoder=None
    )
    assert used_cross_encoder is False
    # The genuinely relevant candidate is promoted to the top.
    assert ranked[0][0].id == "REAL"
    assert ranked[-1][0].id == "DECOY"
    # Scores are the overlap scores, in [0, 1], and sorted descending.
    scores = [s for _c, s in ranked]
    assert scores == sorted(scores, reverse=True)
    assert all(0.0 <= s <= 1.0 for s in scores)


def test_rerank_fallback_preserves_all_candidates():
    candidates = [_cand("A", "alpha overflow"), _cand("B", "beta"), _cand("C", "gamma")]
    ranked, _ = reranking.rerank("overflow", candidates, cross_encoder=None)
    assert {c.id for c, _s in ranked} == {"A", "B", "C"}

"""
Deterministic tests for the shared text helpers in ``utils.text``.

Every keyword-based component (BM25 search, overlap reranker, groundedness
proxy, prompt-leak detector) now uses this single tokenizer, so its behaviour
is pinned here: lowercase ``\\w+`` tokens, exactly what the per-module copies did.
"""

import re

from conftest import load_module

from utils.search import tokenize as search_tokenize
from utils.text import content_terms, tokenize

SAMPLES = [
    "Remote code execution in WebServer v2.1 (CVE-2024-1234)!",
    "SQL injection: bypass the login form; 1 OR 1=1",
    "",
    "ÁCENTOS e números 2024 também viram tokens",
]


def test_tokenize_matches_the_previous_regex_split():
    for text in SAMPLES:
        assert tokenize(text) == re.findall(r"\w+", text.lower())


def test_utils_search_reexports_the_same_tokenizer():
    assert search_tokenize is tokenize


def test_content_terms_drops_stopwords_and_pure_numbers():
    terms = content_terms("The buffer overflow in 2024 and the patch", {"the", "in", "and"})
    assert terms == {"buffer", "overflow", "patch"}


def test_content_terms_without_stopwords_keeps_words():
    assert content_terms("Buffer OVERFLOW 42") == {"buffer", "overflow"}


def test_modules_keep_their_own_stopword_sets():
    # The reranker deliberately drops a few more stopwords than the metrics module.
    rag_metrics = load_module("06_evals/rag_metrics.py", "rag_metrics_text_check")
    text = "this buffer overflow"
    assert rag_metrics._content_terms(text) == {"this", "buffer", "overflow"}
    reranking = load_module("04_advanced_workflows/reranking.py", "reranking_text_check")
    assert reranking._content_terms(text) == {"buffer", "overflow"}

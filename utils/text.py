"""
Text helpers shared by the deterministic (no-LLM) components.

One tokenizer for the whole project keeps every keyword-based piece consistent:
BM25 search (utils.search), the overlap reranker (04), the groundedness proxy
(06), the prompt-leak detector (09) and the BM25 demo (01). Stdlib only, so the
lightweight modules can use it without pulling numpy or sentence-transformers.
"""

import re
from collections.abc import Set as AbstractSet

_WORD_RE = re.compile(r"\w+")


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens (regex ``\\w+``)."""
    return _WORD_RE.findall(text.lower())


def content_terms(text: str, stopwords: AbstractSet[str] = frozenset()) -> set[str]:
    """Content-bearing terms: tokens of ``text`` minus ``stopwords`` and pure numbers."""
    return {t for t in tokenize(text) if t not in stopwords and not t.isdigit()}


__all__ = ["content_terms", "tokenize"]

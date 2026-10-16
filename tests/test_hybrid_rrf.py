"""
Reciprocal Rank Fusion must break exact ties deterministically.

With a small corpus, ties are common: a document ranked (1, 2) by BM25/semantic
and another ranked (2, 1) get exactly the same RRF score. The fusion used to
iterate a ``set`` of ids, so tied documents came out in hash order, which
changes between interpreter runs (PYTHONHASHSEED) -- the "same input, same
result" promise of the deterministic modules did not hold. Ties now keep the
BM25 order, followed by semantic-only hits. No embedding model is loaded here.
"""

import os
import subprocess
import sys
from pathlib import Path

from utils.models import SearchResult
from utils.search import HybridSearch

ROOT = Path(__file__).resolve().parent.parent
PAIRS = 6  # with the old set-based code all pairs come out right only ~1/64 of the time


def _results(ids, method):
    return [
        SearchResult(id=doc_id, content=doc_id, score=0.5, metadata={}, retrieval_method=method)
        for doc_id in ids
    ]


def _tied_rankings():
    """BM25 ranks each pair (a, b); semantic ranks it (b, a): every pair ties under RRF."""
    bm25, semantic = [], []
    for k in range(PAIRS):
        a, b = f"doc-{k}a", f"doc-{k}b"
        bm25 += [a, b]
        semantic += [b, a]
    return bm25, semantic


def test_rrf_ties_keep_the_bm25_order():
    bm25, semantic = _tied_rankings()
    fused = HybridSearch()._reciprocal_rank_fusion(_results(bm25, "bm25"), _results(semantic, "semantic"))
    assert [r.id for r in fused] == bm25


def test_rrf_semantic_only_hits_come_after_tied_bm25_hits():
    fused = HybridSearch()._reciprocal_rank_fusion(
        _results(["x", "y"], "bm25"), _results(["y", "x", "z"], "semantic")
    )
    assert [r.id for r in fused] == ["x", "y", "z"]


def test_rrf_order_is_identical_across_hash_seeds():
    code = (
        "from tests.test_hybrid_rrf import _results, _tied_rankings\n"
        "from utils.search import HybridSearch\n"
        "bm25, sem = _tied_rankings()\n"
        "fused = HybridSearch()._reciprocal_rank_fusion(_results(bm25, 'bm25'), _results(sem, 'semantic'))\n"
        "print(','.join(r.id for r in fused))\n"
    )
    outputs = set()
    for seed in ("1", "2"):
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            env=dict(os.environ, PYTHONPATH=str(ROOT), PYTHONHASHSEED=seed),
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert proc.returncode == 0, proc.stderr
        outputs.add(proc.stdout.strip())
    assert len(outputs) == 1

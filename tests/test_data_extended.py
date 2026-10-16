"""
Deterministic tests for the extended CVE dataset and its retrieval evaluation.

Two groups, both offline (no network, no model download):

1. Dataset integrity — ``utils/data/cves_extended.json`` has unique ids, every
   record uses valid ``SeverityLevel`` / ``VulnerabilityType`` enum values and a
   schema-valid ``CVEData``, and the first three records are byte-for-byte the
   same objects as ``utils/data/cves.json`` (the default dataset must not drift).

2. Metrics on a real retriever — the bm25 engine (``create_search_engine('bm25')``)
   runs over the extended corpus. BM25 needs no embedding model, so this stays
   offline; the semantic/hybrid engines are intentionally NOT exercised here
   (they would download a model), exactly as the existing test_rag_metrics.py
   does. recall@k, precision@k and MRR are checked on known cases.
"""

import json
from pathlib import Path

from conftest import load_module

from utils.data_loader import load_cves_from
from utils.models import CVEData, SeverityLevel, VulnerabilityType

rag_ext = load_module("06_evals/rag_metrics_extended.py", "rag_metrics_extended")

ROOT = Path(__file__).resolve().parent.parent
BASE_PATH = ROOT / "utils" / "data" / "cves.json"
EXTENDED_PATH = ROOT / "utils" / "data" / "cves_extended.json"


def _load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Dataset integrity
# ---------------------------------------------------------------------------
def test_extended_dataset_exists():
    assert EXTENDED_PATH.exists(), f"missing {EXTENDED_PATH}"


def test_extended_has_originals_plus_synthetic():
    """3 originals + at least 30 synthetic records (brief asks for 30-40)."""
    records = _load_json(EXTENDED_PATH)
    assert len(records) >= 33
    synthetic = len(records) - 3
    assert 30 <= synthetic <= 40, f"expected 30-40 synthetic, got {synthetic}"


def test_first_three_identical_to_default_dataset():
    """The extended set must embed the 3 originals unchanged."""
    base = _load_json(BASE_PATH)
    ext = _load_json(EXTENDED_PATH)
    assert len(base) == 3
    assert ext[:3] == base


def test_extended_ids_are_unique():
    records = _load_json(EXTENDED_PATH)
    ids = [r["id"] for r in records]
    assert len(ids) == len(set(ids))


def test_synthetic_ids_use_future_year_format():
    """Synthetic records use the CVE-2099-NNNN marker; originals keep 2024."""
    records = _load_json(EXTENDED_PATH)
    synthetic = records[3:]
    assert synthetic, "no synthetic records found"
    for r in synthetic:
        assert r["id"].startswith("CVE-2099-"), r["id"]


def test_extended_enums_are_valid():
    """Every record uses a valid severity and vulnerability_type enum value."""
    valid_sev = {e.value for e in SeverityLevel}
    valid_type = {e.value for e in VulnerabilityType}
    for r in _load_json(EXTENDED_PATH):
        assert r["severity"] in valid_sev, r["id"]
        assert r["vulnerability_type"] in valid_type, r["id"]


def test_extended_records_are_schema_valid():
    """Each record constructs a CVEData (score bounds, non-empty desc, etc.)."""
    for r in _load_json(EXTENDED_PATH):
        cve = CVEData(
            id=r["id"],
            severity=SeverityLevel(r["severity"]),
            score=r["score"],
            description=r["description"],
            affected_versions=r["affected_versions"],
            cvss_vector=r["cvss_vector"],
            metadata={},
        )
        assert 0.0 <= cve.score <= 10.0


def test_score_matches_severity_band():
    """Scores are coherent with the severity label (CVSS v3.1 bands)."""
    bands = {
        "CRITICAL": (9.0, 10.0),
        "HIGH": (7.0, 8.9),
        "MEDIUM": (4.0, 6.9),
        "LOW": (0.1, 3.9),
        "INFO": (0.0, 0.0),
    }
    for r in _load_json(EXTENDED_PATH):
        lo, hi = bands[r["severity"]]
        assert lo <= r["score"] <= hi, f"{r['id']}: {r['severity']} score {r['score']}"


def test_all_enum_values_represented():
    """The synthetic set spreads across every vulnerability type and severity."""
    records = _load_json(EXTENDED_PATH)
    types = {r["vulnerability_type"] for r in records}
    sevs = {r["severity"] for r in records}
    assert types == {e.value for e in VulnerabilityType}
    assert sevs == {e.value for e in SeverityLevel}


def test_load_cves_from_reads_extended():
    """load_cves_from parses the extended file into CVEData instances."""
    cves = load_cves_from(EXTENDED_PATH)
    assert len(cves) == len(_load_json(EXTENDED_PATH))
    assert all(isinstance(c, CVEData) for c in cves)


def test_load_cves_from_missing_file_returns_empty():
    """Mirrors load_cves: a missing file yields [] rather than raising."""
    assert load_cves_from(ROOT / "utils" / "data" / "does_not_exist.json") == []


# ---------------------------------------------------------------------------
# Pure metric helpers defined in the extended eval
# ---------------------------------------------------------------------------
def test_recall_at_k_known_cases():
    # one of two relevant retrieved in top-k -> 0.5
    assert rag_ext.recall_at_k(["a", "x"], {"a", "b"}, k=2) == 0.5
    # both relevant retrieved -> 1.0
    assert rag_ext.recall_at_k(["a", "b"], {"a", "b"}, k=2) == 1.0
    # none retrieved -> 0.0
    assert rag_ext.recall_at_k(["x", "y"], {"a"}, k=2) == 0.0
    # empty relevant set -> 0.0 (no division by zero)
    assert rag_ext.recall_at_k(["a"], set(), k=1) == 0.0


def test_reciprocal_rank_known_cases():
    assert rag_ext.reciprocal_rank(["a", "b", "c"], {"a"}) == 1.0
    assert rag_ext.reciprocal_rank(["x", "a", "c"], {"a"}) == 0.5
    assert rag_ext.reciprocal_rank(["x", "y", "a"], {"a"}) == 1 / 3
    assert rag_ext.reciprocal_rank(["x", "y", "z"], {"a"}) == 0.0


# ---------------------------------------------------------------------------
# Metrics over a real retriever — bm25 only (no model, no network)
# ---------------------------------------------------------------------------
def test_bm25_evaluation_runs_offline():
    """evaluate_method('bm25', ...) returns the three metrics in [0,1]."""
    documents = rag_ext.build_documents()
    assert documents, "extended documents should be available"
    scores = rag_ext.evaluate_method("bm25", documents, k=3)
    assert scores is not None
    for key in ("precision", "recall", "mrr"):
        assert 0.0 <= scores[key] <= 1.0


def test_bm25_retrieves_exact_id_term():
    """BM25 ranks the document whose id is quoted in the query at the top."""
    documents = rag_ext.build_documents()
    from utils.search import create_search_engine

    engine = create_search_engine("bm25")
    results = engine.search("CVE-2099-0001 proxy buffer overflow", documents, top_k=3)
    assert results, "bm25 returned no results"
    assert results[0].id == "CVE-2099-0001"


def test_build_documents_have_no_injected_keywords():
    """
    The extended eval uses RAW documents: unlike get_cve_documents(), the
    content must not carry a 'Keywords:' line.
    """
    for doc in rag_ext.build_documents():
        assert "Keywords:" not in doc["content"]

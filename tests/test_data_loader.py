"""
Deterministic tests for the keyword enrichment in ``utils.data_loader``.

``get_cve_documents()`` appends a synthetic keyword block per vulnerability
class (document expansion for BM25). The block must follow the record's typed
``vulnerability_type``: the old description-substring test matched "rce" inside
"source" and "force" and gave the cryptographic CVE the RCE keywords.
"""

from utils.data_loader import _KEYWORDS_BY_TYPE, get_cve_documents, load_cves

EXPECTED_TYPES = {
    "CVE-2024-1234": "rce",
    "CVE-2024-5678": "sql_injection",
    "CVE-2024-9012": "crypto",
}


def _keywords(document: str) -> str:
    for line in document.splitlines():
        if line.startswith("Keywords: "):
            return line[len("Keywords: "):]
    return ""


def test_dataset_types_are_the_ones_these_tests_assume():
    types = {cve.id: cve.metadata["vulnerability_type"] for cve in load_cves()}
    assert types == EXPECTED_TYPES


def test_keywords_follow_the_records_vulnerability_type():
    docs = get_cve_documents()
    for cve_id, vuln_type in EXPECTED_TYPES.items():
        assert _keywords(docs[cve_id]) == _KEYWORDS_BY_TYPE[vuln_type]


def test_crypto_record_no_longer_gets_rce_keywords():
    keywords = _keywords(get_cve_documents()["CVE-2024-9012"])
    assert "remote code execution" not in keywords
    assert keywords.startswith("cryptographic weakness")


def test_enrich_keywords_false_returns_the_raw_records():
    raw = get_cve_documents(enrich_keywords=False)
    enriched = get_cve_documents()

    assert set(raw) == set(enriched)
    for cve in load_cves():
        assert "Keywords:" not in raw[cve.id]
        assert cve.description in raw[cve.id]
        assert enriched[cve.id].startswith(raw[cve.id])

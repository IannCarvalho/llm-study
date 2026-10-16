"""
Tests for the demo fixtures in ``utils.agentic_utils``.

- ``get_cve_documents`` is a plain re-export of ``utils.data_loader``'s function
  (no wrapper that would hide its parameters).
- ``get_cve_qa_examples()`` builds one CVE-grounded Q&A pair per record, with
  the expected answer keyword derived from the record's ``vulnerability_type``.
"""

from utils import agentic_utils, data_loader


def test_get_cve_documents_is_the_data_loader_function():
    assert agentic_utils.get_cve_documents is data_loader.get_cve_documents


def test_qa_examples_are_grounded_in_the_cve_base():
    cves = data_loader.load_cves()
    examples = agentic_utils.get_cve_qa_examples()

    assert len(examples) == len(cves)
    for cve, example in zip(cves, examples, strict=True):
        assert cve.description in example["question"]
        assert example["expected"]


def test_qa_expected_keyword_follows_the_vulnerability_type():
    expected = {
        cve.id: example["expected"]
        for cve, example in zip(data_loader.load_cves(), agentic_utils.get_cve_qa_examples(), strict=True)
    }
    assert expected == {
        "CVE-2024-1234": "remote code execution",
        "CVE-2024-5678": "sql injection",
        "CVE-2024-9012": "cryptographic",
    }

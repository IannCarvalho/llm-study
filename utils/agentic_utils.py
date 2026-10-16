"""Demo fixtures shared by the examples.

Despite the name, this module holds no agent logic: it keeps the small inputs
the demos share, so they compare *strategies* on the same data.

- ``QUERY`` / ``CVE_ID``: the example question and CVE used by 02, 03 and 04.
- ``SAMPLE_DOCUMENTS``: free-form prose for the chunking demo (01).
- ``get_cve_qa_examples()``: CVE-grounded Q&A pairs for the observability
  demos (05).
- ``get_cve_documents``: re-exported from ``utils.data_loader`` (its canonical
  home) so existing ``from utils.agentic_utils import get_cve_documents``
  imports keep working.
"""

from utils.data_loader import get_cve_documents, load_cves

# Example queries for demonstrations
QUERY = "What is CVE-2024-1234?"
CVE_ID = "CVE-2024-1234"

# Keyword an answer must mention to be scored as correct, per vulnerability_type.
_EXPECTED_CLASS = {
    "rce": "remote code execution",
    "sql_injection": "sql injection",
    "crypto": "cryptographic",
    "xss": "cross-site scripting",
    "csrf": "cross-site request forgery",
    "auth_bypass": "authentication bypass",
}


def get_cve_qa_examples() -> list[dict[str, str]]:
    """
    One Q&A pair per CVE of the base, for the observability demos.

    The question carries the CVE description: the CVEs are synthetic, so no
    model knows them, and the answer has to come from the given text. The
    ``expected`` keyword is what the Langfuse accuracy evaluator looks for.
    """
    examples = []
    for cve in load_cves():
        vuln_type = cve.metadata.get("vulnerability_type", "other")
        examples.append(
            {
                "question": (
                    f"{cve.description}\n\n"
                    "Which class of vulnerability does the CVE described above belong to?"
                ),
                "expected": _EXPECTED_CLASS.get(vuln_type, vuln_type.replace("_", " ")),
            }
        )
    return examples


SAMPLE_DOCUMENTS = {
    "security": """SQL injection is a web attack that occurs when an attacker inserts
malicious SQL statements into an entry field. This allows the attacker to 
execute arbitrary SQL code on the database. For example, an attacker might 
type: 1 OR 1=1 in a login form to bypass authentication.

The impact is severe: data theft, unauthorized access, or complete database
destruction. To prevent SQL injection, always use parameterized queries and
input validation. Never concatenate user input directly into SQL strings.

XSS attacks are different. They involve injecting malicious scripts that
execute in the victim's browser. This can steal cookies, redirect users,
or modify page content. The defense is to escape HTML and use Content
Security Policy headers.""",
}

__all__ = ["CVE_ID", "QUERY", "SAMPLE_DOCUMENTS", "get_cve_documents", "get_cve_qa_examples"]

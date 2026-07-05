"""Agentic utilities - CVE data and example data"""

from utils.data_loader import get_cve_documents as _get_cve_documents


def get_cve_documents() -> dict[str, str]:
    """Get CVEs formatted as documents for indexing."""
    return _get_cve_documents()


# Example queries for demonstrations
QUERY = "What is CVE-2024-1234?"
CVE_ID = "CVE-2024-1234"

# Example data for demonstrations
SHARED_EXAMPLES = [
    {"question": "What is Python?", "expected": "programming language"},
    {"question": "What is the capital of Brazil?", "expected": "Brasilia"},
    {"question": "What is machine learning?", "expected": "algorithms"},
]

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

"""
Data Loading - Centralized data access with caching

Loads JSON data files and caches them for performance.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from functools import lru_cache
from utils.models import CVEData, SeverityLevel
from utils.logging import get_logger

logger = get_logger(__name__)

DATA_DIR = Path(__file__).parent / "data"


@lru_cache(maxsize=1)
def load_cves() -> List[CVEData]:
    """
    Load CVE data from JSON file.
    
    Returns:
        List of CVEData instances
    """
    cve_file = DATA_DIR / "cves.json"
    
    if not cve_file.exists():
        logger.warning(f"CVE data file not found: {cve_file}")
        return []
    
    try:
        with open(cve_file, 'r') as f:
            data = json.load(f)
        
        cves = [
            CVEData(
                id=item["id"],
                severity=SeverityLevel(item["severity"]),
                score=item["score"],
                description=item["description"],
                affected_versions=item.get("affected_versions", []),
                cvss_vector=item["cvss_vector"],
                metadata={"vulnerability_type": item.get("vulnerability_type", "other")}
            )
            for item in data
        ]
        
        return cves
    
    except Exception as e:
        logger.error(f"Failed to load CVEs: {e}")
        return []


def get_cve_by_id(cve_id: str) -> Optional[CVEData]:
    """
    Get a single CVE by ID.
    
    Args:
        cve_id: CVE identifier
    
    Returns:
        CVEData instance or None if not found
    """
    cves = load_cves()
    return next((cve for cve in cves if cve.id == cve_id), None)


def search_cves(query: str) -> List[CVEData]:
    """
    Search CVEs by query string (substring matching).
    
    Args:
        query: Search query
    
    Returns:
        List of matching CVEs
    """
    cves = load_cves()
    query_lower = query.lower()
    
    return [
        cve for cve in cves
        if query_lower in cve.id.lower() or query_lower in cve.description.lower()
    ]


# Synthetic keywords appended to each document ("document expansion") so BM25
# gets a strong lexical signal per vulnerability class. This is a didactic
# shortcut, not real data -- pass enrich_keywords=False for the raw record text.
# The block is chosen by the record's typed `vulnerability_type` (cves.json),
# never by substrings of the description: a substring test for "rce" also
# matches "source" and "force", which gave the crypto CVE the RCE keywords.
_KEYWORDS_BY_TYPE: Dict[str, str] = {
    "sql_injection": (
        "SQL injection SQL injection SQL injection database attack "
        "SQL query injection SQL injection vulnerability "
        "SQL injection malicious SQL input SQL injection security"
    ),
    "rce": (
        "remote code execution remote code execution remote code execution "
        "RCE command injection vulnerability attack "
        "remote execution command injection vulnerability"
    ),
    "xss": (
        "cross-site scripting XSS vulnerability attack payload injection "
        "cross-site scripting XSS attack browser payload"
    ),
    "csrf": (
        "cross-site request forgery CSRF attack session token "
        "CSRF vulnerability session hijacking"
    ),
    "auth_bypass": (
        "authentication bypass authentication bypass login weakness "
        "credential bruteforce authentication vulnerability"
    ),
    "crypto": (
        "cryptographic weakness encryption vulnerability key generation "
        "random number generator weak randomness encryption vulnerability"
    ),
}


def get_cve_documents(enrich_keywords: bool = True) -> Dict[str, str]:
    """
    Get CVEs formatted as documents for vector database indexing.

    Args:
        enrich_keywords: append the synthetic keyword block for the record's
            ``vulnerability_type`` (see ``_KEYWORDS_BY_TYPE``). True (default)
            keeps the documents every module was built on; False returns the
            raw record text, e.g. to compare retrievers without the boost.

    Returns:
        Dict of {cve_id: formatted_text}
    """
    cves = load_cves()
    docs = {}

    for cve in cves:
        doc = (
            f"CVE ID: {cve.id}\n"
            f"Severity: {cve.severity.value}\n"
            f"CVSS Score: {cve.score}\n"
            f"Affected Versions: {', '.join(cve.affected_versions)}\n"
            f"Description: {cve.description}\n"
        )

        keywords = _KEYWORDS_BY_TYPE.get(cve.metadata.get("vulnerability_type", ""), "")
        if enrich_keywords and keywords:
            doc += f"Keywords: {keywords}\n"

        docs[cve.id] = doc

    return docs


def reset_cache():
    """Clear data loading cache (useful for testing)."""
    load_cves.cache_clear()
    logger.info("Data loading cache cleared")


__all__ = [
    "load_cves",
    "get_cve_by_id",
    "search_cves",
    "get_cve_documents",
    "reset_cache",
]

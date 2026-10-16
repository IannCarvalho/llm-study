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


def get_cve_documents() -> Dict[str, str]:
    """
    Get CVEs formatted as documents for vector database indexing.
    
    Returns:
        Dict of {cve_id: formatted_text}
    """
    cves = load_cves()
    docs = {}
    
    for cve in cves:
        # Build document with context and repeated keywords for BM25 signal
        keywords = ""
        desc_lower = cve.description.lower()
        
        if 'sql' in desc_lower or 'injection' in desc_lower:
            keywords = ("SQL injection SQL injection SQL injection database attack "
                       "SQL query injection SQL injection vulnerability "
                       "SQL injection malicious SQL input SQL injection security")
        elif 'code execution' in desc_lower or 'rce' in desc_lower:
            keywords = ("remote code execution remote code execution remote code execution "
                       "RCE command injection vulnerability attack "
                       "remote execution command injection vulnerability")
        elif 'xss' in desc_lower:
            keywords = ("cross-site scripting XSS vulnerability attack payload injection "
                       "cross-site scripting XSS attack browser payload")
        elif 'csrf' in desc_lower:
            keywords = ("cross-site request forgery CSRF attack session token "
                       "CSRF vulnerability session hijacking")
        elif 'authentication' in desc_lower or 'auth' in desc_lower:
            keywords = ("authentication bypass authentication bypass login weakness "
                       "credential bruteforce authentication vulnerability")
        elif 'crypto' in desc_lower or 'encrypt' in desc_lower:
            keywords = ("cryptographic weakness encryption vulnerability key generation "
                       "random number generator weak randomness encryption vulnerability")
        
        doc = (
            f"CVE ID: {cve.id}\n"
            f"Severity: {cve.severity.value}\n"
            f"CVSS Score: {cve.score}\n"
            f"Affected Versions: {', '.join(cve.affected_versions)}\n"
            f"Description: {cve.description}\n"
        )
        
        if keywords:
            doc += f"Keywords: {keywords}\n"
        
        docs[cve.id] = doc
    
    return docs


def reset_cache():
    """Clear data loading cache (useful for testing)."""
    load_cves.cache_clear()
    logger.info("Data loading cache cleared")


def load_cves_from(path: str | Path) -> List[CVEData]:
    """
    Load CVE data from an arbitrary JSON file (opt-in alternative dataset).

    Mirrors :func:`load_cves` exactly, including the ``CVEData`` construction,
    but reads from the caller-supplied ``path`` instead of the fixed
    ``cves.json`` and is not cached (so switching datasets needs no cache
    reset). Intended for the extended synthetic dataset
    (``utils/data/cves_extended.json``) used by retrieval evaluations; it does
    not change the default dataset or any behaviour that relies on it.

    Args:
        path: Path to a JSON file in the same schema as ``cves.json``.

    Returns:
        List of CVEData instances (empty list if the file is missing or
        cannot be parsed, matching ``load_cves``).
    """
    cve_file = Path(path)

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
        logger.error(f"Failed to load CVEs from {cve_file}: {e}")
        return []


__all__ = [
    "load_cves",
    "load_cves_from",
    "get_cve_by_id",
    "search_cves",
    "get_cve_documents",
    "reset_cache",
]

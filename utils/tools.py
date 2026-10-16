"""
Shared tool definitions.

Add new tools here so every agent pattern (tool_use, react, langgraph)
reuses the same implementation instead of redefining it.
"""

from langchain_core.tools import tool

from utils.data_loader import get_cve_by_id


@tool
def search_cve(cve_id: str) -> dict:
    """Look up details about a CVE by its ID, e.g. CVE-2024-12345."""
    cve = get_cve_by_id(cve_id)
    if cve:
        return {
            "status": "success",
            "data": {
                "id": cve.id,
                "severity": cve.severity.value,
                "score": cve.score,
                "description": cve.description,
                "affected_versions": cve.affected_versions,
            }
        }
    return {"status": "not_found", "message": f"CVE not found: {cve_id}"}


TOOLS = [search_cve]
TOOL_REGISTRY = {t.name: t for t in TOOLS}
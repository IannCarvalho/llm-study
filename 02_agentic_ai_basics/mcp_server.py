"""
Minimal MCP (Model Context Protocol) server over the CVE knowledge base.

Why this exists
---------------
An MCP server exposes *tools*, *resources* and *prompts* to any MCP host (an
agent, an IDE, a chat app) through one standardized, transport-agnostic
interface. Instead of each agent re-inventing how it talks to our CVE data, we
describe the capability once -- a named tool with a typed signature and a
docstring -- and every MCP-aware client can discover and call it.

This module keeps the *logic* (the handlers) completely independent of the SDK
so it is importable and testable with only the CI dependencies. The MCP SDK
(package ``mcp``, class ``MCPServer``) is imported lazily inside
:func:`build_server`, so importing this file never requires ``mcp`` to be
installed.

The underlying CVE lookup/search logic is reused from :mod:`utils.data_loader`
(``get_cve_by_id`` / ``search_cves``). We deliberately do NOT import
``utils.tools`` -- it decorates its functions with LangChain's ``@tool`` and
``langchain_core`` is not part of the CI environment.

Run it as a stdio server from the repository root::

    python -m 02_agentic_ai_basics.mcp_server

Nothing runs on import.
"""

from __future__ import annotations

import re
from typing import Any

from utils.data_loader import get_cve_by_id, search_cves

# A CVE id looks like ``CVE-2021-44228`` (year then a sequence number). We accept
# it case-insensitively and tolerate surrounding whitespace in the handler.
_CVE_ID_PATTERN = re.compile(r"^CVE-\d{4}-\d{4,}$", re.IGNORECASE)


class CVENotFoundError(Exception):
    """Raised when a requested CVE id is well-formed but absent from the data."""


class InvalidCVEIdError(ValueError):
    """Raised when a CVE id does not match the ``CVE-YYYY-NNNN`` shape."""


# ---------------------------------------------------------------------------
# Pure handlers -- no MCP SDK involved, so they are trivially unit-testable.
# ---------------------------------------------------------------------------
def _cve_to_dict(cve: Any) -> dict[str, Any]:
    """Serialize a :class:`utils.models.CVEData` into a JSON-friendly dict."""
    return {
        "id": cve.id,
        "severity": cve.severity.value,
        "score": cve.score,
        "description": cve.description,
        "affected_versions": list(cve.affected_versions),
        "cvss_vector": cve.cvss_vector,
    }


def lookup_cve(cve_id: str) -> dict[str, Any]:
    """
    Look up a single CVE by its identifier.

    Args:
        cve_id: A CVE identifier such as ``"CVE-2021-44228"`` (case-insensitive,
            surrounding whitespace is ignored).

    Returns:
        A JSON-serializable dict describing the CVE.

    Raises:
        InvalidCVEIdError: The id is empty or not shaped like ``CVE-YYYY-NNNN``.
        CVENotFoundError: The id is well-formed but no such CVE exists.
    """
    if not cve_id or not cve_id.strip():
        raise InvalidCVEIdError("CVE id must not be empty.")

    normalized = cve_id.strip().upper()
    if not _CVE_ID_PATTERN.match(normalized):
        raise InvalidCVEIdError(
            f"Malformed CVE id {cve_id!r}; expected the form 'CVE-YYYY-NNNN' "
            "(e.g. 'CVE-2021-44228')."
        )

    cve = get_cve_by_id(normalized)
    if cve is None:
        raise CVENotFoundError(
            f"No CVE found with id {normalized!r}. Use the 'search_cves' tool to "
            "discover available identifiers."
        )
    return _cve_to_dict(cve)


def search_cves_tool(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    Search CVEs by a free-text query (substring match on id and description).

    Args:
        query: Non-empty search text, e.g. ``"sql injection"``.
        limit: Maximum number of results to return (1-100).

    Returns:
        A list of JSON-serializable CVE dicts (possibly empty).

    Raises:
        ValueError: The query is empty/blank or ``limit`` is out of range.
    """
    if not query or not query.strip():
        raise ValueError("Search query must not be empty.")
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100.")

    matches = search_cves(query.strip())
    return [_cve_to_dict(cve) for cve in matches[:limit]]


# ---------------------------------------------------------------------------
# MCP wiring -- the SDK is imported lazily so importing this module (and the
# tests) never requires the ``mcp`` package.
# ---------------------------------------------------------------------------
def build_server() -> Any:
    """
    Build and return an :class:`mcp.server.MCPServer` exposing the CVE tools.

    The ``mcp`` package is imported here (not at module load) so that the pure
    handlers above remain usable in the CI environment, where ``mcp`` is not
    installed. The registered callables are thin adapters that translate our
    domain exceptions into the SDK's ``ToolError``; the MCP SDK reports a
    ``ToolError`` back to the client as a clean tool error carrying its message
    (an arbitrary exception would instead be masked as an opaque internal error).

    Returns:
        A configured ``MCPServer`` instance (not yet running).
    """
    from mcp.server import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError

    server = MCPServer(
        name="cve-knowledge-base",
        instructions=(
            "Tools over a local CVE (vulnerability) knowledge base. Use "
            "'lookup_cve' when you already know the exact CVE id, and "
            "'search_cves' to find ids by keyword."
        ),
    )

    @server.tool(
        name="lookup_cve",
        description="Look up one CVE by its exact id (e.g. 'CVE-2021-44228').",
    )
    def lookup_cve_tool(cve_id: str) -> dict[str, Any]:
        """Return the full record for a single CVE id."""
        try:
            return lookup_cve(cve_id)
        except (InvalidCVEIdError, CVENotFoundError) as exc:
            # Surface a clean, actionable message to the calling agent.
            raise ToolError(str(exc)) from exc

    @server.tool(
        name="search_cves",
        description="Search CVEs by keyword; returns a list of matching records.",
    )
    def search_tool(query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Return CVEs whose id or description contains ``query``."""
        try:
            return search_cves_tool(query, limit)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

    @server.resource(
        "cve://{cve_id}",
        name="cve",
        description="A single CVE record addressed by id, e.g. cve://CVE-2021-44228.",
        mime_type="application/json",
    )
    def cve_resource(cve_id: str) -> dict[str, Any]:
        """Expose a CVE as a readable resource under the ``cve://`` scheme."""
        try:
            return lookup_cve(cve_id)
        except (InvalidCVEIdError, CVENotFoundError) as exc:
            raise ToolError(str(exc)) from exc

    return server


def main() -> None:
    """Build the server and serve it over stdio (the default MCP transport)."""
    server = build_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()

"""
Deterministic tests for 02_agentic_ai_basics/mcp_server.py.

Two layers, split by dependency:

* The pure handlers (``lookup_cve``, ``search_cves_tool``) are exercised
  directly -- they need only the CI dependencies, no MCP SDK, no network, no
  LLM. They read the repo's own ``utils/data/cves.json`` through
  ``utils.data_loader``.
* The ``build_server`` wiring needs the ``mcp`` package, which is NOT in the CI
  dependency set, so those tests are guarded with
  ``pytest.importorskip("mcp")`` and are skipped where ``mcp`` is absent.
"""

import pytest
from conftest import load_module

mcp_server = load_module("02_agentic_ai_basics/mcp_server.py", "mcp_server")

# Known-good fixtures sourced from the repo's bundled CVE data.
KNOWN_ID = "CVE-2024-1234"
SQL_ID = "CVE-2024-5678"


# ---------------------------------------------------------------------------
# lookup_cve -- pure handler
# ---------------------------------------------------------------------------
def test_lookup_cve_returns_dict_for_known_id():
    result = mcp_server.lookup_cve(KNOWN_ID)
    assert result["id"] == KNOWN_ID
    assert result["severity"] == "CRITICAL"
    assert isinstance(result["affected_versions"], list)
    assert set(result) == {
        "id",
        "severity",
        "score",
        "description",
        "affected_versions",
        "cvss_vector",
    }


def test_lookup_cve_is_case_insensitive_and_trims():
    result = mcp_server.lookup_cve("  cve-2024-1234  ")
    assert result["id"] == KNOWN_ID


def test_lookup_cve_empty_id_raises_invalid():
    with pytest.raises(mcp_server.InvalidCVEIdError):
        mcp_server.lookup_cve("   ")


def test_lookup_cve_malformed_id_raises_invalid():
    with pytest.raises(mcp_server.InvalidCVEIdError) as exc:
        mcp_server.lookup_cve("not-a-cve")
    assert "CVE-YYYY-NNNN" in str(exc.value)


def test_lookup_cve_missing_id_raises_not_found():
    with pytest.raises(mcp_server.CVENotFoundError) as exc:
        mcp_server.lookup_cve("CVE-0000-0000")
    assert "CVE-0000-0000" in str(exc.value)


# ---------------------------------------------------------------------------
# search_cves_tool -- pure handler
# ---------------------------------------------------------------------------
def test_search_cves_tool_finds_sql_injection():
    results = mcp_server.search_cves_tool("sql injection")
    ids = {row["id"] for row in results}
    assert SQL_ID in ids


def test_search_cves_tool_returns_list_of_dicts():
    results = mcp_server.search_cves_tool("vulnerability")
    assert isinstance(results, list)
    assert all(isinstance(row, dict) and "id" in row for row in results)


def test_search_cves_tool_respects_limit():
    results = mcp_server.search_cves_tool("vulnerability", limit=1)
    assert len(results) <= 1


def test_search_cves_tool_empty_query_raises():
    with pytest.raises(ValueError):
        mcp_server.search_cves_tool("   ")


def test_search_cves_tool_bad_limit_raises():
    with pytest.raises(ValueError):
        mcp_server.search_cves_tool("sql", limit=0)
    with pytest.raises(ValueError):
        mcp_server.search_cves_tool("sql", limit=101)


def test_search_cves_tool_no_match_returns_empty():
    assert mcp_server.search_cves_tool("zzz-no-such-term-zzz") == []


# ---------------------------------------------------------------------------
# build_server -- needs the MCP SDK, skipped where ``mcp`` is unavailable.
# ---------------------------------------------------------------------------
def test_build_server_registers_tools():
    pytest.importorskip("mcp")
    server = mcp_server.build_server()
    # The server exposes a name and the two tools we registered.
    assert server.name == "cve-knowledge-base"


def test_build_server_lists_expected_tools():
    pytest.importorskip("mcp")
    import asyncio

    server = mcp_server.build_server()
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    assert {"lookup_cve", "search_cves"} <= names

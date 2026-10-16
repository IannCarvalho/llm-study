"""
Minimal MCP client demo: launch the CVE server over stdio and drive it.

This script uses the official ``mcp`` SDK (:class:`mcp.Client`) to spawn
``mcp_server.py`` as a stdio subprocess, discover its tools, call them, and read
the templated ``cve://{id}`` resource -- exactly what any MCP host does when it
connects to a server.

Run it from the repository root::

    python -m 02_agentic_ai_basics.mcp_client_demo

Requires the ``mcp`` package (``pip install mcp``) in the active environment;
the server subprocess is launched with the *same* interpreter running this
client (``sys.executable``), so it inherits this environment.

Nothing runs on import.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any


def _text_of(result: Any) -> str:
    """Flatten an MCP tool/resource result into readable text for the demo."""
    parts: list[str] = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(text)
    return "\n".join(parts) if parts else repr(getattr(result, "content", result))


async def run_demo() -> None:
    """Connect to the CVE MCP server over stdio and exercise its tools."""
    from mcp import Client, StdioServerParameters

    # Launch the server with the SAME interpreter running this client, as a
    # module from the repository root, so its ``from utils...`` imports resolve.
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "02_agentic_ai_basics.mcp_server"],
    )

    async with Client(params) as client:
        # 1. Discover the tools the server advertises.
        tools = await client.list_tools()
        print("=== Tools advertised by the server ===")
        for tool in tools.tools:
            print(f"- {tool.name}: {tool.description}")

        # 2. Call the search tool.
        print("\n=== call search_cves(query='sql injection') ===")
        search_result = await client.call_tool(
            "search_cves", {"query": "sql injection", "limit": 3}
        )
        print(_text_of(search_result))

        # 3. Look up a specific id (reuse the first search hit if any).
        structured = getattr(search_result, "structured_content", None)
        first_id = None
        if isinstance(structured, dict):
            rows = structured.get("result") or structured.get("results")
            if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                first_id = rows[0].get("id")

        if first_id:
            print(f"\n=== call lookup_cve(cve_id='{first_id}') ===")
            lookup_result = await client.call_tool("lookup_cve", {"cve_id": first_id})
            print(_text_of(lookup_result))

            # 4. Read the same CVE through the cve:// resource.
            print(f"\n=== read_resource('cve://{first_id}') ===")
            resource_result = await client.read_resource(f"cve://{first_id}")
            for block in resource_result.contents:
                print(getattr(block, "text", repr(block)))

        # 5. Show the informative error path for a missing id.
        print("\n=== call lookup_cve(cve_id='CVE-0000-0000') (expected error) ===")
        error_result = await client.call_tool(
            "lookup_cve", {"cve_id": "CVE-0000-0000"}
        )
        print("is_error:", getattr(error_result, "is_error", None))
        print(_text_of(error_result))


def main() -> None:
    """Entry point: run the asyncio demo."""
    asyncio.run(run_demo())


if __name__ == "__main__":
    main()

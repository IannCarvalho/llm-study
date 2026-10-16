"""
LangGraph: Conditional Routing

Builds on langgraph_basics.py by adding conditional branching.
The graph takes different paths based on state values, instead of
always following the same pipeline.

Concepts:
- Conditional routing: add_conditional_edges() branches based on state
- Multiple paths: different nodes can be reached depending on logic
- Same task (CVE search), but with decision logic built into the graph

Compare with basics: linear pipeline vs graph with branches.
"""

from typing import TypedDict

from langgraph.graph import END, StateGraph

from utils.agentic_utils import CVE_ID
from utils.llm_client import get_llm_client
from utils.tools import TOOL_REGISTRY


class CVEState(TypedDict):
    """Shared state object passed through the graph."""
    cve_id: str
    cve_data: dict
    summary: str


def fetch_cve(state: CVEState) -> CVEState:
    """Node: Fetch CVE data from tool."""
    print("\nNode: fetch_cve")
    result = TOOL_REGISTRY["search_cve"].invoke(state["cve_id"])
    state["cve_data"] = result
    print(f"  Result: {result['status']}")
    return state


def route_by_status(state: CVEState) -> str:
    """
    Router function: Decide which path to take based on CVE lookup result.
    
    Returns: "summarize" if found, "not_found" if not.
    """
    if state["cve_data"]["status"] == "success":
        print("\nRouting -> summarize (CVE found)")
        return "summarize"
    else:
        print("\nRouting -> not_found (CVE missing)")
        return "not_found"


def summarize(state: CVEState) -> CVEState:
    """Node: Summarize the CVE in plain language."""
    print("\nNode: summarize")
    llm = get_llm_client(temperature=0.3)
    prompt = f"Summarize this CVE in one sentence: {state['cve_data']['data']}"
    state["summary"] = llm.generate(prompt, max_tokens=256)
    print(f"  Summary: {state['summary']}")
    return state


def not_found(state: CVEState) -> CVEState:
    """Node: Handle CVE not found case."""
    print("\nNode: not_found")
    state["summary"] = f"No data available for {state['cve_id']}."
    print(f"  Summary: {state['summary']}")
    return state


def build_graph():
    """Build and compile the conditional graph."""
    graph = StateGraph(CVEState)
    
    # Add nodes
    graph.add_node("fetch_cve", fetch_cve)
    graph.add_node("summarize", summarize)
    graph.add_node("not_found", not_found)
    
    # Set entry point
    graph.set_entry_point("fetch_cve")
    
    # Conditional routing: decide next node based on state
    graph.add_conditional_edges(
        "fetch_cve",
        route_by_status,
        {
            "summarize": "summarize",
            "not_found": "not_found"
        }
    )
    
    # All paths lead to END
    graph.add_edge("summarize", END)
    graph.add_edge("not_found", END)
    
    return graph.compile()


def main() -> None:
    print("=" * 70)
    print("LangGraph: Conditional Routing")
    print("=" * 70)

    app = build_graph()

    # Test 1: CVE found
    print("\n--- Case 1: CVE Found ---")
    result1 = app.invoke({
        "cve_id": CVE_ID,
        "cve_data": {},
        "summary": ""
    })
    print(f"\nFinal: {result1['summary']}")

    # Test 2: CVE not found
    print("\n\n--- Case 2: CVE Not Found ---")
    result2 = app.invoke({
        "cve_id": "CVE-9999-99999",
        "cve_data": {},
        "summary": ""
    })
    print(f"\nFinal: {result2['summary']}")


if __name__ == "__main__":
    main()

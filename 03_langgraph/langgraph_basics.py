"""
LangGraph Basics: State + Nodes + Edges (Linear Pipeline)

The simplest possible graph: a fixed pipeline where each node
transforms a shared state object, one step at a time.

Concepts:
- State: TypedDict passed through the graph
- Nodes: Functions that transform state
- Edges: Define execution order (no branching yet)

Compare with 01_agentic_ai_basics/: same CVE search task,
different execution strategy. Here: explicit state machine.
"""

from typing import TypedDict
from langgraph.graph import StateGraph, END
from utils.llm_client import get_llm_client
from utils.tools import TOOL_REGISTRY
from utils.agentic_utils import CVE_ID


class CVEState(TypedDict):
    """Shared state object passed through the graph."""
    cve_id: str
    cve_data: dict
    summary: str


def fetch_cve(state: CVEState) -> CVEState:
    """Node 1: Fetch CVE data from tool."""
    print("\nNode: fetch_cve")
    result = TOOL_REGISTRY["search_cve"].invoke(state["cve_id"])
    state["cve_data"] = result
    print(f"  Result: {result['status']}")
    return state


def summarize(state: CVEState) -> CVEState:
    """Node 2: Summarize the CVE in plain language."""
    print("\nNode: summarize")
    llm = get_llm_client(temperature=0.3)
    
    if state["cve_data"]["status"] == "success":
        prompt = f"Summarize this CVE in one sentence: {state['cve_data']['data']}"
    else:
        prompt = f"The CVE {state['cve_id']} was not found."
    
    state["summary"] = llm.generate(prompt, max_tokens=256)
    print(f"  Summary: {state['summary']}")
    return state


def build_graph():
    """Build and compile the linear pipeline."""
    graph = StateGraph(CVEState)
    
    # Add nodes
    graph.add_node("fetch_cve", fetch_cve)
    graph.add_node("summarize", summarize)
    
    # Set entry point
    graph.set_entry_point("fetch_cve")
    
    # Define edges (linear: fetch -> summarize -> END)
    graph.add_edge("fetch_cve", "summarize")
    graph.add_edge("summarize", END)
    
    return graph.compile()


def main() -> None:
    print("=" * 70)
    print("LangGraph Basics: Linear Pipeline")
    print("=" * 70)

    app = build_graph()
    result = app.invoke({
        "cve_id": CVE_ID,
        "cve_data": {},
        "summary": ""
    })

    print("\n" + "=" * 70)
    print("Final State:")
    print(f"  CVE ID: {result['cve_id']}")
    print(f"  Summary: {result['summary']}")
    print("=" * 70)


if __name__ == "__main__":
    main()

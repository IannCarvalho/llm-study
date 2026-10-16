"""
LangGraph: Multi-Agent (Supervisor + Handoff)

Builds on langgraph_basics.py (linear pipeline) and langgraph_conditional.py
(one branch point). Here a central SUPERVISOR node repeatedly decides which
specialist agent runs next, until the work is done. This is the "supervisor"
multi-agent architecture: specialized workers coordinated by a router that
controls the flow.

Three specialist agents work the CVE base:
- triage:  classify severity and pick the CVE id to work on
- retrieve: pull the CVE record (the "recovery" / lookup specialist)
- report:   draft the final analyst report

The supervisor routes triage -> retrieve -> report -> END, but the decision is
re-made from STATE on every hop (a handoff), so a failed lookup is routed
straight to report instead of pretending to have data.

Design constraints (so the routing logic is testable in CI without langgraph):
- All routing is in PURE functions (pick_cve_id, supervisor_decide, the agent
  node bodies) that take/return plain dicts and never import langgraph.
- langgraph is imported LAZILY inside build_graph(), so importing this module
  (as the tests do) never requires langgraph to be installed.
- The whole pipeline runs deterministically offline: no Ollama, no network, no
  key. An optional LLM polish step degrades with a clear message when the LLM
  stack is unavailable (repo pattern, see 12_agentic_rag/agentic_rag.py).

Compare with 08_agentic_platforms: "subagents / orchestration" there is the
same idea at the platform level — delegate independent work and consolidate —
whereas here the orchestration is an explicit in-process state machine.
"""

from typing import TypedDict

from utils.data_loader import get_cve_by_id, search_cves
from utils.models import CVEData, SeverityLevel

# Supervisor routing targets. END is a sentinel string here so the pure routing
# logic needs no langgraph import; build_graph() maps it to langgraph's END.
AGENTS = ("triage", "retrieve", "report")

# CVSS base-score thresholds (FIRST.org CVSS v3.1 qualitative mapping).
_SEVERITY_FLOOR: dict[SeverityLevel, float] = {
    SeverityLevel.CRITICAL: 9.0,
    SeverityLevel.HIGH: 7.0,
    SeverityLevel.MEDIUM: 4.0,
    SeverityLevel.LOW: 0.1,
    SeverityLevel.INFO: 0.0,
}


class MultiAgentState(TypedDict):
    """Shared state passed between the supervisor and its specialist agents."""
    request: str          # the user's natural-language ask
    cve_id: str           # id the triage agent decided to work on ("" if none)
    cve_data: dict        # record pulled by the retrieve agent ({} if missing)
    severity_note: str    # triage agent's severity classification
    report: str           # report agent's final text
    visited: list[str]    # agents already run (keeps the supervisor terminating)


# ---------------------------------------------------------------------------
# Pure helpers (no langgraph, no LLM) — unit-testable in isolation
# ---------------------------------------------------------------------------
# Words too common to be useful search keywords when no CVE id is given.
_STOPWORDS = frozenset(
    {
        "the", "a", "an", "is", "are", "was", "were", "what", "which", "who",
        "whom", "that", "this", "these", "those", "and", "or", "of", "to", "in",
        "on", "for", "with", "about", "most", "more", "serious", "severe",
        "worst", "any", "there", "issue", "issues", "problem", "problems",
        "vulnerability", "vulnerabilities", "cve", "cves", "tell", "me", "show",
        "find", "list", "give", "please", "investigate", "triage", "write",
        "up", "it", "do", "does", "how", "why", "can", "could", "should",
    }
)


def pick_cve_id(request: str) -> str:
    """
    Extract a CVE id from the request, or fall back to the highest-scoring CVE
    whose record matches a significant keyword from the request. Returns ""
    when nothing matches.

    Pure and deterministic: this is the triage agent's routing input. The
    keyword fallback lets natural-language asks ("the most serious SQL
    injection issue") resolve, since search_cves does substring matching and
    the full sentence is never a substring of a CVE record.
    """
    for token in request.replace(",", " ").split():
        cleaned = token.strip(".;:()[]").upper()
        if cleaned.startswith("CVE-"):
            return cleaned

    matches: dict[str, CVEData] = {}
    for raw in request.lower().replace(",", " ").split():
        word = raw.strip(".;:()[]?!\"'")
        if len(word) < 3 or word in _STOPWORDS:
            continue
        for cve in search_cves(word):
            matches[cve.id] = cve

    if not matches:
        return ""
    best = max(matches.values(), key=lambda cve: cve.score)
    return best.id


def classify_severity(score: float) -> SeverityLevel:
    """Map a CVSS base score to its qualitative severity band (pure)."""
    for level in (
        SeverityLevel.CRITICAL,
        SeverityLevel.HIGH,
        SeverityLevel.MEDIUM,
        SeverityLevel.LOW,
    ):
        if score >= _SEVERITY_FLOOR[level]:
            return level
    return SeverityLevel.INFO


def supervisor_decide(state: MultiAgentState) -> str:
    """
    The supervisor's routing rule: given the current state, name the next agent
    (or "report" to finish). Pure function — this is what the graph branches on.

    Flow: triage -> retrieve -> report -> END, but a failed lookup skips
    straight to report so the pipeline never summarizes missing data.
    """
    visited = state.get("visited", [])

    if "triage" not in visited:
        return "triage"

    # No CVE could be identified at triage: nothing to retrieve, go report.
    if not state.get("cve_id"):
        return "report"

    if "retrieve" not in visited:
        return "retrieve"

    return "report"


# ---------------------------------------------------------------------------
# Specialist agent nodes (pure dict -> dict; printing is didactic narration)
# ---------------------------------------------------------------------------
def triage_agent(state: MultiAgentState) -> MultiAgentState:
    """Specialist 1: decide which CVE to work on and note its severity band."""
    print("\n[triage] classifying request")
    cve_id = pick_cve_id(state["request"])
    state["cve_id"] = cve_id
    state.setdefault("visited", []).append("triage")

    if not cve_id:
        state["severity_note"] = "No CVE identified from the request."
        print("  -> no CVE matched")
        return state

    cve = get_cve_by_id(cve_id)
    if cve is None:
        state["severity_note"] = f"{cve_id} is not in the knowledge base."
        print(f"  -> {cve_id} selected (not in base)")
        return state

    band = classify_severity(cve.score)
    state["severity_note"] = f"{cve_id} scores {cve.score} -> {band.value}."
    print(f"  -> {cve_id} selected ({band.value})")
    return state


def retrieve_agent(state: MultiAgentState) -> MultiAgentState:
    """Specialist 2: pull the full CVE record for the triaged id."""
    print("\n[retrieve] looking up CVE record")
    state.setdefault("visited", []).append("retrieve")

    cve = get_cve_by_id(state["cve_id"])
    if cve is None:
        state["cve_data"] = {}
        print("  -> not found")
        return state

    state["cve_data"] = _cve_to_dict(cve)
    print(f"  -> found {cve.id}")
    return state


def report_agent(state: MultiAgentState) -> MultiAgentState:
    """Specialist 3: draft the analyst report from whatever state we have."""
    print("\n[report] drafting report")
    state.setdefault("visited", []).append("report")
    state["report"] = _compose_report(state)
    print("  -> report ready")
    return state


# ---------------------------------------------------------------------------
# Report composition — deterministic baseline + optional LLM polish
# ---------------------------------------------------------------------------
def _cve_to_dict(cve: CVEData) -> dict:
    """Flatten a CVEData into the plain dict carried in state."""
    return {
        "id": cve.id,
        "severity": cve.severity.value,
        "score": cve.score,
        "description": cve.description,
        "affected_versions": list(cve.affected_versions),
        "cvss_vector": cve.cvss_vector,
    }


def deterministic_report(state: MultiAgentState) -> str:
    """Build the grounded report with no LLM (always available, pure)."""
    if not state.get("cve_id"):
        return (
            "No CVE could be identified from the request "
            f"'{state['request']}'. Nothing to report."
        )

    data = state.get("cve_data") or {}
    if not data:
        return (
            f"{state['cve_id']} was requested but is not present in the CVE "
            f"base. {state.get('severity_note', '')}".strip()
        )

    versions = ", ".join(data["affected_versions"]) or "n/a"
    return (
        f"CVE {data['id']} — severity {data['severity']} "
        f"(CVSS {data['score']}).\n"
        f"Triage: {state.get('severity_note', '').strip()}\n"
        f"Affected versions: {versions}.\n"
        f"Vector: {data['cvss_vector']}.\n"
        f"Summary: {data['description']}"
    )


def _compose_report(state: MultiAgentState) -> str:
    """
    Return the deterministic report, optionally rewritten by an LLM.

    The LLM stack is OPTIONAL: imported lazily, and ANY failure (Ollama down,
    missing dependency, no key, timeout) degrades to the deterministic baseline
    with a clear note — the repo's offline-first contract.
    """
    facts = deterministic_report(state)
    if not state.get("cve_data"):
        return facts  # nothing worth spending an LLM call on

    try:
        from utils.llm_client import get_llm_client  # lazy: LLM stack optional

        client = get_llm_client(temperature=0.3)
        prompt = (
            "You are a security analyst. Rewrite the CVE briefing below as one "
            "tight paragraph for an incident ticket. Keep every number and the "
            "CVE id exactly.\n\n"
            f"{facts}\n\nRewritten:"
        )
        polished = client.generate(prompt, max_tokens=256)
        if polished and polished.strip():
            return polished.strip()
    except Exception as exc:  # Ollama down, missing dep/key, timeout, etc.
        print(
            f"  (LLM unavailable: {exc.__class__.__name__}; "
            "using deterministic report)"
        )

    return facts


# ---------------------------------------------------------------------------
# Graph assembly (langgraph imported HERE, not at module top)
# ---------------------------------------------------------------------------
def build_graph():
    """
    Build and compile the supervisor graph.

    langgraph is imported inside this function on purpose: importing this
    module (as the deterministic tests do) must not require langgraph. Only
    actually building/running the graph needs it.
    """
    from langgraph.graph import END, StateGraph

    graph = StateGraph(MultiAgentState)

    graph.add_node("triage", triage_agent)
    graph.add_node("retrieve", retrieve_agent)
    graph.add_node("report", report_agent)

    graph.set_entry_point("triage")

    # The supervisor's decision is re-evaluated after each specialist via
    # conditional edges keyed on the pure supervisor_decide() rule.
    route_map = {"triage": "triage", "retrieve": "retrieve", "report": "report"}
    graph.add_conditional_edges("triage", supervisor_decide, route_map)
    graph.add_conditional_edges("retrieve", supervisor_decide, route_map)
    graph.add_edge("report", END)

    return graph.compile()


def initial_state(request: str) -> MultiAgentState:
    """A fresh state for a request (helper for callers and tests)."""
    return {
        "request": request,
        "cve_id": "",
        "cve_data": {},
        "severity_note": "",
        "report": "",
        "visited": [],
    }


def main() -> None:
    print("=" * 70)
    print("LangGraph: Multi-Agent (Supervisor + Handoff)")
    print("=" * 70)

    app = build_graph()

    demo_requests = [
        "Triage CVE-2024-1234 and write it up.",
        "What is the most serious SQL injection issue?",
        "Investigate CVE-0000-0000.",  # not in base -> handoff skips retrieve
    ]

    for request in demo_requests:
        print("\n" + "-" * 70)
        print(f"Request: {request}")
        result = app.invoke(initial_state(request))
        print("\nFinal report:")
        print(result["report"])
        print(f"Agents run: {' -> '.join(result['visited'])}")


if __name__ == "__main__":
    main()

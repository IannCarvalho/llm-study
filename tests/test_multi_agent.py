"""
Deterministic tests for 03_langgraph/langgraph_multi_agent.py.

Two layers, mirroring the module's design:

1. The routing logic is pure (pick_cve_id, classify_severity, supervisor_decide
   and the agent node bodies take/return plain dicts and never import
   langgraph). Those tests run in CI with no langgraph installed — the module
   is loaded via conftest.load_module, whose build_graph() langgraph import is
   never triggered.

2. Graph assembly/execution needs langgraph, so those tests are guarded with
   pytest.importorskip("langgraph") and are skipped when it is absent.

No network, no LLM, no model download: the optional LLM polish step in
report_agent is never reached because the deterministic baseline is returned
whenever cve_data is empty, and the graph tests assert on the grounded report.
"""

import pytest
from conftest import load_module

multi = load_module("03_langgraph/langgraph_multi_agent.py", "langgraph_multi_agent")

from utils.models import SeverityLevel


# ---------------------------------------------------------------------------
# pick_cve_id — triage's routing input
# ---------------------------------------------------------------------------
def test_pick_cve_id_extracts_explicit_id():
    assert multi.pick_cve_id("Please triage CVE-2024-1234 now.") == "CVE-2024-1234"


def test_pick_cve_id_strips_trailing_punctuation():
    assert multi.pick_cve_id("look at (CVE-2024-5678).") == "CVE-2024-5678"


def test_pick_cve_id_falls_back_to_best_match():
    # No explicit id: keyword search resolves to the SQL-injection CVE.
    assert multi.pick_cve_id("the most serious SQL injection issue?") == "CVE-2024-5678"


def test_pick_cve_id_returns_empty_when_nothing_matches():
    assert multi.pick_cve_id("tell me a joke about penguins") == ""


# ---------------------------------------------------------------------------
# classify_severity — CVSS band mapping
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "score,expected",
    [
        (9.8, SeverityLevel.CRITICAL),
        (9.0, SeverityLevel.CRITICAL),
        (8.2, SeverityLevel.HIGH),
        (7.0, SeverityLevel.HIGH),
        (6.5, SeverityLevel.MEDIUM),
        (4.0, SeverityLevel.MEDIUM),
        (1.0, SeverityLevel.LOW),
        (0.0, SeverityLevel.INFO),
    ],
)
def test_classify_severity_bands(score, expected):
    assert multi.classify_severity(score) == expected


# ---------------------------------------------------------------------------
# supervisor_decide — the routing rule
# ---------------------------------------------------------------------------
def test_supervisor_starts_with_triage():
    state = multi.initial_state("anything")
    assert multi.supervisor_decide(state) == "triage"


def test_supervisor_goes_to_retrieve_after_triage_with_cve():
    state = multi.initial_state("x")
    state["visited"] = ["triage"]
    state["cve_id"] = "CVE-2024-1234"
    assert multi.supervisor_decide(state) == "retrieve"


def test_supervisor_skips_retrieve_when_no_cve():
    # Handoff: a failed triage routes straight to report, not retrieve.
    state = multi.initial_state("x")
    state["visited"] = ["triage"]
    state["cve_id"] = ""
    assert multi.supervisor_decide(state) == "report"


def test_supervisor_finishes_after_retrieve():
    state = multi.initial_state("x")
    state["visited"] = ["triage", "retrieve"]
    state["cve_id"] = "CVE-2024-1234"
    assert multi.supervisor_decide(state) == "report"


# ---------------------------------------------------------------------------
# Agent node bodies — pure state transforms
# ---------------------------------------------------------------------------
def test_triage_agent_sets_cve_and_severity():
    state = multi.triage_agent(multi.initial_state("triage CVE-2024-1234"))
    assert state["cve_id"] == "CVE-2024-1234"
    assert "CRITICAL" in state["severity_note"]
    assert "triage" in state["visited"]


def test_retrieve_agent_fills_cve_data():
    state = multi.initial_state("x")
    state["cve_id"] = "CVE-2024-5678"
    state = multi.retrieve_agent(state)
    assert state["cve_data"]["id"] == "CVE-2024-5678"
    assert state["cve_data"]["severity"] == "HIGH"
    assert "retrieve" in state["visited"]


def test_retrieve_agent_empty_for_unknown_cve():
    state = multi.initial_state("x")
    state["cve_id"] = "CVE-0000-0000"
    state = multi.retrieve_agent(state)
    assert state["cve_data"] == {}


# ---------------------------------------------------------------------------
# Report composition — deterministic, no LLM reached
# ---------------------------------------------------------------------------
def test_deterministic_report_includes_facts():
    state = multi.initial_state("triage CVE-2024-1234")
    state = multi.triage_agent(state)
    state = multi.retrieve_agent(state)
    report = multi.deterministic_report(state)
    assert "CVE-2024-1234" in report
    assert "9.8" in report
    assert "CRITICAL" in report


def test_deterministic_report_handles_no_cve():
    state = multi.initial_state("hello")
    state = multi.triage_agent(state)
    report = multi.deterministic_report(state)
    assert "No CVE" in report


def test_deterministic_report_handles_missing_cve():
    state = multi.initial_state("look at CVE-0000-0000")
    state = multi.triage_agent(state)
    state = multi.retrieve_agent(state)
    report = multi.deterministic_report(state)
    assert "CVE-0000-0000" in report
    assert "not present" in report


# ---------------------------------------------------------------------------
# Graph assembly / execution — needs langgraph
# ---------------------------------------------------------------------------
def test_graph_runs_full_pipeline_for_known_cve():
    pytest.importorskip("langgraph")
    app = multi.build_graph()
    result = app.invoke(multi.initial_state("triage CVE-2024-1234 and write it up"))
    assert result["visited"] == ["triage", "retrieve", "report"]
    assert "CVE-2024-1234" in result["report"]


def test_graph_skips_retrieve_when_no_cve():
    pytest.importorskip("langgraph")
    app = multi.build_graph()
    result = app.invoke(multi.initial_state("tell me a joke about penguins"))
    # Handoff path: triage -> report, retrieve never runs.
    assert "retrieve" not in result["visited"]
    assert result["visited"][0] == "triage"
    assert result["visited"][-1] == "report"

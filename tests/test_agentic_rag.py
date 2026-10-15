"""
Deterministic tests for 12_agentic_rag/agentic_rag.py.

The planner/controller decisions are pure rules (no LLM). run_agentic_retrieval
normally builds a hybrid search engine, whose semantic half would download an
embedding model — excluded by the golden rule. We therefore inject a STUB search
engine via monkeypatch, so the agentic loop's real decision logic (plan ->
search per iteration -> accumulate -> comparison sweep) is exercised with no
network and no model download. The final LLM generation step is never called.
"""

from conftest import load_module

agentic = load_module("12_agentic_rag/agentic_rag.py", "agentic_rag")

from utils.models import SearchResult


# ---------------------------------------------------------------------------
# needs_retrieval
# ---------------------------------------------------------------------------
def test_needs_retrieval_false_for_greeting():
    assert agentic.needs_retrieval("hello there, how are you?") is False


def test_needs_retrieval_true_for_cve_id():
    assert agentic.needs_retrieval("tell me about CVE-2024-1234") is True


def test_needs_retrieval_true_for_topic_cue():
    assert agentic.needs_retrieval("is there an RCE vulnerability?") is True


# ---------------------------------------------------------------------------
# wants_comparison
# ---------------------------------------------------------------------------
def test_wants_comparison_true_for_most_severe():
    assert agentic.wants_comparison("which is the most severe CVE?") is True


def test_wants_comparison_true_for_portuguese_cue():
    assert agentic.wants_comparison("qual e mais severo?") is True


def test_wants_comparison_false_for_plain_question():
    assert agentic.wants_comparison("what is a SQL injection?") is False


# ---------------------------------------------------------------------------
# plan_sub_queries
# ---------------------------------------------------------------------------
def test_plan_decomposes_compound_query():
    subs = agentic.plan_sub_queries("RCE in the request handler and a SQL injection")
    # Distinct topic cues -> distinct sub-queries (de-duplicated, order-preserving).
    assert len(subs) >= 2
    assert any("code execution" in s for s in subs)
    assert any("SQL injection" in s for s in subs)


def test_plan_falls_back_to_raw_query_when_no_cue():
    subs = agentic.plan_sub_queries("general overview please")
    assert subs == ["general overview please"]


def test_plan_dedupes_sub_queries():
    subs = agentic.plan_sub_queries("rce and remote code execution")
    assert len(subs) == len(set(subs))


# ---------------------------------------------------------------------------
# AgentState accumulation / ranking
# ---------------------------------------------------------------------------
def test_agent_state_keeps_best_score_and_ranks():
    st = agentic.AgentState(query="q")
    st.add_result("A", "content a", 0.1)
    st.add_result("A", "content a", 0.9)  # better score replaces
    st.add_result("B", "content b", 0.5)
    assert st.evidence["A"].score == 0.9
    ranked = st.ranked_evidence()
    assert [d.id for d in ranked] == ["A", "B"]  # descending by score


# ---------------------------------------------------------------------------
# run_agentic_retrieval with a STUB engine (no model download)
# ---------------------------------------------------------------------------
class _StubEngine:
    """Records queries and returns a fixed hit, so no embedding model loads."""

    def __init__(self):
        self.queries = []

    def search(self, query, documents, top_k=3):
        self.queries.append(query)
        return [
            SearchResult(
                id="CVE-2024-1234",
                content="remote code execution via buffer overflow in request handler",
                score=0.9,
                retrieval_method="hybrid",
            )
        ]


def test_run_agentic_retrieval_accumulates_evidence(monkeypatch):
    stub = _StubEngine()
    monkeypatch.setattr(agentic, "create_search_engine", lambda method="hybrid", **k: stub)

    docs = [{"id": "CVE-2024-1234", "content": "rce buffer overflow", "metadata": {}}]
    state = agentic.run_agentic_retrieval(
        "Which RCE CVEs affect request handlers, and which is most severe?", docs
    )

    assert isinstance(state, agentic.AgentState)
    # The loop actually ran searches and gathered evidence.
    assert len(state.sub_queries_run) >= 1
    assert "CVE-2024-1234" in state.evidence
    ranked = state.ranked_evidence()
    assert ranked and ranked[0].id == "CVE-2024-1234"
    # A comparison question added a severity sweep as an extra planned pass.
    assert any("severity" in q.lower() or "severe" in q.lower() for q in stub.queries)


def test_run_agentic_retrieval_skips_retrieval_for_greeting(monkeypatch):
    stub = _StubEngine()
    monkeypatch.setattr(agentic, "create_search_engine", lambda method="hybrid", **k: stub)

    docs = [{"id": "CVE-2024-1234", "content": "rce", "metadata": {}}]
    state = agentic.run_agentic_retrieval("hello", docs)

    assert state.evidence == {}
    assert state.sub_queries_run == []
    # No search was issued at all.
    assert stub.queries == []


def test_run_agentic_retrieval_ranked_evidence_is_sorted(monkeypatch):
    class _MultiEngine:
        def search(self, query, documents, top_k=3):
            return [
                SearchResult(id="LOW", content="x", score=0.2, retrieval_method="hybrid"),
                SearchResult(id="HIGH", content="y", score=0.8, retrieval_method="hybrid"),
            ]

    monkeypatch.setattr(agentic, "create_search_engine", lambda method="hybrid", **k: _MultiEngine())
    docs = [{"id": "LOW", "content": "x", "metadata": {}}]
    state = agentic.run_agentic_retrieval("is there an RCE vulnerability?", docs)
    ranked = state.ranked_evidence()
    scores = [d.score for d in ranked]
    assert scores == sorted(scores, reverse=True)
    assert ranked[0].id == "HIGH"

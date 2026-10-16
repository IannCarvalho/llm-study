"""
Deterministic tests for 06_evals/agent_evals.py.

Two layers, both offline (no network, no model download, no LLM):

1. The pure metric functions (task_success, search_precision_recall,
   estimate_context_tokens, count_redundant_calls) are exercised directly on
   hand-built inputs — no agent involved.

2. The end-to-end path (run_evaluation -> evaluate_task -> module-12 agent) is
   exercised with a STUB search engine injected via monkeypatch, exactly as
   tests/test_agentic_rag.py does. agent_evals imports agentic_rag and the agent
   calls create_search_engine from ITS OWN module namespace, so the patch target
   is agent_evals.agentic_rag.create_search_engine. This drives the real planner
   / controller / trajectory logic while the "hybrid" engine (whose semantic
   half would download an embedding model) never loads.
"""

from conftest import load_module

agent_evals = load_module("06_evals/agent_evals.py", "agent_evals")

from utils.models import SearchResult


# ===========================================================================
# Pure metric: task_success
# ===========================================================================
def test_task_success_true_when_all_expected_retrieved():
    assert agent_evals.task_success({"A", "B", "C"}, {"A", "B"}) is True


def test_task_success_true_on_exact_match():
    assert agent_evals.task_success({"A"}, {"A"}) is True


def test_task_success_false_when_one_expected_missing():
    # Recovered two of three required ids -> task is NOT complete.
    assert agent_evals.task_success({"A", "B"}, {"A", "B", "C"}) is False


# ===========================================================================
# Pure metric: search_precision_recall
# ===========================================================================
def test_precision_recall_perfect_plan():
    # Two issued searches, each covering a distinct reference cue.
    issued = [{"sql injection"}, {"authentication"}]
    precision, recall = agent_evals.search_precision_recall(
        issued, ("sql injection", "authentication")
    )
    assert precision == 1.0
    assert recall == 1.0


def test_precision_penalizes_off_plan_search():
    # Three issued searches; one covers no reference cue -> precision 2/3.
    issued = [{"sql injection"}, {"authentication"}, set()]
    precision, recall = agent_evals.search_precision_recall(
        issued, ("sql injection", "authentication")
    )
    assert round(precision, 2) == 0.67
    assert recall == 1.0


def test_recall_penalizes_uncovered_cue():
    # Only one of two reference cues is covered by any issued search.
    issued = [{"sql injection"}]
    precision, recall = agent_evals.search_precision_recall(
        issued, ("sql injection", "authentication")
    )
    assert precision == 1.0
    assert recall == 0.5


def test_precision_recall_no_searches_but_cues_expected():
    precision, recall = agent_evals.search_precision_recall([], ("sql injection",))
    assert precision == 0.0
    assert recall == 0.0


def test_precision_recall_no_searches_and_nothing_expected():
    # Vacuous case: no plan, no searches -> both perfect.
    precision, recall = agent_evals.search_precision_recall([], ())
    assert precision == 1.0
    assert recall == 1.0


# ===========================================================================
# Pure metric: estimate_context_tokens
# ===========================================================================
def test_estimate_context_tokens_is_bytes_over_four():
    # 8 ASCII bytes // 4 == 2.
    assert agent_evals.estimate_context_tokens("abcdefgh") == 2


def test_estimate_context_tokens_sums_blocks():
    # "abcd" (4) + "efgh" (4) = 8 bytes // 4 == 2.
    assert agent_evals.estimate_context_tokens("abcd", "efgh") == 2


def test_estimate_context_tokens_empty_is_zero():
    assert agent_evals.estimate_context_tokens("", "") == 0


# ===========================================================================
# Pure metric: count_redundant_calls
# ===========================================================================
def test_count_redundant_calls_flags_repeat_hits():
    # Step 1 finds A,B (new). Step 2 finds A (already seen) -> redundant.
    steps = [["A", "B"], ["A"]]
    assert agent_evals.count_redundant_calls(steps) == 1


def test_count_redundant_calls_zero_when_each_step_adds_new():
    steps = [["A"], ["B"], ["C"]]
    assert agent_evals.count_redundant_calls(steps) == 0


def test_count_redundant_calls_empty_step_is_redundant():
    # A search that returned nothing added nothing -> redundant.
    steps = [["A"], []]
    assert agent_evals.count_redundant_calls(steps) == 1


# ===========================================================================
# End-to-end over a STUB engine (no model download)
# ===========================================================================
class _StubEngine:
    """
    Returns a fixed hit per search, recording the queries issued. No embedding
    model loads, so the suite stays offline. The fixed hit is CVE-2024-5678 so
    the SQL-injection task's expected id is actually recovered.
    """

    def __init__(self):
        self.queries: list[str] = []

    def search(self, query, documents, top_k=3):
        self.queries.append(query)
        return [
            SearchResult(
                id="CVE-2024-5678",
                content="sql injection authentication bypass login database",
                score=0.9,
                retrieval_method="hybrid",
            )
        ]


def _patch_stub(monkeypatch) -> _StubEngine:
    stub = _StubEngine()
    monkeypatch.setattr(
        agent_evals.agentic_rag,
        "create_search_engine",
        lambda method="hybrid", **k: stub,
    )
    return stub


def test_evaluate_task_runs_agent_and_reports(monkeypatch):
    _patch_stub(monkeypatch)
    task = agent_evals.AgentTask(
        name="t",
        query="Is there a SQL injection vulnerability that bypasses authentication?",
        expected_ids=frozenset({"CVE-2024-5678"}),
        expected_sub_queries=2,
        reference_cues=("sql injection", "authentication"),
    )
    docs = [{"id": "CVE-2024-5678", "content": "sql injection", "metadata": {}}]
    report = agent_evals.evaluate_task(task, docs)

    assert isinstance(report, agent_evals.TaskReport)
    # The stub always returns the expected id, so the task succeeds.
    assert report.success is True
    assert "CVE-2024-5678" in report.retrieved_ids
    # The agent issued at least one search (trajectory has length).
    assert report.steps >= 1
    # Context estimate is a non-negative integer (bytes/4 proxy).
    assert isinstance(report.est_context_tokens, int)
    assert report.est_context_tokens >= 0


def test_evaluate_task_detects_redundant_calls(monkeypatch):
    # Every search returns the SAME single id, so only the first search adds a
    # new CVE; every later search is redundant. A two-cue query -> >=1 redundant.
    _patch_stub(monkeypatch)
    task = agent_evals.AgentTask(
        name="t",
        query="SQL injection that bypasses authentication",
        expected_ids=frozenset({"CVE-2024-5678"}),
        expected_sub_queries=2,
        reference_cues=("sql injection", "authentication"),
    )
    docs = [{"id": "CVE-2024-5678", "content": "sql injection", "metadata": {}}]
    report = agent_evals.evaluate_task(task, docs)
    assert report.steps >= 2
    assert report.redundant_calls >= 1


def test_run_evaluation_covers_all_tasks(monkeypatch):
    _patch_stub(monkeypatch)
    docs = [{"id": "CVE-2024-5678", "content": "sql injection", "metadata": {}}]
    reports = agent_evals.run_evaluation(docs)
    assert len(reports) == len(agent_evals.EVAL_TASKS)
    assert {r.name for r in reports} == {t.name for t in agent_evals.EVAL_TASKS}


def test_aggregate_folds_reports(monkeypatch):
    _patch_stub(monkeypatch)
    docs = [{"id": "CVE-2024-5678", "content": "sql injection", "metadata": {}}]
    reports = agent_evals.run_evaluation(docs)
    agg = agent_evals.aggregate(reports)

    assert agg.n_tasks == len(reports)
    assert 0.0 <= agg.success_rate <= 1.0
    assert 0.0 <= agg.mean_search_precision <= 1.0
    assert 0.0 <= agg.mean_search_recall <= 1.0
    assert agg.total_steps == sum(r.steps for r in reports)
    assert agg.total_redundant_calls == sum(r.redundant_calls for r in reports)
    assert agg.total_est_context_tokens == sum(r.est_context_tokens for r in reports)


def test_aggregate_empty_is_zeroed():
    agg = agent_evals.aggregate([])
    assert agg.n_tasks == 0
    assert agg.success_rate == 0.0
    assert agg.total_steps == 0

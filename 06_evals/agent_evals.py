"""
Agent Evals — Trajectory and Per-Task Cost over the Agentic RAG Loop

`rag_metrics.py` grades a SINGLE retrieval: embed the query, pull top-k, score
the hits. That is the right tool for naive RAG. It is the wrong tool for an
*agent*, which decides whether to search, plans several sub-queries, runs them
one at a time, and only stops when it judges the question answered. Grading just
the final hit set misses everything the agent did to get there — how many steps
it took, whether it issued the right searches, whether it wasted calls re-asking
for what it already had.

So this module evaluates the TRAJECTORY and the WHOLE TASK, not one call:

- success          — were all the expected CVE ids recovered into evidence?
- search precision — of the searches the agent actually issued, how many match
  the reference plan (planned the right sub-queries)?
- search recall    — of the reference sub-queries, how many did the agent issue
  (covered the plan)?
- steps            — how many searches the loop ran (trajectory length).
- redundant_calls  — searches that returned only CVEs already in evidence
  (a step that added nothing — the agent "spinning").
- est_context_tokens — a declared ESTIMATE (bytes / 4) of the context the task
  accumulated: pooled evidence text plus the reasoning trace. NOT a tokenizer
  count — it is a cheap, deterministic, tiktoken-free proxy, and it is labelled
  as an estimate everywhere it is reported.

Why trajectory + whole-task cost, and not tokens-per-call? GitHub evaluated the
RTK output-shortener on Copilot and found that trimming each tool's output made
the model reopen or rerun commands to recover what was cut — the task used more
tokens and took longer even though every single response was shorter. "Tokens
per tool call is the wrong objective. An efficiency change has to be evaluated
across the complete task." (see AGENT_EVALS.md Referências). A redundant search
in this harness is the same failure in miniature: a locally cheap step that
raises the task's real cost without moving it forward.

The agent under test is the deterministic planner/controller of
`12_agentic_rag/agentic_rag.py`, reused via importlib (its package name starts
with a digit, so a plain `import` is impossible). The retrieval path is
LLM-free, so every number here is reproducible without Ollama.

Run from the repo root:

    python -m 06_evals.agent_evals
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field

# The agentic_rag module lives in a digit-prefixed package (12_agentic_rag),
# which cannot be loaded with a normal `import 12_agentic_rag...`. importlib
# resolves it by its dotted string name instead.
agentic_rag = importlib.import_module("12_agentic_rag.agentic_rag")


# ---------------------------------------------------------------------------
# Task definitions — the evaluation set
# ---------------------------------------------------------------------------
# Each task carries the ground truth the agent is graded against:
#   - query:                 the user question fed to the agent.
#   - expected_ids:          CVE ids a correct run must gather into evidence.
#   - expected_sub_queries:  how many sub-queries the rule-based planner SHOULD
#                            decompose the question into (the severity sweep that
#                            a comparison question adds is counted here too, so
#                            this is the expected number of SEARCHES).
#   - reference_cues:        topical substrings that each reference sub-query is
#                            expected to carry. Used to score search precision /
#                            recall against the plan the agent actually issued,
#                            without hard-coding the planner's exact wording.
# The ids come straight from utils/data/cves.json (an RCE, a SQL injection, and
# a cryptographic weakness), so the labels are facts, not guesses.
@dataclass(frozen=True)
class AgentTask:
    name: str
    query: str
    expected_ids: frozenset[str]
    expected_sub_queries: int
    reference_cues: tuple[str, ...]


EVAL_TASKS: list[AgentTask] = [
    AgentTask(
        name="simple_sql_injection",
        query="Is there a SQL injection vulnerability that bypasses authentication?",
        expected_ids=frozenset({"CVE-2024-5678"}),
        # The question names TWO topic cues — "SQL injection" and
        # "authentication ... bypass" — so the rule-based planner decomposes it
        # into two sub-queries. Both point at the same CVE, which is exactly why
        # the second search registers as a redundant call in the trajectory
        # metrics: a textbook locally-cheap-but-globally-wasteful step.
        expected_sub_queries=2,
        reference_cues=("sql injection", "authentication"),
    ),
    AgentTask(
        name="simple_rce",
        query="Which CVE allows remote code execution in the request handler?",
        expected_ids=frozenset({"CVE-2024-1234"}),
        # "remote code execution" and "request handler" are two distinct topic
        # cues, so the planner decomposes this into two sub-queries.
        expected_sub_queries=2,
        reference_cues=("code execution", "request handler"),
    ),
    AgentTask(
        name="compound_rce_plus_severity",
        query="Which RCE CVEs affect request handlers, and which one is the most severe?",
        expected_ids=frozenset({"CVE-2024-1234"}),
        # Two topic cues (RCE, request handler) + a severity sweep added because
        # the question asks for a ranking -> three searches.
        expected_sub_queries=3,
        reference_cues=("code execution", "request handler", "severity"),
    ),
    AgentTask(
        name="compound_crypto_vs_sql",
        query="Compare the cryptographic and SQL injection issues — which is more severe?",
        expected_ids=frozenset({"CVE-2024-9012", "CVE-2024-5678"}),
        # Two topic cues (crypto, SQL injection) + a severity sweep -> three.
        expected_sub_queries=3,
        reference_cues=("cryptographic", "sql injection", "severity"),
    ),
]


# ---------------------------------------------------------------------------
# Per-task result
# ---------------------------------------------------------------------------
@dataclass
class TaskReport:
    name: str
    query: str
    expected_ids: frozenset[str]
    retrieved_ids: frozenset[str]
    success: bool
    steps: int
    expected_steps: int
    search_precision: float
    search_recall: float
    redundant_calls: int
    est_context_tokens: int
    sub_queries_run: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pure metric functions (no agent, no I/O — unit-testable in isolation)
# ---------------------------------------------------------------------------
def task_success(retrieved_ids: set[str], expected_ids: set[str]) -> bool:
    """
    True when EVERY expected CVE id was gathered into evidence.

    Deliberately strict (expected ⊆ retrieved): an agent that recovers two of
    three required CVEs has not completed the task, however good its individual
    searches looked.
    """
    return expected_ids.issubset(retrieved_ids)


def search_precision_recall(
    issued_cues: list[set[str]],
    reference_cues: tuple[str, ...],
) -> tuple[float, float]:
    """
    Score the agent's issued searches against the reference plan.

    Each issued search is reduced to the set of reference cues it covers.
    - precision = issued searches that match at least one reference cue
                  / issued searches  (did the agent avoid off-plan searches?)
    - recall    = reference cues covered by some issued search
                  / reference cues   (did the agent cover the whole plan?)

    Matching on cues rather than exact strings keeps the metric robust to the
    planner's precise phrasing: we check that the right TOPICS were searched,
    not that a sub-query string is character-identical.
    """
    references = {c.lower() for c in reference_cues}
    if not issued_cues:
        # No searches issued: recall is 0 if anything was expected; precision is
        # vacuously 1.0 (no off-plan search was made) when nothing was expected,
        # else 0.0.
        recall = 0.0 if references else 1.0
        precision = 1.0 if not references else 0.0
        return precision, recall

    on_plan = sum(1 for cues in issued_cues if cues & references)
    precision = on_plan / len(issued_cues)

    covered = set().union(*issued_cues) & references if references else set()
    recall = len(covered) / len(references) if references else 1.0
    return precision, recall


def estimate_context_tokens(*text_blocks: str) -> int:
    """
    ESTIMATE the context tokens a task accumulated, as total bytes // 4.

    This is a proxy, NOT a tokenizer: ~4 bytes/token is the common rule of thumb
    for English, and it is deterministic and dependency-free (no tiktoken). It
    exists to make the *relative* cost of trajectories comparable — a loop that
    carries more evidence and a longer trace forward estimates higher — not to
    predict a billing figure. Every report labels it "estimate".
    """
    total_bytes = sum(len(block.encode("utf-8")) for block in text_blocks)
    return total_bytes // 4


# ---------------------------------------------------------------------------
# Trajectory analysis over an AgentState produced by module 12
# ---------------------------------------------------------------------------
def _cues_in(text: str, reference_cues: tuple[str, ...]) -> set[str]:
    """Which reference cues appear (as substrings) in one issued sub-query."""
    low = text.lower()
    return {c.lower() for c in reference_cues if c.lower() in low}


def count_redundant_calls(per_step_found_ids: list[list[str]]) -> int:
    """
    Count searches that added no NEW CVE to the evidence set.

    Walks the trajectory in order, tracking which ids have been seen. A step
    whose hits are all already-seen ids is redundant — it spent a turn and
    carried more context forward without advancing the task. This is the
    whole-task analogue of GitHub's "recovery step" cost: a locally free call
    that raises the real cost of the task without moving it forward.
    """
    seen: set[str] = set()
    redundant = 0
    for found in per_step_found_ids:
        new_ids = [i for i in found if i not in seen]
        if not new_ids:
            redundant += 1
        seen.update(found)
    return redundant


def _per_step_found_ids(state) -> list[list[str]]:
    """
    Recover the per-search hit lists from the agent's reasoning trace.

    Module 12 records one 'iter N: search '<q>' -> [ids]' line per search in
    state.trace. Parsing it back is how we reconstruct the trajectory without
    changing module 12 (which this task must not edit). Deterministic: the trace
    format is fixed and the ids are plain CVE tokens.
    """
    import ast
    import re

    steps: list[list[str]] = []
    for line in state.trace:
        m = re.search(r"iter \d+: search '.*?' -> (\[.*\])", line)
        if not m:
            continue
        try:
            ids = ast.literal_eval(m.group(1))
            steps.append([str(i) for i in ids])
        except (ValueError, SyntaxError):
            steps.append([])
    return steps


def evaluate_task(task: AgentTask, documents: list[dict]) -> TaskReport:
    """Run the module-12 agent on one task and compute every trajectory metric."""
    state = agentic_rag.run_agentic_retrieval(task.query, documents)

    retrieved_ids = frozenset(state.evidence.keys())
    per_step_ids = _per_step_found_ids(state)

    issued_cues = [_cues_in(q, task.reference_cues) for q in state.sub_queries_run]
    precision, recall = search_precision_recall(issued_cues, task.reference_cues)

    context_block = agentic_rag.build_context(state)
    trace_block = "\n".join(state.trace)
    est_tokens = estimate_context_tokens(context_block, trace_block)

    return TaskReport(
        name=task.name,
        query=task.query,
        expected_ids=task.expected_ids,
        retrieved_ids=retrieved_ids,
        success=task_success(set(retrieved_ids), set(task.expected_ids)),
        steps=len(state.sub_queries_run),
        expected_steps=task.expected_sub_queries,
        search_precision=precision,
        search_recall=recall,
        redundant_calls=count_redundant_calls(per_step_ids),
        est_context_tokens=est_tokens,
        sub_queries_run=list(state.sub_queries_run),
    )


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
@dataclass
class AggregateReport:
    n_tasks: int
    success_rate: float
    mean_search_precision: float
    mean_search_recall: float
    total_steps: int
    total_redundant_calls: int
    total_est_context_tokens: int


def aggregate(reports: list[TaskReport]) -> AggregateReport:
    """Fold the per-task reports into a single whole-suite summary."""
    n = len(reports)
    if n == 0:
        return AggregateReport(0, 0.0, 0.0, 0.0, 0, 0, 0)
    return AggregateReport(
        n_tasks=n,
        success_rate=sum(1 for r in reports if r.success) / n,
        mean_search_precision=sum(r.search_precision for r in reports) / n,
        mean_search_recall=sum(r.search_recall for r in reports) / n,
        total_steps=sum(r.steps for r in reports),
        total_redundant_calls=sum(r.redundant_calls for r in reports),
        total_est_context_tokens=sum(r.est_context_tokens for r in reports),
    )


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------
def run_evaluation(documents: list[dict] | None = None) -> list[TaskReport]:
    """Evaluate every task in EVAL_TASKS and return the per-task reports."""
    if documents is None:
        documents = agentic_rag.build_documents()
    return [evaluate_task(task, documents) for task in EVAL_TASKS]


def main() -> None:
    documents = agentic_rag.build_documents()
    if not documents:
        print("No CVE documents available — cannot run agent evals.")
        return

    print("=" * 74)
    print("Agent Evals — trajectory & per-task cost (deterministic, no Ollama)")
    print(f"Corpus: {len(documents)} CVE documents | agent: 12_agentic_rag (hybrid)")
    print("Context tokens are an ESTIMATE (bytes/4), not a tokenizer count.")
    print("=" * 74)

    reports = run_evaluation(documents)

    for r in reports:
        print(f"\nTask: {r.name}")
        print(f'  Query: "{r.query}"')
        print(f"  Expected ids:   {sorted(r.expected_ids)}")
        print(f"  Retrieved ids:  {sorted(r.retrieved_ids)}")
        print(f"  Success:        {r.success}")
        print(f"  Steps (searches): {r.steps}  (expected {r.expected_steps})")
        print(f"  Search precision / recall: {r.search_precision:.2f} / {r.search_recall:.2f}")
        print(f"  Redundant calls: {r.redundant_calls}")
        print(f"  Est. context tokens: ~{r.est_context_tokens}  (estimate, bytes/4)")

    agg = aggregate(reports)
    print("\n" + "-" * 74)
    print("Aggregate (whole task set)")
    print(f"  tasks:                   {agg.n_tasks}")
    print(f"  success rate:            {agg.success_rate:.2f}")
    print(f"  mean search precision:   {agg.mean_search_precision:.2f}")
    print(f"  mean search recall:      {agg.mean_search_recall:.2f}")
    print(f"  total steps:             {agg.total_steps}")
    print(f"  total redundant calls:   {agg.total_redundant_calls}")
    print(f"  total est. ctx tokens:   ~{agg.total_est_context_tokens}  (estimate)")
    print("-" * 74)
    print(
        "\nReading: per-task cost (steps, redundant calls, est. tokens) is the "
        "objective,\nnot the size of any single tool response. A redundant call "
        "is a locally cheap\nstep that still raises the task's real cost — the "
        "trap AGENT_EVALS.md explains."
    )


if __name__ == "__main__":
    main()

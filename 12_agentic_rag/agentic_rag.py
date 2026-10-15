"""
Agentic RAG — Multi-Step Retrieval over the CVE Knowledge Base

Naive RAG retrieves ONCE: embed the query, pull the top-k documents, stuff them
into the prompt, generate. That works for a question whose answer sits in a
single passage. It falls apart on a *compound* question like:

    "Which RCE CVEs affect request handlers, and which one is the most severe?"

A single retrieval cannot answer that: "RCE request handler" and "most severe"
pull on different signals, and the comparison only makes sense after both have
been gathered. Agentic RAG puts a planning/decision loop AROUND retrieval: the
agent decides *whether* it needs to search, *what* sub-queries to issue, runs
them one at a time, accumulates the evidence, and only stops when it judges the
question answerable — then it generates.

The part that makes it "agentic" is the DECISION, not the model. This module
keeps that decision deterministic so the whole retrieval path runs WITHOUT an
LLM (no Ollama required): a rule-based planner decomposes the query into
sub-queries, and a rule-based controller decides when enough has been gathered.
The hybrid retriever (`create_search_engine('hybrid')`) and the CVE corpus
(`get_cve_documents()`) are the project's real components, so the retrieved CVEs
are reproducible. Only the FINAL natural-language answer needs the LLM, and that
step degrades gracefully: when the LLM is unavailable it prints the recovered
context and the deterministic conclusion instead of crashing.

Run from the repo root:

    python -m 12_agentic_rag.agentic_rag
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from utils.search import create_search_engine
from utils.data_loader import get_cve_documents, load_cves
from utils.logging import get_logger

# NOTE: utils.llm_client is imported lazily inside generate_answer(), NOT here.
# It pulls in langchain_openai, which is an LLM-stack dependency. Importing it at
# module load would make the whole module (including the deterministic retrieval
# path) crash when the LLM stack is absent — exactly the "LLM unavailable" case
# this module is designed to survive. Deferring the import lets that failure be
# caught and degrade gracefully.

logger = get_logger(__name__)

# How many agentic iterations we allow before forcing a stop. A small cap keeps
# a runaway planner from looping; the deterministic planner never needs many.
MAX_ITERATIONS = 4
# Documents to pull per sub-query search.
TOP_K = 3


# ---------------------------------------------------------------------------
# Document shape (GOTCHA): get_cve_documents() returns {cve_id: text}; the search
# engine wants List[{"id", "content", "metadata"}] with the "content" key.
# ---------------------------------------------------------------------------
def build_documents() -> List[Dict]:
    """Adapt get_cve_documents() {id: text} into the retriever's doc shape."""
    return [
        {"id": cve_id, "content": text, "metadata": {}}
        for cve_id, text in get_cve_documents().items()
    ]


# ---------------------------------------------------------------------------
# Retrieved-evidence accumulator
# ---------------------------------------------------------------------------
@dataclass
class RetrievedDoc:
    """One CVE pulled during the loop, with the best score seen for it."""

    id: str
    content: str
    score: float


@dataclass
class AgentState:
    """Everything the loop accumulates across iterations."""

    query: str
    sub_queries_run: List[str] = field(default_factory=list)
    # cve_id -> RetrievedDoc, so re-finding a CVE in a later search keeps the
    # best score instead of duplicating it.
    evidence: Dict[str, RetrievedDoc] = field(default_factory=dict)
    trace: List[str] = field(default_factory=list)

    def add_result(self, doc_id: str, content: str, score: float) -> None:
        existing = self.evidence.get(doc_id)
        if existing is None or score > existing.score:
            self.evidence[doc_id] = RetrievedDoc(doc_id, content, score)

    def ranked_evidence(self) -> List[RetrievedDoc]:
        return sorted(self.evidence.values(), key=lambda d: d.score, reverse=True)


# ---------------------------------------------------------------------------
# Deterministic planner — the "agentic" decision, no LLM required
# ---------------------------------------------------------------------------
# Topic cues map a word in the user's question to a focused retrieval sub-query.
# These are lexical rules, so decomposition is reproducible and offline.
_TOPIC_CUES: List[tuple[tuple[str, ...], str]] = [
    (("rce", "remote code execution", "code execution", "execute"),
     "remote code execution buffer overflow command injection"),
    (("request handler", "request parsing", "http request", "handler"),
     "request handler HTTP request parsing buffer overflow"),
    (("sql", "injection", "database"),
     "SQL injection authentication bypass login database"),
    (("auth", "authentication", "login", "credential", "bypass"),
     "authentication bypass login credential weakness"),
    (("crypto", "encryption", "cryptographic", "random", "key"),
     "cryptographic weakness weak random number generator key generation"),
    (("xss", "cross-site scripting", "script"),
     "cross-site scripting XSS payload injection"),
    (("csrf", "forgery"),
     "cross-site request forgery CSRF session token"),
]

# Phrases that signal the question asks for a comparison / ranking across CVEs
# (e.g. "most severe"). When present, the loop runs a severity pass and the
# synthesizer ranks by CVSS score.
_COMPARISON_CUES = (
    "most severe", "highest", "worst", "compare", "comparison", "rank",
    "which one", "most critical", "mais severo", "mais grave", "mais critico",
    "qual o mais", "compare", "ranking",
)


def _normalize(text: str) -> str:
    return text.lower()


def needs_retrieval(query: str) -> bool:
    """
    Decide whether the question requires the knowledge base at all.

    A greeting or a meta-question ("hello", "what can you do") does not; anything
    that mentions a CVE concept does. Deterministic: a question with no topical
    cue and no CVE-ish token is answered directly without retrieval.
    """
    norm = _normalize(query)
    if re.search(r"cve[-\s]?\d", norm):
        return True
    for cues, _ in _TOPIC_CUES:
        if any(cue in norm for cue in cues):
            return True
    # Generic security vocabulary still warrants a lookup.
    return any(word in norm for word in ("vulnerability", "cve", "exploit", "attack", "severe"))


def wants_comparison(query: str) -> bool:
    """True when the question asks to rank/compare across multiple CVEs."""
    norm = _normalize(query)
    return any(cue in norm for cue in _COMPARISON_CUES)


def plan_sub_queries(query: str) -> List[str]:
    """
    Decompose a (possibly compound) question into focused retrieval sub-queries,
    by rule. Each distinct topic cue present in the question yields one sub-query;
    de-duplicated and order-preserving. Falls back to the raw query when no cue
    matches, so the planner never returns an empty plan for a retrieval question.
    """
    norm = _normalize(query)
    subs: List[str] = []
    for cues, sub_query in _TOPIC_CUES:
        if any(cue in norm for cue in cues) and sub_query not in subs:
            subs.append(sub_query)

    if not subs:
        subs.append(query)
    return subs


# ---------------------------------------------------------------------------
# The agentic loop
# ---------------------------------------------------------------------------
def run_agentic_retrieval(query: str, documents: List[Dict]) -> AgentState:
    """
    Iterative, decision-driven retrieval. Deterministic and LLM-free.

    Steps:
      1. Decide whether retrieval is needed at all.
      2. Plan sub-queries from the question (rule-based decomposition).
      3. Search one sub-query per iteration, accumulating evidence, until the
         plan is exhausted or MAX_ITERATIONS is hit.
      4. If the question asks for a comparison, run one extra severity-focused
         pass so the ranked evidence is complete.
    """
    state = AgentState(query=query)
    engine = create_search_engine("hybrid")

    if not needs_retrieval(query):
        state.trace.append("decision: no retrieval needed (no CVE topic in query)")
        return state

    planned = plan_sub_queries(query)
    state.trace.append(f"plan: decomposed into {len(planned)} sub-queries -> {planned}")

    if wants_comparison(query):
        # A ranking question needs the broad field, not just the top hit of one
        # facet — add a severity-oriented pass so comparison has candidates.
        extra = "critical high severity CVSS score vulnerability"
        if extra not in planned:
            planned.append(extra)
            state.trace.append("decision: comparison detected -> added severity sweep")

    for i, sub_query in enumerate(planned[:MAX_ITERATIONS], start=1):
        state.sub_queries_run.append(sub_query)
        results = engine.search(sub_query, documents, top_k=TOP_K)
        found = [r.id for r in results]
        state.trace.append(f"iter {i}: search '{sub_query}' -> {found}")
        for r in results:
            state.add_result(r.id, r.content, r.score)

    state.trace.append(
        f"stop: plan exhausted after {len(state.sub_queries_run)} searches; "
        f"{len(state.evidence)} unique CVEs in evidence"
    )
    return state


# ---------------------------------------------------------------------------
# Deterministic synthesis helpers (used both as fallback and to ground the LLM)
# ---------------------------------------------------------------------------
def _severity_by_id() -> Dict[str, float]:
    """Map CVE id -> CVSS score, straight from the dataset (no LLM)."""
    return {cve.id: cve.score for cve in load_cves()}


def deterministic_conclusion(state: AgentState) -> str:
    """
    A rule-based answer derived purely from retrieved evidence and dataset
    scores. This is what we show when the LLM is unavailable, and what we hand
    the LLM as grounded facts when it is.
    """
    ranked = state.ranked_evidence()
    if not ranked:
        return "No CVEs matched the query."

    scores = _severity_by_id()
    by_severity = sorted(
        ranked, key=lambda d: scores.get(d.id, 0.0), reverse=True
    )
    lines = ["Retrieved CVEs (by CVSS severity):"]
    for d in by_severity:
        lines.append(f"  - {d.id}  (CVSS {scores.get(d.id, 0.0)})")

    if wants_comparison(state.query) and by_severity:
        top = by_severity[0]
        lines.append(
            f"Most severe among the retrieved CVEs: {top.id} "
            f"(CVSS {scores.get(top.id, 0.0)})."
        )
    return "\n".join(lines)


def build_context(state: AgentState) -> str:
    """Pool the retrieved document text into a single context block."""
    ranked = state.ranked_evidence()
    return "\n\n".join(f"[{d.id}]\n{d.content}" for d in ranked)


# ---------------------------------------------------------------------------
# Final generation with graceful degradation
# ---------------------------------------------------------------------------
def generate_answer(state: AgentState) -> str:
    """
    Produce the final natural-language answer.

    Tries the LLM; on ANY failure (Ollama down, no API key, network error) it
    falls back to the deterministic conclusion so the module always returns a
    useful, grounded result.
    """
    context = build_context(state)
    facts = deterministic_conclusion(state)

    if not context:
        return facts

    prompt = (
        "You are a security analyst. Answer the question using ONLY the CVE "
        "context below. Be concise and cite CVE ids.\n\n"
        f"Context:\n{context}\n\n"
        f"Grounded facts (CVSS scores):\n{facts}\n\n"
        f"Question: {state.query}\n\nAnswer:"
    )

    try:
        from utils.llm_client import get_llm_client  # lazy: LLM stack is optional

        client = get_llm_client()
        answer = client.generate(prompt, temperature=0.2, max_tokens=256)
        if answer and answer.strip():
            return answer.strip()
        logger.warning("LLM returned empty output; using deterministic fallback.")
    except Exception as exc:  # Ollama down, missing dep/key, timeout, etc.
        logger.warning(f"LLM unavailable ({exc.__class__.__name__}); using fallback.")

    return (
        "LLM unavailable — showing retrieved context and deterministic "
        "conclusion instead:\n\n" + facts
    )


# ---------------------------------------------------------------------------
# Demo driver
# ---------------------------------------------------------------------------
DEMO_QUERIES = [
    # Compound: needs decomposition (RCE + request handler) AND a comparison.
    "Which RCE CVEs affect request handlers, and which one is the most severe?",
    # Single-facet retrieval question.
    "Is there a SQL injection vulnerability that bypasses authentication?",
    # Comparison across the whole field.
    "Compare the cryptographic and SQL injection issues — which is more severe?",
]


def run_query(query: str, documents: List[Dict]) -> None:
    """Run the full agentic pipeline for one query and print the trace."""
    print("=" * 74)
    print(f"QUERY: {query}")
    print("=" * 74)

    state = run_agentic_retrieval(query, documents)

    print("\nAgent reasoning trace (deterministic, no LLM):")
    for step in state.trace:
        print(f"  • {step}")

    print("\nAccumulated evidence (ranked by retrieval score):")
    for d in state.ranked_evidence():
        print(f"  - {d.id}  (score {d.score:.4f})")

    print("\nFinal answer:")
    print(generate_answer(state))
    print()


def main() -> None:
    documents = build_documents()
    if not documents:
        print("No CVE documents available — cannot run agentic RAG.")
        return

    print("Agentic RAG over the CVE knowledge base")
    print(f"Corpus: {len(documents)} CVE documents | retriever: hybrid | top_k={TOP_K}")
    print(
        "The retrieval/decision path is deterministic and runs without Ollama; "
        "only final generation uses the LLM (with graceful fallback).\n"
    )
    for query in DEMO_QUERIES:
        run_query(query, documents)


if __name__ == "__main__":
    main()

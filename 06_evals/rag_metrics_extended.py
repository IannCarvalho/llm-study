"""
Retrieval Evaluation on the Extended CVE Dataset — BM25 vs Semantic vs Hybrid

Why a second eval script? ``rag_metrics.py`` runs over the 3-record default
dataset, where almost any retriever gets precision@1 right and the three
methods are indistinguishable. This script runs the same deterministic,
reference-based idea over the *extended* synthetic dataset
(``utils/data/cves_extended.json``, 39 records with deliberate distractors), so
BM25, semantic, and hybrid actually separate.

Two deliberate differences from the default eval:

- **Raw documents, no injected keywords.** ``get_cve_documents()`` sprinkles
  repeated keyword strings into each document to boost BM25; that hand-tuning
  hides how the retrievers really behave. Here each document is just the CVE's
  own fields (id, severity, score, versions, description), so the comparison is
  honest.
- **Three metrics, three retrievers.** precision@k, recall@k and MRR are
  reported for each of ``bm25``, ``semantic`` and ``hybrid`` over a labelled
  query set, printed as a comparative table.

The pure, LLM-free metric helpers (``precision_at_k``) are reused from
``rag_metrics.py`` via :mod:`importlib` so there is a single source of truth and
that file is not edited. recall@k and MRR are defined here because the default
eval does not need them.

Offline note: ``bm25`` runs with no model and no network. ``semantic`` and
``hybrid`` call ``sentence-transformers`` and download a model on first use; if
that is unavailable the script reports the method as skipped and still prints
the BM25 results, matching the repo's degrade-with-a-message convention.
"""

import importlib.util
from collections.abc import Callable
from pathlib import Path

from utils.data_loader import load_cves_from
from utils.search import create_search_engine

# ---------------------------------------------------------------------------
# Reuse the pure metric helpers from rag_metrics.py WITHOUT importing the
# package (digit-prefixed dir name is not a valid module path) and WITHOUT
# editing it. Load it by file path under a private alias.
# ---------------------------------------------------------------------------
_RAG_METRICS_PATH = Path(__file__).with_name("rag_metrics.py")


def _load_rag_metrics():
    spec = importlib.util.spec_from_file_location(
        "_rag_metrics_for_extended", _RAG_METRICS_PATH
    )
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load {_RAG_METRICS_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_rag_metrics = _load_rag_metrics()
precision_at_k: Callable[[list[str], set[str], int], float] = _rag_metrics.precision_at_k

# ---------------------------------------------------------------------------
# Dataset location (opt-in extended set, never the default cves.json).
# ---------------------------------------------------------------------------
_DATA_DIR = Path(__file__).resolve().parent.parent / "utils" / "data"
EXTENDED_DATASET = _DATA_DIR / "cves_extended.json"

# ---------------------------------------------------------------------------
# Labelled query set. Each query names the CVE id(s) a correct retriever should
# return for it. Labels target the distractor structure of the extended set:
# several queries have more than one relevant id (near-duplicate pairs), which
# is exactly where recall@k and precision@k start to disagree between methods.
# ---------------------------------------------------------------------------
EVAL_CASES = [
    {
        "query": (
            "unauthenticated buffer overflow remote code execution "
            "in a proxy connection handler"
        ),
        "relevant_ids": {"CVE-2099-0001"},
    },
    {
        "query": "deserialization remote code execution in a plugin loader",
        "relevant_ids": {"CVE-2099-0002"},
    },
    {
        "query": "sql injection reading customer records and payment tokens from a shopping cart",
        "relevant_ids": {"CVE-2099-0004", "CVE-2099-0005"},
    },
    {
        "query": "stored cross-site scripting executing in an administrator session",
        "relevant_ids": {"CVE-2099-0009"},
    },
    {
        "query": "cross-site request forgery changing a victim account email address",
        "relevant_ids": {"CVE-2099-0010"},
    },
    {
        "query": "authentication bypass by forging an unsigned single sign-on token",
        "relevant_ids": {"CVE-2099-0012"},
    },
    {
        "query": "heap buffer overflow decoding a malformed image file",
        "relevant_ids": {"CVE-2099-0015"},
    },
    {
        "query": "nonce reuse keystream reuse in authenticated encryption",
        "relevant_ids": {"CVE-2099-0019"},
    },
    {
        "query": "server-side request forgery reaching internal metadata endpoints",
        "relevant_ids": {"CVE-2099-0022"},
    },
    {
        "query": "weak random number generator predictable cryptographic keys",
        "relevant_ids": {"CVE-2024-9012", "CVE-2099-0020"},
    },
]


def recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """
    Fraction of the relevant documents that appear in the top-k.

    Complements precision@k: precision asks "how clean is the top-k?", recall
    asks "how much of what I wanted did I find?". For a query with two relevant
    ids, retrieving one of them is recall 0.5.
    """
    if not relevant_ids:
        return 0.0
    top_k = retrieved_ids[:k]
    hits = sum(1 for doc_id in top_k if doc_id in relevant_ids)
    return hits / len(relevant_ids)


def reciprocal_rank(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    """
    1 / rank of the first relevant document (1-indexed), or 0.0 if none is
    retrieved. Averaged over queries this is MRR — it rewards putting a correct
    document high, not merely somewhere in the list.
    """
    for i, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in relevant_ids:
            return 1.0 / i
    return 0.0


def build_documents() -> list[dict]:
    """
    Raw documents from the extended dataset — the CVE's own fields only, with
    NO injected keyword strings, so the retrievers are compared honestly.
    """
    cves = load_cves_from(EXTENDED_DATASET)
    documents: list[dict] = []
    for cve in cves:
        content = (
            f"CVE ID: {cve.id}\n"
            f"Severity: {cve.severity.value}\n"
            f"CVSS Score: {cve.score}\n"
            f"Affected Versions: {', '.join(cve.affected_versions)}\n"
            f"Description: {cve.description}\n"
        )
        documents.append({"id": cve.id, "content": content, "metadata": {}})
    return documents


def evaluate_method(method: str, documents: list[dict], k: int) -> dict[str, float] | None:
    """
    Run one retriever over every eval case and return mean precision@k,
    recall@k and MRR. Returns None if the method cannot run offline (e.g.
    semantic/hybrid without the embedding model), so the caller can report it
    as skipped rather than crash.
    """
    try:
        engine = create_search_engine(method)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"  [{method}] could not be created: {exc}")
        return None

    precisions: list[float] = []
    recalls: list[float] = []
    rrs: list[float] = []

    try:
        for case in EVAL_CASES:
            results = engine.search(case["query"], documents, top_k=k)
            retrieved_ids = [r.id for r in results]
            relevant = case["relevant_ids"]
            precisions.append(precision_at_k(retrieved_ids, relevant, k))
            recalls.append(recall_at_k(retrieved_ids, relevant, k))
            rrs.append(reciprocal_rank(retrieved_ids, relevant))
    except Exception as exc:
        # Typically a model download / network failure for semantic & hybrid.
        print(f"  [{method}] skipped — retrieval unavailable offline: {exc}")
        return None

    n = len(EVAL_CASES)
    return {
        "precision": sum(precisions) / n,
        "recall": sum(recalls) / n,
        "mrr": sum(rrs) / n,
    }


def main() -> None:
    """Compare bm25, semantic and hybrid on the extended dataset."""
    documents = build_documents()
    if not documents:
        print(
            "No extended CVE documents available — expected "
            f"{EXTENDED_DATASET}. Cannot run retrieval evaluation."
        )
        return

    k = 3  # the distractor pairs make top-3 the interesting cutoff
    print("=" * 74)
    print("Retrieval metrics on the EXTENDED CVE dataset (raw docs, no injected keywords)")
    print(f"Corpus: {len(documents)} CVE documents | queries: {len(EVAL_CASES)} | k={k}")
    print("semantic/hybrid need the embedding model; without it they are skipped.")
    print("=" * 74)

    header = f"{'method':<10} {'precision@k':>13} {'recall@k':>11} {'MRR':>8}"
    print("\n" + header)
    print("-" * len(header))

    for method in ("bm25", "semantic", "hybrid"):
        scores = evaluate_method(method, documents, k)
        if scores is None:
            print(f"{method:<10} {'(skipped — no model / offline)':>35}")
            continue
        print(
            f"{method:<10} {scores['precision']:>13.3f} "
            f"{scores['recall']:>11.3f} {scores['mrr']:>8.3f}"
        )

    print("\nLegend: precision@k = clean top-k; recall@k = share of relevant found;")
    print("        MRR = 1/rank of the first relevant hit, averaged over queries.")


if __name__ == "__main__":
    main()

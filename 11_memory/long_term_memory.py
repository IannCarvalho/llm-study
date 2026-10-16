"""
Long-Term Memory — Durable Knowledge via Semantic Retrieval

Short-term memory (`memory_store.py`) keeps the recent conversation in a bounded
window. But a window, by design, forgets: anything that scrolls out is gone (or
only coarsely summarized). **Long-term memory** solves the other half — storing
knowledge durably and recalling the *relevant* piece on demand, no matter how
long ago it was seen.

The standard implementation is a vector store queried by meaning: embed every
memory, embed the incoming question, and retrieve the closest matches. This
module reuses the project's own retrieval stack as that long-term store:

- the CVE knowledge base (`get_cve_documents()`) plays the role of durable memory;
- `create_search_engine('semantic'|'hybrid')` is the semantic recall mechanism;
- given a user question, the top matches are retrieved and injected into the
  prompt context — exactly how a RAG-style agent "remembers" facts it was never
  told in the current conversation.

Retrieval is **deterministic and LLM-free**: it uses local embeddings (semantic)
or BM25 (fallback), so it runs with no Ollama. Only the optional final answer
generation needs an LLM; without one, the module still prints the retrieved
context so the recall step is fully demonstrable offline.

Run it (retrieval runs without Ollama; generation is skipped if no LLM):

    $env:PYTHONPATH = "."
    python -m 11_memory.long_term_memory
"""

from __future__ import annotations

from utils.data_loader import get_cve_documents
from utils.search import as_search_documents, create_search_engine


def _build_documents() -> list[dict]:
    """
    Adapt the CVE knowledge base into the retriever's document shape.

    ``get_cve_documents()`` returns ``{id: formatted_text}``; the search engines
    expect a list of ``{"id", "content", "metadata"}`` dicts. This is the
    long-term memory "store" the retriever searches over.
    """
    return as_search_documents(get_cve_documents())


class LongTermMemory:
    """
    Semantic long-term memory backed by the project's search engines.

    Args:
        method: retrieval method — "semantic" (local embeddings) or "hybrid"
            (embeddings + BM25). Both are deterministic and need no LLM. If the
            embedding model cannot be loaded (e.g. offline, no model cached), the
            engine is transparently downgraded to "bm25" so recall still works.
        top_k: how many memories to retrieve per query.
    """

    def __init__(self, method: str = "semantic", top_k: int = 3) -> None:
        self.top_k = top_k
        self.documents = _build_documents()
        self.method = method
        self._engine = self._make_engine(method)

    def _make_engine(self, method: str):
        """
        Build the requested engine, degrading to BM25 if embeddings are
        unavailable. BM25 is pure-Python keyword matching: it needs no model
        download, so retrieval never hard-fails just because an embedding model
        is missing.
        """
        try:
            engine = create_search_engine(method)
            if method in ("semantic", "hybrid"):
                # Force the embedding model to load now (lazily imported inside
                # the engine) so we can fall back here rather than at query time.
                from utils.semantic_embeddings import embed_text

                embed_text("warmup")
            return engine
        except Exception as exc:  # noqa: BLE001 - embeddings missing/offline -> BM25
            print(f"[long-term memory] '{method}' retrieval unavailable "
                  f"({exc}); falling back to 'bm25'.")
            self.method = "bm25"
            return create_search_engine("bm25")

    def recall(self, query: str) -> list[dict]:
        """
        Retrieve the most relevant memories for a query.

        Returns a list of ``{"id", "content", "score"}`` dicts in rank order.
        Deterministic: the same query over the same store yields the same ranking.
        """
        results = self._engine.search(query, self.documents, top_k=self.top_k)
        return [
            {"id": r.id, "content": r.content, "score": float(r.score)}
            for r in results
        ]

    def build_context(self, query: str) -> str:
        """
        Recall relevant memories and format them as a context block ready to be
        injected into a prompt — the "memory → context" step of a RAG agent.
        """
        memories = self.recall(query)
        if not memories:
            return ""
        blocks = [f"[Memory {m['id']} | relevance {m['score']:.3f}]\n{m['content']}"
                  for m in memories]
        return "\n\n".join(blocks)

    def answer(self, query: str) -> str | None:
        """
        Full long-term-memory loop: recall context, then generate a grounded
        answer with the central LLM client.

        Returns the generated answer, or None if no LLM backend is reachable
        (the retrieval half still ran — see ``build_context``/``recall``).
        """
        context = self.build_context(query)
        try:
            from utils.llm_client import get_llm_client

            client = get_llm_client()
            prompt = (
                "Use the retrieved long-term memory below to answer the question. "
                "Only use facts supported by the memory; if it is not covered, say so.\n\n"
                f"=== Long-term memory ===\n{context}\n\n"
                f"=== Question ===\n{query}"
            )
            return client.generate(
                prompt,
                system_prompt="You answer strictly from the provided memory context.",
            ).strip()
        except Exception as exc:  # noqa: BLE001 - no LLM: retrieval still succeeded
            print(f"[long-term memory] LLM generation skipped (no backend: {exc}).")
            return None


def main() -> None:
    """
    Demonstrate long-term semantic recall.

    The retrieval step runs with no Ollama (local embeddings or BM25). The final
    generation is attempted and gracefully skipped if no LLM backend is up.
    """
    print("=" * 70)
    print("Long-term memory via semantic retrieval over the CVE knowledge base")
    print("=" * 70)

    memory = LongTermMemory(method="semantic", top_k=2)
    print(f"Store: {len(memory.documents)} CVE memories | retrieval method: "
          f"'{memory.method}'\n")

    queries = [
        "Was there a remote code execution bug in the request handler?",
        "Tell me about weaknesses in random number generation.",
    ]

    for query in queries:
        print(f'Question: "{query}"')
        memories = memory.recall(query)
        print(f"  Recalled {len(memories)} memory/memories (ranked):")
        for m in memories:
            first_line = m["content"].splitlines()[0] if m["content"] else ""
            print(f"    - {m['id']} (score {m['score']:.3f}) :: {first_line}")

        answer = memory.answer(query)
        if answer is not None:
            print(f"  LLM answer (grounded in memory):\n    {answer}")
        print()

    print("-" * 70)
    print("Retrieval ran deterministically without Ollama; generation needs an LLM.")
    print("-" * 70)


if __name__ == "__main__":
    main()

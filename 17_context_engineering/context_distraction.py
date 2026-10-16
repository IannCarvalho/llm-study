"""
Context Engineering — Context Distraction, and the four strategies to fix it.

This module is the hands-on half of the course's "Day 3.5 — Context Engineering".
It demonstrates, with the repo's own CVE data and NO LLM required, the central
failure mode of a bloated context window and the four engineering strategies that
counter it.

The idea (see utils/data/cves.json for the three real CVEs):

1.  FOCUSED context — a question about ONE CVE with only that CVE in the window.
2.  INFLATED context — the same single piece of evidence buried among dozens of
    synthetic distractor CVEs. The distractors are generated deterministically
    from the real CVEs (same seed every run) and are clearly tagged "[SYNTHETIC]"
    so no fake data is ever mistaken for ground truth.

The target evidence is placed at the START, the MIDDLE and the END of the
inflated context, because position matters: Liu et al. (2023), "Lost in the
Middle", show models recall evidence best at the beginning or end and worst in
the middle, and Chroma's "Context Rot" (2025) shows accuracy degrading as input
length grows even on simple tasks.

Then the four strategies from LangChain's "Context Engineering" (2025) are
applied to the inflated context and each one's resulting size is measured and
compared, checking whether the target evidence survives:

* SELECT   — top-k retrieval with utils.search.create_search_engine("bm25").
* COMPRESS — extract only the sentences that overlap the question's terms.
* ISOLATE  — one sub-context per sub-question instead of one giant blob.
* WRITE    — a persisted scratchpad of distilled notes kept outside the window.

Size is reported in characters and in ESTIMATED tokens (bytes / 4, the usual
rough rule of thumb — it is an estimate, not a real tokenizer count).

Determinism / offline: the whole demo above runs with no network, no model
download and no Ollama. An OPTIONAL last step, enabled only when an LLM is
reachable, asks the same question with the focused vs. inflated context and
compares the answer and the latency; it is imported lazily and degrades with a
clear message when the LLM stack is unavailable (the repo's standard pattern).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from utils.data_loader import load_cves
from utils.logging import get_logger
from utils.models import CVEData
from utils.search import create_search_engine, tokenize

logger = get_logger(__name__)

# Rough token estimate: ~4 bytes per token. This is an ESTIMATE, not a real
# tokenizer; it is enough to show relative context growth.
BYTES_PER_TOKEN = 4

# How many synthetic distractor CVEs to generate to "inflate" the context.
NUM_DISTRACTORS = 40

SYNTHETIC_TAG = "[SYNTHETIC]"

# A deterministic bank of fake product names / vulnerability flavours. Indexed
# by position so the same seed produces the same distractors on every run.
_FAKE_PRODUCTS = [
    "InvoicePrinter",
    "ChartRenderer",
    "LocaleFormatter",
    "ThumbnailCache",
    "NewsletterQueue",
    "AvatarUploader",
    "SitemapBuilder",
    "ColorPaletteKit",
]
_FAKE_FLAVOURS = [
    "an open redirect in the share dialog",
    "a verbose error page leaking stack traces",
    "a missing rate limit on the export endpoint",
    "a timezone off-by-one in the scheduler",
    "a deprecated TLS cipher left enabled",
]


@dataclass
class ContextBundle:
    """A built context plus the metadata needed to measure and compare it."""

    label: str
    text: str
    evidence_present: bool

    @property
    def chars(self) -> int:
        return len(self.text)

    @property
    def est_tokens(self) -> int:
        """Estimated token count (bytes / 4). An estimate, not a tokenizer."""
        return len(self.text.encode("utf-8")) // BYTES_PER_TOKEN


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------
def cve_block(cve: CVEData) -> str:
    """Render one real CVE as a compact context block."""
    return (
        f"CVE ID: {cve.id}\n"
        f"Severity: {cve.severity.value} (CVSS {cve.score})\n"
        f"Description: {cve.description}\n"
    )


def make_synthetic_distractors(
    real_cves: list[CVEData], count: int = NUM_DISTRACTORS
) -> list[str]:
    """
    Generate ``count`` deterministic distractor blocks derived from the real CVEs.

    Each distractor reuses a real CVE's shape but swaps in a fake product and a
    fake flavour chosen by index, and is tagged ``[SYNTHETIC]`` so it can never
    be confused with ground truth. Same input -> same output, every run.
    """
    if not real_cves:
        return []

    distractors: list[str] = []
    for i in range(count):
        base = real_cves[i % len(real_cves)]
        product = _FAKE_PRODUCTS[i % len(_FAKE_PRODUCTS)]
        flavour = _FAKE_FLAVOURS[i % len(_FAKE_FLAVOURS)]
        fake_id = f"CVE-9{i:03d}-{1000 + i}"
        # Keep the score in a plausible band but clearly derived from the index.
        fake_score = round(3.0 + (i % 60) / 10.0, 1)
        block = (
            f"{SYNTHETIC_TAG} CVE ID: {fake_id}\n"
            f"{SYNTHETIC_TAG} Severity: LOW (CVSS {fake_score})\n"
            f"{SYNTHETIC_TAG} Description: {product} v1.{i} has {flavour}. "
            f"This is synthetic filler derived from {base.id} to inflate the "
            f"context window and is NOT a real vulnerability.\n"
        )
        distractors.append(block)
    return distractors


def build_focused_context(target: CVEData) -> ContextBundle:
    """A minimal context holding only the target CVE."""
    return ContextBundle(
        label="focused (target only)",
        text=cve_block(target),
        evidence_present=True,
    )


def build_inflated_context(
    target: CVEData, distractors: list[str]
) -> ContextBundle:
    """
    Bury the target CVE in distractors, placing a copy of the target block at the
    START, the MIDDLE and the END so the demo can discuss positional recall
    ("lost in the middle").
    """
    target_block = cve_block(target)
    n = len(distractors)
    mid = n // 2
    parts: list[str] = []
    parts.append(target_block)  # START
    parts.extend(distractors[:mid])
    parts.append(target_block)  # MIDDLE
    parts.extend(distractors[mid:])
    parts.append(target_block)  # END
    return ContextBundle(
        label="inflated (target buried among distractors)",
        text="\n".join(parts),
        evidence_present=True,
    )


# ---------------------------------------------------------------------------
# The four strategies (Write / Select / Compress / Isolate)
# ---------------------------------------------------------------------------
def _split_sentences(text: str) -> list[str]:
    """Naive sentence split on '.', '!' or '?' — enough for the demo."""
    pieces = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in pieces if p.strip()]


def strategy_select(
    question: str, docs: list[dict], top_k: int = 3
) -> ContextBundle:
    """
    SELECT: pull in only the top-k most relevant documents via BM25 retrieval.

    Uses the deterministic, offline "bm25" engine (no embedding model download).
    """
    engine = create_search_engine("bm25")
    results = engine.search(question, docs, top_k=top_k)
    text = "\n".join(r.content for r in results)
    present = any(SYNTHETIC_TAG not in r.content for r in results)
    return ContextBundle(
        label=f"SELECT (bm25 top-{top_k})",
        text=text,
        evidence_present=present,
    )


def strategy_compress(question: str, context: str) -> ContextBundle:
    """
    COMPRESS: keep only sentences that share terms with the question.

    Deterministic lexical overlap — no LLM. Shrinks the window while trying to
    preserve the load-bearing sentences.
    """
    q_terms = set(tokenize(question))
    kept: list[str] = []
    for sentence in _split_sentences(context):
        if q_terms & set(tokenize(sentence)):
            kept.append(sentence)
    text = " ".join(kept)
    # Evidence survives if we kept a non-synthetic sentence mentioning the target.
    present = any(SYNTHETIC_TAG not in s for s in kept)
    return ContextBundle(
        label="COMPRESS (relevant sentences only)",
        text=text,
        evidence_present=present,
    )


def strategy_isolate(
    sub_questions: list[str], docs: list[dict], top_k: int = 2
) -> dict[str, ContextBundle]:
    """
    ISOLATE: build one small sub-context per sub-question instead of one blob.

    Each sub-context is independently retrieved, so irrelevant material from one
    sub-question never pollutes another.
    """
    engine = create_search_engine("bm25")
    bundles: dict[str, ContextBundle] = {}
    for sub in sub_questions:
        results = engine.search(sub, docs, top_k=top_k)
        text = "\n".join(r.content for r in results)
        present = any(SYNTHETIC_TAG not in r.content for r in results)
        bundles[sub] = ContextBundle(
            label=f"ISOLATE[{sub}]",
            text=text,
            evidence_present=present,
        )
    return bundles


@dataclass
class Scratchpad:
    """
    WRITE: a persisted scratchpad kept OUTSIDE the context window.

    The agent distills what it needs into short notes; later steps read the notes
    back instead of re-reading the whole raw context. This is the "scratchpad"
    form of the Write strategy (LangChain, 2025).
    """

    notes: list[str] = field(default_factory=list)

    def write(self, note: str) -> None:
        self.notes.append(note)

    def render(self) -> str:
        return "\n".join(f"- {n}" for n in self.notes)

    def as_bundle(self) -> ContextBundle:
        text = self.render()
        present = any(SYNTHETIC_TAG not in n for n in self.notes)
        return ContextBundle(
            label="WRITE (persisted scratchpad notes)",
            text=text,
            evidence_present=present,
        )


def distill_to_scratchpad(target: CVEData) -> Scratchpad:
    """Build a scratchpad holding only the facts needed to answer about target."""
    pad = Scratchpad()
    pad.write(f"{target.id}: {target.severity.value}, CVSS {target.score}")
    first_sentence = _split_sentences(target.description)[0]
    pad.write(f"{target.id} summary: {first_sentence}")
    return pad


# ---------------------------------------------------------------------------
# Optional LLM comparison (lazy, degrades cleanly)
# ---------------------------------------------------------------------------
def ask_with_context(question: str, context: str) -> tuple[str, float]:
    """
    Ask the question grounded in ``context`` using the optional LLM.

    Returns (answer, latency_seconds). Raises if the LLM stack is unavailable;
    the caller is responsible for degrading. Imported lazily so the module has
    no hard dependency on the LLM stack.
    """
    from utils.llm_client import get_llm_client  # lazy: LLM stack is optional

    prompt = (
        "You are a security analyst. Using ONLY the context below, answer the "
        "question in one sentence and cite the CVE id. Ignore any block tagged "
        "[SYNTHETIC].\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\nAnswer:"
    )
    client = get_llm_client()
    start = time.perf_counter()
    answer = client.generate(prompt, temperature=0.2, max_tokens=128)
    elapsed = time.perf_counter() - start
    return answer.strip(), elapsed


# ---------------------------------------------------------------------------
# Demo driver
# ---------------------------------------------------------------------------
def _print_measure(bundle: ContextBundle) -> None:
    survived = "yes" if bundle.evidence_present else "NO"
    print(
        f"  {bundle.label:<42} "
        f"chars={bundle.chars:>6}  ~tokens={bundle.est_tokens:>5}  "
        f"evidence={survived}"
    )


def _demo() -> int:
    print("=" * 70)
    print("DEMO — Context Engineering: distraction and the four strategies")
    print("=" * 70)

    cves = load_cves()
    if not cves:
        print("No CVE data found (utils/data/cves.json). Nothing to demonstrate.")
        return 1

    target = cves[0]  # CVE-2024-1234, the RCE
    question = f"What is the severity of {target.id} and what does it allow?"
    print(f"\nTarget CVE : {target.id}")
    print(f"Question   : {question}\n")

    # 1 & 2 — focused vs inflated context -----------------------------------
    distractors = make_synthetic_distractors(cves, NUM_DISTRACTORS)
    focused = build_focused_context(target)
    inflated = build_inflated_context(target, distractors)

    print(f"Built {len(distractors)} synthetic distractors (deterministic, tagged "
          f"{SYNTHETIC_TAG}).")
    print("The target block is placed at START, MIDDLE and END of the inflated "
          "context\n(positional recall — 'lost in the middle').\n")

    print("Context sizes:")
    _print_measure(focused)
    _print_measure(inflated)
    growth = inflated.est_tokens / max(focused.est_tokens, 1)
    print(f"\n  -> inflating multiplied the window ~{growth:.1f}x in estimated "
          f"tokens, for the SAME single answer.\n")

    # Build the document list used by retrieval-based strategies.
    docs: list[dict] = [
        {"id": target.id, "content": cve_block(target), "metadata": {}}
    ]
    for i, block in enumerate(distractors):
        docs.append({"id": f"SYN-{i}", "content": block, "metadata": {}})

    # 3 — the four strategies applied to the inflated context ----------------
    print("Applying the four strategies to the inflated context:\n")

    select_bundle = strategy_select(question, docs, top_k=3)
    _print_measure(select_bundle)

    compress_bundle = strategy_compress(question, inflated.text)
    _print_measure(compress_bundle)

    pad = distill_to_scratchpad(target)
    write_bundle = pad.as_bundle()
    _print_measure(write_bundle)

    sub_questions = [
        f"severity of {target.id}",
        f"what does {target.id} allow an attacker to do",
    ]
    isolate_bundles = strategy_isolate(sub_questions, docs, top_k=2)
    for bundle in isolate_bundles.values():
        _print_measure(bundle)

    print("\nSELECT, ISOLATE and WRITE all reconstruct a context far smaller "
          "than the\ninflated blob while keeping the real evidence. COMPRESS "
          "barely shrinks here\non purpose: every synthetic block also contains "
          "the words 'CVE', 'Severity'\nand the id, so naive lexical overlap "
          "keeps almost everything — a live demo\nof 'context confusion', where "
          "superfluous-but-similar text is hard to drop.\nReal compressors use "
          "an LLM or embeddings to judge meaning, not shared words.\n")

    # 4 — optional LLM comparison -------------------------------------------
    print("-" * 70)
    print("Optional step: ask the LLM with each context and compare "
          "answer + latency.")
    try:
        focused_answer, focused_t = ask_with_context(question, focused.text)
        inflated_answer, inflated_t = ask_with_context(question, inflated.text)
    except Exception as exc:  # Ollama down, missing dep/key, timeout, etc.
        logger.warning(f"LLM unavailable ({exc.__class__.__name__}); skipping.")
        print(
            "LLM unavailable — skipping the live comparison. The deterministic "
            "part above already shows the context sizes and that each strategy "
            "preserves the evidence while shrinking the window.\n"
            "To run the live step, start Ollama (or set an API key) and re-run."
        )
        return 0

    print("\nFOCUSED context:")
    print(f"  latency = {focused_t:.2f}s")
    print(f"  answer  = {focused_answer}")
    print("\nINFLATED context:")
    print(f"  latency = {inflated_t:.2f}s")
    print(f"  answer  = {inflated_answer}")
    print(f"\n  -> inflating the context changed latency by "
          f"{inflated_t - focused_t:+.2f}s for the same question.")
    return 0


def main() -> None:
    raise SystemExit(_demo())


if __name__ == "__main__":
    main()

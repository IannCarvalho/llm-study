"""
15_token_economy/token_budget.py — Estimating and budgeting the token bill.

This module answers two practical questions an AI engineer faces before cutting
anything:

1. *Where do the tokens of one model call actually go?* The "anatomy of the
   bill" breaks a single request into its parts — system prompt, conversation
   history, retrieved RAG context, tool output, and the model's own output —
   using the project's real prompts (``utils.prompts``) and real documents
   (``utils.data_loader.get_cve_documents``). You cannot optimize a bill you
   have not measured.

2. *How do I stop a single client from spending the whole budget?* The
   :class:`RateLimiter` is a deterministic in-memory token bucket with an
   injectable clock, so a budget policy can be tested without ``time.sleep``.

Token counting: by default we estimate ``bytes / 4``, the same heuristic RTK
ships (it carries no tokenizer, so percentages are reliable but absolute numbers
are approximate — see the README). If ``tiktoken`` is installed, pass
``use_tiktoken=True`` to :func:`estimate_tokens` for an exact BPE count; the
import is lazy so the deterministic path never requires the package.

Everything here is deterministic and offline: no network, no LLM, no model
download. ``main()`` narrates a worked example; nothing runs on import.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from utils.data_loader import get_cve_documents
from utils.prompts import RAG_SYSTEM

# Bytes-per-token divisor used by the ``bytes / 4`` heuristic. English text in a
# BPE tokenizer averages roughly four bytes per token; this is an estimate, not
# a measurement (the README is explicit that absolute numbers are approximate).
_BYTES_PER_TOKEN = 4


def estimate_tokens(text: str, *, use_tiktoken: bool = False, encoding: str = "cl100k_base") -> int:
    """Estimate the number of tokens in ``text``.

    By default uses the ``bytes / 4`` heuristic (UTF-8 byte length divided by
    four, rounded up for any non-empty string). This needs no dependency and
    matches how RTK reports its savings.

    When ``use_tiktoken`` is true the count is delegated to ``tiktoken`` for an
    exact BPE count. The import is done lazily inside this function so importing
    this module — and the whole deterministic path — never requires the package.
    If ``tiktoken`` is not installed the call falls back to the heuristic rather
    than raising, so callers get a number either way.

    Args:
        text: The string to measure.
        use_tiktoken: Prefer an exact ``tiktoken`` count when available.
        encoding: The ``tiktoken`` encoding name (default ``cl100k_base``).

    Returns:
        A non-negative token-count estimate.
    """
    if not text:
        return 0

    if use_tiktoken:
        try:
            import tiktoken  # lazy: never imported on the deterministic path

            return len(tiktoken.get_encoding(encoding).encode(text))
        except Exception:
            # Package missing or encoding unavailable — degrade to the heuristic
            # instead of failing. The caller still gets a usable estimate.
            pass

    n_bytes = len(text.encode("utf-8"))
    # Round up: any non-empty string costs at least one token.
    return -(-n_bytes // _BYTES_PER_TOKEN)


@dataclass(frozen=True)
class RequestAnatomy:
    """The token cost of one model call, broken down by part.

    The five parts are the usual contributors to a single request's input, plus
    the model's output:

    - ``system_prompt``: the standing instructions sent every turn.
    - ``history``: prior conversation turns carried forward.
    - ``rag_context``: retrieved documents injected into the prompt.
    - ``tool_output``: output of tool/shell calls the agent read (what RTK
      compresses).
    - ``model_output``: the tokens the model generates in reply.

    ``reasoning_output`` optionally accounts for hidden reasoning/"thinking"
    tokens, which are billed as output on models that expose them even though
    the user never sees them.
    """

    system_prompt: int
    history: int
    rag_context: int
    tool_output: int
    model_output: int
    reasoning_output: int = 0

    @property
    def input_tokens(self) -> int:
        """Tokens sent TO the model (everything but what it generates)."""
        return self.system_prompt + self.history + self.rag_context + self.tool_output

    @property
    def output_tokens(self) -> int:
        """Tokens the model GENERATES (visible output plus hidden reasoning)."""
        return self.model_output + self.reasoning_output

    @property
    def total(self) -> int:
        """All tokens for this call — the denominator every percentage dilutes against."""
        return self.input_tokens + self.output_tokens

    def fractions(self) -> dict[str, float]:
        """Each part as a fraction (0.0-1.0) of the call's total tokens."""
        total = self.total
        if total == 0:
            return {k: 0.0 for k in _PART_NAMES}
        return {
            "system_prompt": self.system_prompt / total,
            "history": self.history / total,
            "rag_context": self.rag_context / total,
            "tool_output": self.tool_output / total,
            "model_output": self.model_output / total,
            "reasoning_output": self.reasoning_output / total,
        }


_PART_NAMES = (
    "system_prompt",
    "history",
    "rag_context",
    "tool_output",
    "model_output",
    "reasoning_output",
)


def anatomy_from_text(
    *,
    system_prompt: str,
    history: str,
    rag_context: str,
    tool_output: str,
    model_output: str,
    reasoning_output: str = "",
    use_tiktoken: bool = False,
) -> RequestAnatomy:
    """Build a :class:`RequestAnatomy` by estimating each text part's tokens."""
    return RequestAnatomy(
        system_prompt=estimate_tokens(system_prompt, use_tiktoken=use_tiktoken),
        history=estimate_tokens(history, use_tiktoken=use_tiktoken),
        rag_context=estimate_tokens(rag_context, use_tiktoken=use_tiktoken),
        tool_output=estimate_tokens(tool_output, use_tiktoken=use_tiktoken),
        model_output=estimate_tokens(model_output, use_tiktoken=use_tiktoken),
        reasoning_output=estimate_tokens(reasoning_output, use_tiktoken=use_tiktoken),
    )


def sample_rag_anatomy(*, top_k: int = 3, use_tiktoken: bool = False) -> RequestAnatomy:
    """A realistic anatomy built from the project's own prompt and documents.

    Uses the real RAG system prompt (``utils.prompts.RAG_SYSTEM``) and the first
    ``top_k`` CVE documents (``utils.data_loader.get_cve_documents``) as the RAG
    context, so the breakdown reflects data that actually exists in this repo
    rather than invented strings. History / tool output / model output are short
    representative stand-ins — the point is the SHAPE of the bill.
    """
    docs = list(get_cve_documents().values())[:top_k]
    rag_context = "\n\n".join(docs)

    history = (
        "user: which CVEs affect the login flow?\n"
        "assistant: the SQL-injection one looks most relevant.\n"
        "user: what is its CVSS score?"
    )
    tool_output = rag_context  # the retrieval tool's raw output, pre-compression
    model_output = (
        "The most relevant CVE is a SQL injection in the login form with a high "
        "CVSS score; use parameterized queries to remediate it."
    )

    return anatomy_from_text(
        system_prompt=RAG_SYSTEM,
        history=history,
        rag_context=rag_context,
        tool_output=tool_output,
        model_output=model_output,
        use_tiktoken=use_tiktoken,
    )


@dataclass
class RequestBudget:
    """A per-request token budget with a simple fits/overflow check.

    ``max_input_tokens`` and ``max_output_tokens`` cap the two halves of a call
    independently, because they are priced and constrained differently (a
    context window bounds input; a ``max_tokens`` parameter bounds output).
    """

    max_input_tokens: int
    max_output_tokens: int

    def check(self, anatomy: RequestAnatomy) -> BudgetReport:
        """Report whether ``anatomy`` fits the budget and by how much it is over."""
        input_over = max(0, anatomy.input_tokens - self.max_input_tokens)
        output_over = max(0, anatomy.output_tokens - self.max_output_tokens)
        return BudgetReport(
            anatomy=anatomy,
            input_over=input_over,
            output_over=output_over,
        )


@dataclass(frozen=True)
class BudgetReport:
    """The result of checking a :class:`RequestAnatomy` against a budget."""

    anatomy: RequestAnatomy
    input_over: int
    output_over: int

    @property
    def fits(self) -> bool:
        """True when neither half exceeds its cap."""
        return self.input_over == 0 and self.output_over == 0


@dataclass
class RateLimiter:
    """A deterministic in-memory token-bucket rate limiter.

    The bucket holds up to ``capacity`` tokens and refills at ``refill_per_sec``
    tokens per second, capped at ``capacity``. :meth:`allow` tries to remove the
    requested number of tokens; it succeeds (and removes them) only if enough are
    available after refilling for the elapsed time.

    The clock is INJECTED (``clock`` returns the current time in seconds), so
    tests advance time explicitly instead of sleeping — the limiter is fully
    deterministic. Default clock is ``time.monotonic``.

    This models the budget idea from OWASP LLM10:2025 "Unbounded Consumption":
    without a limiter, one client can drive token spend without bound.

    Args:
        capacity: Maximum tokens the bucket can hold (also the burst size).
        refill_per_sec: Tokens added per second of elapsed time.
        clock: Callable returning monotonic seconds. Injected for testability.
    """

    capacity: float
    refill_per_sec: float
    clock: Callable[[], float] = field(default=None)  # type: ignore[assignment]
    _tokens: float = field(init=False, default=0.0)
    _last: float = field(init=False, default=0.0)

    def __post_init__(self) -> None:
        if self.capacity <= 0:
            raise ValueError("capacity must be positive")
        if self.refill_per_sec < 0:
            raise ValueError("refill_per_sec must be non-negative")
        if self.clock is None:
            import time

            self.clock = time.monotonic
        # Start full: a fresh client may burst up to one full bucket.
        self._tokens = float(self.capacity)
        self._last = self.clock()

    @property
    def available(self) -> float:
        """Current token count after refilling for elapsed time (read-only peek)."""
        now = self.clock()
        elapsed = max(0.0, now - self._last)
        return min(self.capacity, self._tokens + elapsed * self.refill_per_sec)

    def allow(self, cost: float = 1.0) -> bool:
        """Try to spend ``cost`` tokens; return whether it was allowed.

        Refills the bucket for the time elapsed since the last call, then removes
        ``cost`` tokens if at least that many are available. A denied request
        removes nothing.
        """
        if cost < 0:
            raise ValueError("cost must be non-negative")
        now = self.clock()
        elapsed = max(0.0, now - self._last)
        self._last = now
        self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_per_sec)
        if self._tokens >= cost:
            self._tokens -= cost
            return True
        return False


def _format_anatomy(anatomy: RequestAnatomy, fractions: Mapping[str, float]) -> str:
    """Pretty one-part-per-line breakdown for the demo narration."""
    rows = []
    labels = {
        "system_prompt": "system prompt",
        "history": "history",
        "rag_context": "RAG context",
        "tool_output": "tool output",
        "model_output": "model output",
        "reasoning_output": "reasoning output",
    }
    for key in _PART_NAMES:
        tokens = getattr(anatomy, key)
        rows.append(f"  {labels[key]:<18} {tokens:>6} tok   {fractions[key]:>6.1%}")
    return "\n".join(rows)


def main() -> None:
    """Narrate the anatomy of one real RAG request and a rate-limit decision."""
    print("=" * 64)
    print("Token economy — anatomy of one model call (bytes/4 estimate)")
    print("=" * 64)

    anatomy = sample_rag_anatomy(top_k=3)
    print(_format_anatomy(anatomy, anatomy.fractions()))
    print("-" * 64)
    print(f"  input tokens : {anatomy.input_tokens}")
    print(f"  output tokens: {anatomy.output_tokens}")
    print(f"  TOTAL        : {anatomy.total}")
    print()
    print(
        "  Note: tool output is one slice of INPUT, which is one slice of the\n"
        "  TOTAL. Compressing tool output by 90% does NOT cut the bill by 90%."
    )

    budget = RequestBudget(max_input_tokens=400, max_output_tokens=256)
    report = budget.check(anatomy)
    print("-" * 64)
    print(f"  budget {budget.max_input_tokens} in / {budget.max_output_tokens} out "
          f"-> fits={report.fits} (input_over={report.input_over}, "
          f"output_over={report.output_over})")

    # Deterministic rate-limit demo with an injected fake clock.
    now = {"t": 0.0}
    limiter = RateLimiter(capacity=2, refill_per_sec=1.0, clock=lambda: now["t"])
    decisions = []
    for _ in range(3):
        decisions.append(limiter.allow(cost=1))  # third is denied: bucket empty
    now["t"] = 2.0  # two seconds pass -> two tokens refill
    decisions.append(limiter.allow(cost=1))  # allowed again
    print("-" * 64)
    print(f"  rate limiter (cap=2, 1 tok/s): first-three={decisions[:3]}, "
          f"after 2s={decisions[3]}")
    print("=" * 64)


if __name__ == "__main__":
    main()

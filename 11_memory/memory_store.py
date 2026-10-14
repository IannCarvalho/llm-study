"""
Short-Term Conversation Memory — Sliding Window + Summarization Trigger

Agents elsewhere in this project are *stateless*: each call sees only the prompt
it is given and forgets everything afterwards. This module shows the first half
of giving an agent memory — **short-term memory** — using two classic techniques:

1. Sliding window: keep only the last N turns verbatim. This bounds the context
   size (and therefore cost/latency) no matter how long the conversation runs.
2. Summarization trigger: when the conversation grows past the window, the turns
   that fall out are not thrown away — they are compressed into a running
   "summary" turn so their gist survives. The compression uses the project's
   central LLM client (`client.generate`), with a deterministic fallback so the
   mechanism (and this file's self-test) works with no LLM / no Ollama.

The companion file `long_term_memory.py` covers the second half (durable,
searchable long-term memory via semantic retrieval over the CVE knowledge base).

Run the self-test (no LLM required):

    $env:PYTHONPATH = "."
    python -m 11_memory.memory_store
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional


# A turn is one message in the conversation. role is "user" | "assistant" |
# "system"; a summary of evicted history is stored as a system turn so it is
# clearly not something the user or assistant literally said.
@dataclass
class Turn:
    """A single conversation message."""

    role: str
    content: str


# A summarizer compresses newly evicted turns into one summary string, folding
# in whatever summary already existed. Taking the prior summary as a separate
# argument (instead of smuggling it back in as a fake turn) keeps cumulative
# summarization from re-wrapping its own header on every eviction. The LLM-backed
# summarizer and the deterministic fallback share this signature, so the memory
# class never cares which one it was given.
Summarizer = Callable[[List["Turn"], Optional[str]], str]

_SUMMARY_HEADER = "Earlier conversation (summarized):"


def _deterministic_summary(turns: List[Turn], prior_summary: Optional[str] = None) -> str:
    """
    LLM-free fallback summarizer.

    Produces a compact, reproducible digest: the prior summary's body (if any) is
    carried forward verbatim and the newly evicted turns are appended as trimmed
    role/snippet lines under a single header. It understands no meaning, but it is
    instant, dependency-free, and good enough to keep the conversation's gist when
    no LLM is available — and it makes this module testable without Ollama.
    """
    lines: List[str] = []

    # Carry the prior summary's existing bullet lines forward unchanged so the
    # oldest content is not re-truncated (and the header is not nested) on each
    # successive eviction.
    if prior_summary:
        for line in prior_summary.splitlines():
            if line.strip() and line.strip() != _SUMMARY_HEADER:
                lines.append(line)

    for turn in turns:
        snippet = " ".join(turn.content.split())  # collapse whitespace
        if len(snippet) > 80:
            snippet = snippet[:77] + "..."
        lines.append(f"- {turn.role}: {snippet}")

    if not lines:
        return ""
    return _SUMMARY_HEADER + "\n" + "\n".join(lines)


def _llm_summary(turns: List[Turn], prior_summary: Optional[str] = None) -> str:
    """
    LLM-backed summarizer using the project's central client.

    Folds the prior summary and the newly evicted turns into one fresh summary.
    Falls back to the deterministic summary if the LLM backend (e.g. Ollama) is
    not reachable, so a missing LLM degrades gracefully instead of crashing the
    conversation. Import is local so this module loads with no LLM configured.
    """
    try:
        from utils.llm_client import get_llm_client

        client = get_llm_client()
        transcript = "\n".join(f"{t.role}: {t.content}" for t in turns)
        prior_block = (
            f"Summary so far:\n{prior_summary}\n\n" if prior_summary else ""
        )
        prompt = (
            "Update the running summary of a conversation. Preserve facts, "
            "decisions, and any identifiers mentioned, and keep it concise.\n\n"
            f"{prior_block}New turns to fold in:\n{transcript}"
        )
        summary = client.generate(
            prompt,
            system_prompt="You compress conversation history without losing key facts.",
        ).strip()
        return summary or _deterministic_summary(turns, prior_summary)
    except Exception as exc:  # noqa: BLE001 - any backend/config failure degrades to fallback
        fallback = _deterministic_summary(turns, prior_summary)
        return fallback + f"\n(LLM summarizer unavailable: {exc})"


class ConversationMemory:
    """
    Short-term conversation memory with a sliding window and summarization.

    The most recent ``window_size`` turns are always kept verbatim. When adding a
    turn would push the count past the window, the oldest overflowing turns are
    evicted and folded into a single running summary turn (prepended to the
    history) so their information is not lost outright.

    Args:
        window_size: how many of the most recent turns to keep verbatim (>= 1).
        summarizer: callable that compresses evicted turns into one string.
            Defaults to the LLM-backed summarizer (which itself falls back to a
            deterministic digest when no LLM is reachable). Pass a custom
            callable — e.g. the deterministic one — for fully offline behaviour.
    """

    def __init__(
        self,
        window_size: int = 4,
        summarizer: Optional[Summarizer] = None,
    ) -> None:
        if window_size < 1:
            raise ValueError("window_size must be >= 1")

        self.window_size = window_size
        self._summarizer: Summarizer = summarizer or _llm_summary
        self._turns: List[Turn] = []
        # The running summary of everything that has fallen out of the window.
        self._summary: Optional[str] = None

    def add_turn(self, role: str, content: str) -> None:
        """Append a turn and summarize-then-evict anything beyond the window."""
        self._turns.append(Turn(role=role, content=content))
        self._enforce_window()

    def add_user(self, content: str) -> None:
        """Convenience: add a user turn."""
        self.add_turn("user", content)

    def add_assistant(self, content: str) -> None:
        """Convenience: add an assistant turn."""
        self.add_turn("assistant", content)

    def _enforce_window(self) -> None:
        """
        If the window overflowed, summarize the oldest excess turns and drop them.

        The newly produced summary is merged with any prior summary so the digest
        stays a single turn no matter how many times eviction happens.
        """
        overflow = len(self._turns) - self.window_size
        if overflow <= 0:
            return

        evicted = self._turns[:overflow]
        self._turns = self._turns[overflow:]

        # Fold the newly evicted turns into whatever summary already existed so
        # the compression is cumulative rather than losing older context.
        self._summary = self._summarizer(evicted, self._summary)

    def get_messages(self) -> List[dict]:
        """
        Build the message list to send to the LLM: the running summary (as a
        system message) followed by the verbatim windowed turns.

        Shaped as ``{"role": ..., "content": ...}`` dicts to match
        ``LLMClient.chat`` directly.
        """
        messages: List[dict] = []
        if self._summary:
            messages.append({"role": "system", "content": self._summary})
        messages.extend({"role": t.role, "content": t.content} for t in self._turns)
        return messages

    @property
    def summary(self) -> Optional[str]:
        """The current running summary of evicted turns (None if nothing evicted)."""
        return self._summary

    @property
    def window(self) -> List[Turn]:
        """A copy of the turns currently held verbatim in the window."""
        return list(self._turns)

    def __len__(self) -> int:
        """Number of turns currently held verbatim (excludes the summary)."""
        return len(self._turns)


def _demo() -> None:
    """
    Self-test with a deterministic (no-LLM) summarizer.

    Proves two things without any backend:
    - the sliding window never exceeds window_size verbatim turns;
    - crossing the window triggers summarization and the evicted turns' content
      is captured in the running summary.
    """
    print("=" * 70)
    print("Short-term memory: sliding window + summarization trigger (no LLM)")
    print("=" * 70)

    window_size = 4
    memory = ConversationMemory(
        window_size=window_size,
        summarizer=_deterministic_summary,  # deterministic => testable offline
    )

    scripted = [
        ("user", "Which CVE is the critical RCE?"),
        ("assistant", "CVE-2024-1234 is a CRITICAL remote code execution (score 9.8)."),
        ("user", "And the SQL injection one?"),
        ("assistant", "CVE-2024-5678 covers SQL injection used to bypass authentication."),
        ("user", "What about the crypto weakness?"),
        ("assistant", "CVE-2024-9012 is a weak random number generator issue."),
        ("user", "Remind me which one was the RCE again?"),
    ]

    print(f"\nwindow_size = {window_size}\n")
    for i, (role, content) in enumerate(scripted, start=1):
        memory.add_turn(role, content)
        print(f"after turn {i:>2} ({role:<9}) -> window holds {len(memory)} turn(s), "
              f"summary={'yes' if memory.summary else 'no'}")

    # --- Assertions: the mechanism must behave exactly as described ----------
    assert len(memory) <= window_size, "window exceeded its size"
    assert memory.summary is not None, "summarization should have triggered"

    total_added = len(scripted)
    assert total_added > window_size, "test should add more turns than the window"
    # The very first turn fell out of the window, so its content must now live
    # only inside the summary — proof the trigger preserved evicted history.
    assert "critical RCE" in memory.summary, "evicted turn not captured in summary"
    # And it must NOT still be sitting in the verbatim window.
    assert all("critical RCE" not in t.content for t in memory.window), \
        "evicted turn should no longer be verbatim"

    print("\n" + "-" * 70)
    print("Running summary (compressed evicted history):")
    print(memory.summary)
    print("-" * 70)

    print("\nMessages that would be sent to the LLM (summary + window):")
    for msg in memory.get_messages():
        content = msg["content"]
        if len(content) > 70:
            content = content[:67] + "..."
        print(f"  [{msg['role']:<9}] {content}")

    print("\nAll assertions passed: window bounded, summarization triggered, "
          "evicted history preserved.")


if __name__ == "__main__":
    _demo()

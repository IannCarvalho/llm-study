"""
Deterministic tests for 11_memory/memory_store.py.

Uses the deterministic (no-LLM) summarizer so the whole suite is offline.
Covers the sliding window bound, the summarization trigger on overflow,
coherence of get_messages / __len__ / window / summary, and the
_deterministic_summary helper directly.
"""

from conftest import load_module

ms = load_module("11_memory/memory_store.py", "memory_store")


def _make(window_size=2):
    """A memory with the deterministic summarizer (no LLM)."""
    return ms.ConversationMemory(window_size=window_size, summarizer=ms._deterministic_summary)


# ---------------------------------------------------------------------------
# Sliding window bound
# ---------------------------------------------------------------------------
def test_window_never_exceeds_max():
    mem = _make(window_size=3)
    for i in range(10):
        mem.add_user(f"message number {i}")
    assert len(mem) <= 3
    assert len(mem.window) <= 3


def test_window_keeps_most_recent_verbatim():
    mem = _make(window_size=2)
    mem.add_user("oldest")
    mem.add_assistant("middle")
    mem.add_user("newest")
    contents = [t.content for t in mem.window]
    assert contents == ["middle", "newest"]
    assert "oldest" not in contents


# ---------------------------------------------------------------------------
# Summarization trigger
# ---------------------------------------------------------------------------
def test_no_summary_before_overflow():
    mem = _make(window_size=4)
    mem.add_user("one")
    mem.add_assistant("two")
    assert mem.summary is None


def test_summary_triggers_on_overflow():
    mem = _make(window_size=2)
    mem.add_user("first turn about the critical RCE")
    mem.add_assistant("ack")
    mem.add_user("third turn")  # pushes the first turn out of the window
    assert mem.summary is not None
    # The evicted turn's content now lives only in the summary.
    assert "critical RCE" in mem.summary
    assert all("critical RCE" not in t.content for t in mem.window)


def test_summary_is_cumulative_across_multiple_evictions():
    mem = _make(window_size=2)
    mem.add_user("alpha fact")
    mem.add_assistant("beta fact")
    mem.add_user("gamma fact")  # evicts alpha
    mem.add_assistant("delta fact")  # evicts beta
    # Both evicted turns are retained in the single running summary.
    assert "alpha fact" in mem.summary
    assert "beta fact" in mem.summary


# ---------------------------------------------------------------------------
# get_messages / coherence
# ---------------------------------------------------------------------------
def test_get_messages_without_summary_is_just_window():
    mem = _make(window_size=4)
    mem.add_user("u1")
    mem.add_assistant("a1")
    msgs = mem.get_messages()
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert [m["content"] for m in msgs] == ["u1", "a1"]


def test_get_messages_prepends_summary_as_system():
    mem = _make(window_size=2)
    mem.add_user("evicted one")
    mem.add_assistant("kept a")
    mem.add_user("kept b")  # triggers summary
    msgs = mem.get_messages()
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == mem.summary
    # Remaining messages are the verbatim window, in order.
    assert [m["content"] for m in msgs[1:]] == [t.content for t in mem.window]


def test_len_counts_only_verbatim_turns():
    mem = _make(window_size=2)
    for text in ["a", "b", "c", "d"]:
        mem.add_user(text)
    # Four turns added, window holds 2; __len__ excludes the summary.
    assert len(mem) == 2


def test_window_size_must_be_positive():
    import pytest

    with pytest.raises(ValueError):
        ms.ConversationMemory(window_size=0)


# ---------------------------------------------------------------------------
# _deterministic_summary helper
# ---------------------------------------------------------------------------
def test_deterministic_summary_empty_is_empty_string():
    assert ms._deterministic_summary([], None) == ""


def test_deterministic_summary_includes_role_and_snippet():
    turns = [ms.Turn(role="user", content="what is the RCE CVE")]
    summary = ms._deterministic_summary(turns, None)
    assert ms._SUMMARY_HEADER in summary
    assert "user" in summary
    assert "RCE" in summary


def test_deterministic_summary_carries_prior_forward():
    turns = [ms.Turn(role="assistant", content="new content here")]
    prior = ms._SUMMARY_HEADER + "\n- user: old content"
    summary = ms._deterministic_summary(turns, prior)
    assert "old content" in summary
    assert "new content here" in summary
    # Header appears exactly once (not nested).
    assert summary.count(ms._SUMMARY_HEADER) == 1

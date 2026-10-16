"""
15_token_economy/task_cost_sim.py — Per-call savings vs per-task cost.

This is the "local metric trap" from GitHub's RTK write-up, made into a small
deterministic simulation: compressing a tool's output saves tokens on THAT call,
but if the compression drops something the agent needed, the agent recovers it
(reopens the saved original, or reruns the command), and those extra turns carry
the whole conversation forward again. Measured across the complete task, an
over-aggressive compressor can make the bill go UP — "We saved tokens locally
and spent more globally."

The model here is deliberately simple and fully deterministic (no randomness, no
LLM): each tool call has a raw output size; a compression ratio shrinks what the
agent reads; a per-call "recovery probability" (really a deterministic threshold
on how much was cut) decides whether the agent must recover. Recovery re-reads
the full original AND replays the carried-forward context of the turn.

Run it to see the crossover: light compression wins, aggressive compression
loses once recovery kicks in. ``main()`` prints the comparison; nothing runs on
import.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module

_token_budget = import_module("15_token_economy.token_budget")

# Above this fraction of output removed, the compression is "too aggressive" and
# the agent is modelled as needing to recover the dropped detail. Mirrors
# GitHub's finding that cutting source-like/needed output forces reopen/rerun.
_RECOVERY_CUT_THRESHOLD = 0.5


@dataclass(frozen=True)
class ToolCall:
    """One tool call in the simulated task.

    Attributes:
        name: Label for the call (for the printout).
        raw_tokens: Tokens the tool's full output would cost.
        needed: True if the agent genuinely needs the detail that aggressive
            compression would drop — only these can trigger recovery.
    """

    name: str
    raw_tokens: int
    needed: bool


@dataclass(frozen=True)
class TaskResult:
    """The accounting for one simulated run of the whole task."""

    compression: float
    carried_context: int
    tool_tokens: int
    recovery_tokens: int
    recoveries: int

    @property
    def total(self) -> int:
        """Full token bill for the task: tool reads + recovery overhead."""
        return self.tool_tokens + self.recovery_tokens


def simulate_task(
    calls: list[ToolCall],
    *,
    compression: float,
    carried_context: int,
) -> TaskResult:
    """Simulate one task run at a given compression level.

    Args:
        calls: The tool calls the task makes, in order.
        compression: Fraction of each tool output removed (0.0 = no
            compression, 0.9 = keep only 10%).
        carried_context: Tokens of conversation context re-sent on each
            recovery turn (history + prompts that ride along).

    Returns:
        A :class:`TaskResult` with the per-call tool tokens, the recovery
        overhead, and the total.

    Model:
        - Each call contributes ``raw_tokens * (1 - compression)`` tokens to
          what the agent reads.
        - A call that is ``needed`` AND compressed past
          ``_RECOVERY_CUT_THRESHOLD`` triggers ONE recovery: the agent reopens
          the FULL original AND reruns the command (``2 * raw_tokens``) and
          carries context forward on both extra turns (``2 * carried_context``).
          This is the "spent more globally" term.
    """
    if not 0.0 <= compression <= 1.0:
        raise ValueError("compression must be in [0.0, 1.0]")

    tool_tokens = 0
    recovery_tokens = 0
    recoveries = 0
    for call in calls:
        tool_tokens += round(call.raw_tokens * (1.0 - compression))
        if call.needed and compression > _RECOVERY_CUT_THRESHOLD:
            # Recovery (GitHub's finding): the agent reopens the full original
            # AND reruns the command to get back what was dropped, and each of
            # those extra turns carries the conversation context forward again.
            # So one recovery costs: full original + rerun + two carried turns.
            recovery_tokens += 2 * call.raw_tokens + 2 * carried_context
            recoveries += 1

    return TaskResult(
        compression=compression,
        carried_context=carried_context,
        tool_tokens=tool_tokens,
        recovery_tokens=recovery_tokens,
        recoveries=recoveries,
    )


def _default_task() -> list[ToolCall]:
    """A representative task: some noisy outputs, some the agent truly needs."""
    return [
        ToolCall("pytest (noise)", raw_tokens=1200, needed=False),
        ToolCall("git status (noise)", raw_tokens=300, needed=False),
        ToolCall("git diff (needed)", raw_tokens=900, needed=True),
        ToolCall("grep (needed)", raw_tokens=600, needed=True),
        ToolCall("build log (noise)", raw_tokens=1500, needed=False),
    ]


def main() -> None:
    """Sweep compression levels and show where the total bill crosses over."""
    calls = _default_task()
    carried = 800  # tokens of history/prompt re-sent on each recovery turn

    print("=" * 68)
    print("Per-call savings vs per-task cost (deterministic simulation)")
    print("=" * 68)
    print(f"  task: {len(calls)} tool calls, "
          f"{sum(c.raw_tokens for c in calls)} raw tool tokens, "
          f"carried context per recovery = {carried}")
    print("-" * 68)
    print(f"  {'compression':>12} {'tool tok':>10} {'recovery':>10} "
          f"{'recov#':>7} {'TOTAL':>8}")

    baseline = simulate_task(calls, compression=0.0, carried_context=carried)
    for comp in (0.0, 0.3, 0.5, 0.7, 0.9):
        res = simulate_task(calls, compression=comp, carried_context=carried)
        flag = ""
        if res.total > baseline.total:
            flag = "  <- costs MORE than no compression"
        print(f"  {comp:>12.0%} {res.tool_tokens:>10} {res.recovery_tokens:>10} "
              f"{res.recoveries:>7} {res.total:>8}{flag}")

    print("-" * 68)
    print("  Light compression (<=50%) only trims noise -> total drops.")
    print("  Past the threshold, compressing NEEDED output triggers recovery")
    print("  (reopen original + carry context), and the TOTAL climbs back up.")
    print("  This is GitHub's 'saved tokens locally, spent more globally'.")
    print("=" * 68)


if __name__ == "__main__":
    main()

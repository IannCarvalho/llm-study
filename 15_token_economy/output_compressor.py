"""
15_token_economy/output_compressor.py — A didactic, RTK-style output compressor.

This is a Python teaching reimplementation of the idea behind RTK (the Rust
Token Killer, https://github.com/rtk-ai/rtk): shorten the captured output of
common dev commands before it reaches the model's context, while keeping a way
to recover the original.

It deliberately follows the *selective* policy GitHub described after evaluating
RTK on Copilot (https://github.blog/ai-and-ml/github-copilot/how-we-make-ai-coding-more-cost-efficient-without-sacrificing-task-quality/):

1. **Preserve source-like / arbitrary output.** ``cat``, ``git diff``,
   ``git show`` and arbitrary scripts are returned UNCHANGED — compressing them
   made the model reopen the original.
2. **Reorganize search results without dropping content.** ``grep`` matches are
   grouped by file; every matched line is retained.
3. **Compress repetitive noise selectively.** ``pytest``, ``git status``,
   ``git log``, ``ls``, ``ruff check`` output is reduced (failures only, group,
   deduplicate) and the reduction is kept ONLY when the saving is substantial.

Every compression keeps the full original behind a recovery pointer, mirroring
RTK's recovery path and GitHub's finding that a recovery path is both a safety
net and an evaluation signal. :func:`compress` returns a :class:`Compressed`
whose ``.recover()`` hands back the exact original bytes.

Token estimates use :func:`token_budget.estimate_tokens` (``bytes / 4``). The
module is deterministic and offline; nothing runs on import.
"""

from __future__ import annotations

import re
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module

# token_budget lives in this same digit-prefixed package, which cannot be
# imported with a plain ``import`` statement, so load it by module path.
_token_budget = import_module("15_token_economy.token_budget")
estimate_tokens = _token_budget.estimate_tokens

# Minimum fraction of tokens that must be removed for a noise-compression to be
# kept. GitHub's policy compresses repetitive noise "only when the savings are
# substantial"; below this the original is returned unchanged.
_SUBSTANTIAL_SAVING = 0.15


@dataclass(frozen=True)
class Compressed:
    """The result of compressing one command's output.

    Attributes:
        command: The logical command kind (e.g. ``"pytest"``, ``"git diff"``).
        compressed: The text to put in the model's context.
        original: The full, untouched original — the recovery path.
        strategy: Which policy branch handled it (``preserve`` / ``reorganize``
            / ``compress`` / ``noop``).
    """

    command: str
    compressed: str
    original: str
    strategy: str

    @property
    def original_tokens(self) -> int:
        return estimate_tokens(self.original)

    @property
    def compressed_tokens(self) -> int:
        return estimate_tokens(self.compressed)

    @property
    def saving(self) -> float:
        """Fraction of estimated tokens removed (0.0-1.0)."""
        before = self.original_tokens
        if before == 0:
            return 0.0
        return max(0.0, (before - self.compressed_tokens) / before)

    def recover(self) -> str:
        """Return the exact original output — RTK/GitHub's recovery path."""
        return self.original


# --- source-like commands: preserved verbatim (policy #1) -------------------
_PRESERVE = frozenset({"cat", "read", "git diff", "git show", "script"})


def _compress_pytest(output: str) -> str:
    """Keep failures and the summary; collapse passes to a count (policy #3).

    Mirrors RTK's ``pytest`` filter ("failures only, traceback trimmed"): the
    long run of ``PASSED``/``.`` lines carries almost no information for the
    agent, while ``FAILED`` lines and the final summary carry all of it.
    """
    lines = output.splitlines()
    passed = 0
    kept: list[str] = []
    # A per-test PASSED line, in both the compact ("... PASSED") and the verbose
    # ("tests/x.py::t PASSED [ 18%]") formats. FAILED/ERROR lines never match,
    # so they are always kept.
    passed_line = re.compile(r"\bPASSED\b")
    for line in lines:
        stripped = line.strip()
        # Collapse per-test PASSED lines and the bare-dot progress line.
        if passed_line.search(stripped) or re.fullmatch(r"[.\s]+", stripped):
            passed += 1
            continue
        kept.append(line)
    header = f"[compressed pytest: {passed} passing line(s) collapsed]"
    return header + "\n" + "\n".join(kept)


def _compress_git_status(output: str) -> str:
    """Group porcelain status lines by their state code (policy #3).

    RTK renders ``git status`` as a "compact stat format, grouped by state".
    Expects ``git status --porcelain`` style (``XY path``) lines.
    """
    groups: OrderedDict[str, list[str]] = OrderedDict()
    other: list[str] = []
    for line in output.splitlines():
        m = re.match(r"^([ MADRCU?!]{1,2})\s+(.*)$", line)
        if m:
            code, path = m.group(1).strip() or "??", m.group(2)
            groups.setdefault(code, []).append(path)
        elif line.strip():
            other.append(line)
    out: list[str] = []
    for code, paths in groups.items():
        out.append(f"{code} ({len(paths)}): " + ", ".join(paths))
    out.extend(other)
    return "\n".join(out)


def _compress_git_log(output: str) -> str:
    """Keep hash + subject per commit, drop body/date noise (policy #3).

    RTK's ``git log`` filter keeps "hash, author and subject only". This reduces
    a verbose ``git log`` to one line per commit where it can detect them.
    """
    commits: list[str] = []
    cur_hash: str | None = None
    cur_author: str | None = None
    for line in output.splitlines():
        m = re.match(r"^commit ([0-9a-f]{7,40})", line)
        if m:
            cur_hash, cur_author = m.group(1)[:9], None
            continue
        a = re.match(r"^Author:\s*(.+?)\s*<", line)
        if a:
            cur_author = a.group(1)
            continue
        if cur_hash and line.startswith("    ") and line.strip():
            subject = line.strip()
            who = f" {cur_author}" if cur_author else ""
            commits.append(f"{cur_hash}{who}: {subject}")
            cur_hash = None
    return "\n".join(commits)


def _compress_ls(output: str) -> str:
    """Summarize a long listing by extension counts (policy #3).

    RTK renders ``ls``/``tree`` as counts instead of one line per entry. Here we
    group the entries by file extension and report counts.
    """
    entries = [e for e in re.split(r"\s+", output.strip()) if e]
    counts: OrderedDict[str, int] = OrderedDict()
    for e in entries:
        ext = e.rsplit(".", 1)[-1] if "." in e and not e.endswith("/") else "(dir/other)"
        counts[ext] = counts.get(ext, 0) + 1
    parts = [f"{n} .{ext}" if ext != "(dir/other)" else f"{n} dir/other"
             for ext, n in counts.items()]
    return f"[{len(entries)} entries] " + ", ".join(parts)


def _compress_ruff(output: str) -> str:
    """Group ruff findings by rule code (policy #3).

    RTK renders ``ruff check`` "grouped by rule and file". Lines look like
    ``path:line:col: CODE message``; we group by CODE and count.
    """
    groups: OrderedDict[str, list[str]] = OrderedDict()
    tail: list[str] = []
    for line in output.splitlines():
        m = re.search(r":\d+:\d+:\s+([A-Z]+\d+)\s", line)
        if m:
            groups.setdefault(m.group(1), []).append(line.strip())
        elif line.strip().startswith("Found") or line.strip().startswith("["):
            tail.append(line.strip())
    out = [f"{code} ({len(items)}): {items[0]}" + (" ..." if len(items) > 1 else "")
           for code, items in groups.items()]
    out.extend(tail)
    return "\n".join(out)


def _reorganize_grep(output: str) -> str:
    """Group grep matches by file WITHOUT dropping any match (policy #2).

    This is the lossless branch: every matched line is retained, only regrouped
    under its file header so repeated file paths are not repeated per line.
    Expects ``grep -n`` style ``path:line:text``.
    """
    by_file: OrderedDict[str, list[str]] = OrderedDict()
    passthrough: list[str] = []
    for line in output.splitlines():
        m = re.match(r"^(.*?):(\d+):(.*)$", line)
        if m:
            path, lineno, text = m.group(1), m.group(2), m.group(3)
            by_file.setdefault(path, []).append(f"  {lineno}:{text}")
        elif line.strip():
            passthrough.append(line)
    out: list[str] = []
    for path, matches in by_file.items():
        out.append(f"{path} ({len(matches)}):")
        out.extend(matches)
    out.extend(passthrough)
    return "\n".join(out)


# Which compressor handles each lossy-but-selective command (policy #3).
_NOISE_COMPRESSORS: dict[str, Callable[[str], str]] = {
    "pytest": _compress_pytest,
    "git status": _compress_git_status,
    "git log": _compress_git_log,
    "ls": _compress_ls,
    "ruff check": _compress_ruff,
}


def compress(command: str, output: str) -> Compressed:
    """Compress one command's ``output`` under the selective policy.

    Dispatch:
      - a source-like / arbitrary command (``cat``, ``git diff``, ``git show``,
        ``script``) is returned UNCHANGED (``strategy="preserve"``);
      - ``grep`` is regrouped losslessly (``strategy="reorganize"``);
      - a known noisy command is compressed, but the reduction is KEPT only when
        it removes at least ``_SUBSTANTIAL_SAVING`` of the estimated tokens —
        otherwise the original is returned (``strategy="compress"`` vs
        ``"noop"``);
      - anything else is passed through unchanged (``strategy="noop"``).

    The returned :class:`Compressed` always carries the full ``original`` for
    recovery.
    """
    if command in _PRESERVE:
        return Compressed(command, output, output, "preserve")

    if command == "grep":
        reorganized = _reorganize_grep(output)
        return Compressed(command, reorganized, output, "reorganize")

    compressor = _NOISE_COMPRESSORS.get(command)
    if compressor is None:
        return Compressed(command, output, output, "noop")

    candidate = compressor(output)
    trial = Compressed(command, candidate, output, "compress")
    # Keep the compression only if it saved a substantial fraction of tokens.
    if trial.saving >= _SUBSTANTIAL_SAVING:
        return trial
    return Compressed(command, output, output, "noop")


def main() -> None:
    """Narrate compression of a few captured sample outputs with recovery."""
    from pathlib import Path

    samples_dir = Path(__file__).parent / "samples"
    cases = [
        ("pytest", "pytest_verbose.txt"),
        ("git status", "git_status.txt"),
        ("git log", "git_log.txt"),
        ("ruff check", "ruff_check.txt"),
        ("grep", "grep_matches.txt"),
        ("git diff", "git_diff.txt"),
    ]

    print("=" * 64)
    print("Output compressor — RTK-style, GitHub selective policy")
    print("=" * 64)

    for command, filename in cases:
        path = samples_dir / filename
        if not path.exists():
            print(f"  (missing sample: {filename})")
            continue
        original = path.read_text(encoding="utf-8")
        result = compress(command, original)
        print(
            f"  {command:<12} strategy={result.strategy:<10} "
            f"{result.original_tokens:>4} -> {result.compressed_tokens:>4} tok "
            f"(saved {result.saving:.0%})"
        )
        # Prove the recovery path returns the exact original.
        assert result.recover() == original
    print("-" * 64)
    print("  source-like output (git diff) is preserved; recovery returns the")
    print("  exact original for every case (asserted above).")
    print("=" * 64)


if __name__ == "__main__":
    main()

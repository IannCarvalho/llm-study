"""
Deterministic tests for 15_token_economy.

All offline: no network, no LLM, no model download. The modules are loaded with
conftest.load_module because the package is digit-prefixed (``15_token_economy``)
and cannot be imported with a plain ``import`` statement.
"""

from conftest import load_module

token_budget = load_module("15_token_economy/token_budget.py", "token_budget")
# output_compressor and task_cost_sim import token_budget via import_module, so
# the alias above must be registered first (it is, by load order).
output_compressor = load_module("15_token_economy/output_compressor.py", "output_compressor")
task_cost_sim = load_module("15_token_economy/task_cost_sim.py", "task_cost_sim")


# ---------------------------------------------------------------------------
# estimate_tokens
# ---------------------------------------------------------------------------
def test_estimate_tokens_empty_is_zero():
    assert token_budget.estimate_tokens("") == 0


def test_estimate_tokens_bytes_over_four_rounds_up():
    # 5 ASCII bytes -> ceil(5/4) == 2.
    assert token_budget.estimate_tokens("hello") == 2
    # 8 ASCII bytes -> exactly 2.
    assert token_budget.estimate_tokens("hihihihi") == 2


def test_estimate_tokens_counts_utf8_bytes_not_characters():
    # A multi-byte character costs by its UTF-8 byte length, not 1.
    assert token_budget.estimate_tokens("\u00e9") == token_budget.estimate_tokens("\u00e9")
    # "ação" is 6 UTF-8 bytes (a + c-cedilha(2) + a-tilde(2) + o) -> ceil(6/4)=2.
    assert token_budget.estimate_tokens("ação") == 2


def test_estimate_tokens_missing_tiktoken_falls_back_not_raises():
    # use_tiktoken=True must never raise even if tiktoken is absent; it degrades
    # to the heuristic and returns a positive estimate.
    n = token_budget.estimate_tokens("some text here", use_tiktoken=True)
    assert n > 0


# ---------------------------------------------------------------------------
# RequestAnatomy / budget
# ---------------------------------------------------------------------------
def test_anatomy_totals_and_fractions():
    a = token_budget.RequestAnatomy(
        system_prompt=10, history=20, rag_context=30, tool_output=40, model_output=50
    )
    assert a.input_tokens == 100
    assert a.output_tokens == 50
    assert a.total == 150
    fr = a.fractions()
    assert abs(sum(fr.values()) - 1.0) < 1e-9
    assert abs(fr["tool_output"] - (40 / 150)) < 1e-9


def test_anatomy_fractions_zero_total_is_all_zero():
    a = token_budget.RequestAnatomy(0, 0, 0, 0, 0)
    assert a.total == 0
    assert all(v == 0.0 for v in a.fractions().values())


def test_reasoning_output_counts_as_output():
    a = token_budget.RequestAnatomy(
        system_prompt=0, history=0, rag_context=0, tool_output=0,
        model_output=10, reasoning_output=15,
    )
    assert a.output_tokens == 25
    assert a.input_tokens == 0


def test_sample_rag_anatomy_uses_real_repo_data():
    # Built from utils.prompts + utils.data_loader; all parts are populated and
    # the total is the sum of the parts.
    a = token_budget.sample_rag_anatomy(top_k=3)
    assert a.system_prompt > 0
    assert a.rag_context > 0
    assert a.total == a.input_tokens + a.output_tokens


def test_budget_fits_and_overflow():
    a = token_budget.RequestAnatomy(
        system_prompt=100, history=100, rag_context=100, tool_output=100,
        model_output=100,
    )
    # input=400, output=100
    ok = token_budget.RequestBudget(max_input_tokens=400, max_output_tokens=100)
    assert ok.check(a).fits

    tight = token_budget.RequestBudget(max_input_tokens=300, max_output_tokens=50)
    report = tight.check(a)
    assert not report.fits
    assert report.input_over == 100
    assert report.output_over == 50


# ---------------------------------------------------------------------------
# RateLimiter (deterministic, injected clock)
# ---------------------------------------------------------------------------
def test_rate_limiter_burst_then_denies():
    now = {"t": 0.0}
    rl = token_budget.RateLimiter(capacity=2, refill_per_sec=1.0, clock=lambda: now["t"])
    assert rl.allow(1) is True
    assert rl.allow(1) is True
    assert rl.allow(1) is False  # bucket empty, no time has passed


def test_rate_limiter_refills_over_time():
    now = {"t": 0.0}
    rl = token_budget.RateLimiter(capacity=2, refill_per_sec=1.0, clock=lambda: now["t"])
    rl.allow(2)  # drain
    assert rl.allow(1) is False
    now["t"] = 1.0  # one second -> one token
    assert rl.allow(1) is True


def test_rate_limiter_capacity_caps_refill():
    now = {"t": 0.0}
    rl = token_budget.RateLimiter(capacity=2, refill_per_sec=10.0, clock=lambda: now["t"])
    rl.allow(2)  # drain to 0
    now["t"] = 100.0  # huge wait, but capacity caps at 2
    assert rl.available == 2.0


def test_rate_limiter_denied_request_removes_nothing():
    now = {"t": 0.0}
    rl = token_budget.RateLimiter(capacity=2, refill_per_sec=0.0, clock=lambda: now["t"])
    assert rl.allow(5) is False  # too big
    assert rl.allow(2) is True   # full bucket still intact


def test_rate_limiter_rejects_bad_config():
    import pytest

    with pytest.raises(ValueError):
        token_budget.RateLimiter(capacity=0, refill_per_sec=1.0)
    with pytest.raises(ValueError):
        token_budget.RateLimiter(capacity=1, refill_per_sec=-1.0)


# ---------------------------------------------------------------------------
# output_compressor — selective policy + recovery path
# ---------------------------------------------------------------------------
def test_preserve_source_like_output_unchanged():
    diff = "diff --git a/x b/x\n@@ -1 +1 @@\n-old\n+new\n"
    r = output_compressor.compress("git diff", diff)
    assert r.strategy == "preserve"
    assert r.compressed == diff
    assert r.recover() == diff


def test_grep_reorganized_is_lossless():
    grep = (
        "a.py:1:def foo():\n"
        "a.py:2:    return 1\n"
        "b.py:9:def bar():\n"
    )
    r = output_compressor.compress("grep", grep)
    assert r.strategy == "reorganize"
    # Every matched line number/text is still present.
    assert "1:def foo():" in r.compressed
    assert "2:    return 1" in r.compressed
    assert "9:def bar():" in r.compressed
    # Grouped under file headers.
    assert "a.py (2):" in r.compressed
    assert "b.py (1):" in r.compressed
    assert r.recover() == grep


def test_pytest_compresses_passes_to_count():
    lines = [f"tests/test_x.py::t{i} PASSED" for i in range(40)]
    lines.append("tests/test_x.py::t_bad FAILED")
    lines.append("=== 40 passed, 1 failed in 1.0s ===")
    output = "\n".join(lines)
    r = output_compressor.compress("pytest", output)
    assert r.strategy == "compress"
    assert r.saving > 0.0
    # The failure and summary survive; the passing lines are collapsed.
    assert "FAILED" in r.compressed
    assert "40 passed" in r.compressed
    assert "PASSED" not in r.compressed
    assert r.recover() == output


def test_noop_when_saving_not_substantial():
    # A pytest output that is almost all failures compresses little, so the
    # policy keeps the original (strategy "noop") rather than a tiny win.
    output = "\n".join(f"tests/test_x.py::t{i} FAILED" for i in range(20))
    r = output_compressor.compress("pytest", output)
    assert r.strategy == "noop"
    assert r.compressed == output


def test_unknown_command_passes_through():
    r = output_compressor.compress("some-random-cmd", "arbitrary output\n")
    assert r.strategy == "noop"
    assert r.recover() == "arbitrary output\n"


def test_git_status_grouped_by_state():
    status = " M a.py\n M b.py\n?? c.txt\nA  d.py\n"
    r = output_compressor.compress("git status", status)
    # Grouping keeps every path; recovery is exact.
    assert "a.py" in r.compressed and "b.py" in r.compressed
    assert "c.txt" in r.compressed and "d.py" in r.compressed
    assert r.recover() == status


# ---------------------------------------------------------------------------
# task_cost_sim — per-call vs per-task
# ---------------------------------------------------------------------------
def test_light_compression_lowers_total():
    calls = task_cost_sim._default_task()
    base = task_cost_sim.simulate_task(calls, compression=0.0, carried_context=800)
    light = task_cost_sim.simulate_task(calls, compression=0.3, carried_context=800)
    assert light.recoveries == 0
    assert light.total < base.total


def test_aggressive_compression_triggers_recovery_and_raises_total():
    calls = task_cost_sim._default_task()
    base = task_cost_sim.simulate_task(calls, compression=0.0, carried_context=800)
    aggressive = task_cost_sim.simulate_task(calls, compression=0.9, carried_context=800)
    # Needed calls were cut past the threshold -> recoveries happen.
    assert aggressive.recoveries > 0
    assert aggressive.recovery_tokens > 0
    # And the whole task ends up MORE expensive than no compression at all.
    assert aggressive.total > base.total


def test_simulate_task_rejects_bad_compression():
    import pytest

    with pytest.raises(ValueError):
        task_cost_sim.simulate_task([], compression=1.5, carried_context=0)

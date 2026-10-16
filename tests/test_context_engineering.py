"""
Deterministic tests for 17_context_engineering/context_distraction.py.

Everything here is offline: no network, no model download, no LLM. The module's
core (distractor generation, context building, size measurement, and the four
strategies) is pure and uses only the "bm25" search engine, so it runs under the
golden rule unchanged. The optional LLM comparison step is never called from the
tests.
"""

from conftest import load_module

ctx = load_module("17_context_engineering/context_distraction.py", "context_distraction")

from utils.data_loader import load_cves


# ---------------------------------------------------------------------------
# ContextBundle measurement
# ---------------------------------------------------------------------------
def test_context_bundle_measures_chars_and_tokens():
    bundle = ctx.ContextBundle(label="x", text="abcd" * 4, evidence_present=True)
    assert bundle.chars == 16
    # bytes/4 estimate: 16 ascii bytes -> 4 estimated tokens.
    assert bundle.est_tokens == 4


# ---------------------------------------------------------------------------
# Synthetic distractors: deterministic + clearly tagged
# ---------------------------------------------------------------------------
def test_distractors_are_deterministic():
    cves = load_cves()
    a = ctx.make_synthetic_distractors(cves, count=10)
    b = ctx.make_synthetic_distractors(cves, count=10)
    assert a == b  # same seed -> identical output every run


def test_distractors_count_and_tagging():
    cves = load_cves()
    distractors = ctx.make_synthetic_distractors(cves, count=12)
    assert len(distractors) == 12
    # Every synthetic block is clearly marked so it can't be mistaken for truth.
    assert all(ctx.SYNTHETIC_TAG in block for block in distractors)


def test_distractors_empty_when_no_real_cves():
    assert ctx.make_synthetic_distractors([], count=5) == []


# ---------------------------------------------------------------------------
# Context building: focused vs inflated, evidence at start/middle/end
# ---------------------------------------------------------------------------
def test_inflated_context_is_larger_and_keeps_evidence():
    cves = load_cves()
    target = cves[0]
    distractors = ctx.make_synthetic_distractors(cves, count=20)
    focused = ctx.build_focused_context(target)
    inflated = ctx.build_inflated_context(target, distractors)

    assert inflated.est_tokens > focused.est_tokens
    assert focused.evidence_present and inflated.evidence_present
    # The target BLOCK (its "CVE ID:" header line) appears three times: start,
    # middle, end. The bare id string also appears inside distractors (which say
    # they are "derived from <id>"), so count the header line, not the id alone.
    assert inflated.text.count(f"CVE ID: {target.id}") == 3


# ---------------------------------------------------------------------------
# SELECT: bm25 top-k pulls the real CVE out of the noise
# ---------------------------------------------------------------------------
def test_strategy_select_recovers_target_and_shrinks():
    cves = load_cves()
    target = cves[0]
    distractors = ctx.make_synthetic_distractors(cves, count=30)
    inflated = ctx.build_inflated_context(target, distractors)

    docs = [{"id": target.id, "content": ctx.cve_block(target), "metadata": {}}]
    for i, block in enumerate(distractors):
        docs.append({"id": f"SYN-{i}", "content": block, "metadata": {}})

    question = f"What is the severity of {target.id}?"
    selected = ctx.strategy_select(question, docs, top_k=3)

    assert selected.evidence_present
    assert target.id in selected.text
    assert selected.est_tokens < inflated.est_tokens


# ---------------------------------------------------------------------------
# COMPRESS: keeps relevant sentences, drops the rest
# ---------------------------------------------------------------------------
def test_strategy_compress_shrinks_and_keeps_evidence():
    cves = load_cves()
    target = cves[0]
    distractors = ctx.make_synthetic_distractors(cves, count=30)
    inflated = ctx.build_inflated_context(target, distractors)

    question = f"What is the severity of {target.id} and what does it allow?"
    compressed = ctx.strategy_compress(question, inflated.text)

    assert compressed.est_tokens < inflated.est_tokens
    assert compressed.evidence_present
    assert target.id in compressed.text


# ---------------------------------------------------------------------------
# ISOLATE: one sub-context per sub-question
# ---------------------------------------------------------------------------
def test_strategy_isolate_builds_one_bundle_per_subquestion():
    cves = load_cves()
    target = cves[0]
    distractors = ctx.make_synthetic_distractors(cves, count=20)

    docs = [{"id": target.id, "content": ctx.cve_block(target), "metadata": {}}]
    for i, block in enumerate(distractors):
        docs.append({"id": f"SYN-{i}", "content": block, "metadata": {}})

    subs = [f"severity of {target.id}", f"what does {target.id} allow"]
    bundles = ctx.strategy_isolate(subs, docs, top_k=2)

    assert set(bundles.keys()) == set(subs)
    assert all(isinstance(b, ctx.ContextBundle) for b in bundles.values())


# ---------------------------------------------------------------------------
# WRITE: scratchpad distillation kept outside the window
# ---------------------------------------------------------------------------
def test_write_scratchpad_is_small_and_grounded():
    cves = load_cves()
    target = cves[0]
    inflated = ctx.build_inflated_context(
        target, ctx.make_synthetic_distractors(cves, count=30)
    )

    pad = ctx.distill_to_scratchpad(target)
    bundle = pad.as_bundle()

    assert bundle.evidence_present
    assert target.id in bundle.text
    # The whole point of WRITE: the notes are far smaller than the raw context.
    assert bundle.est_tokens < inflated.est_tokens
    assert len(pad.notes) >= 2


def test_scratchpad_write_appends_notes():
    pad = ctx.Scratchpad()
    pad.write("first")
    pad.write("second")
    assert pad.notes == ["first", "second"]
    assert "- first" in pad.render()

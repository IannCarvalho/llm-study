"""
Deterministic tests for 16_decision_models.

Everything here is offline: no LLM, no network, and NO embedding-model download.
The decision model takes an injectable embedder, so every test passes a tiny
FAKE deterministic embedder (a bag-of-words hash into a fixed-dim vector). That
exercises the real decision logic -- cosine similarity, temperature softmax,
Jev-compatible confidence, routing and composition -- with reproducible numbers.

The sibling modules live in a digit-prefixed package, so we register them with
conftest.load_module under bare aliases; calibration/routing then reuse the
already-registered ``decision_model`` object instead of re-loading it.
"""

import json
import zlib
from pathlib import Path

import numpy as np
import pytest
from conftest import load_module

# load decision_model FIRST so calibration/routing reuse the same object.
dm = load_module("16_decision_models/decision_model.py", "decision_model")
calib = load_module("16_decision_models/calibration.py", "calibration")
routing = load_module("16_decision_models/routing.py", "routing")

from utils.models import SeverityLevel, VulnerabilityType  # noqa: E402


# ---------------------------------------------------------------------------
# Fake deterministic embedder (no model download)
# ---------------------------------------------------------------------------
def make_fake_embedder(dim: int = 32):
    """Bag-of-words hash embedder: identical text -> identical vector."""

    def embed(texts):
        out = np.zeros((len(texts), dim), dtype=np.float64)
        for r, text in enumerate(texts):
            for tok in str(text).lower().split():
                # crc32, not hash(): str hashing is salted per process.
                out[r, zlib.crc32(tok.encode("utf-8")) % dim] += 1.0
        return out

    return embed


# ---------------------------------------------------------------------------
# softmax
# ---------------------------------------------------------------------------
def test_softmax_sums_to_one_and_orders():
    probs = dm.softmax(np.array([2.0, 1.0, 0.0]))
    assert probs == pytest.approx(probs)  # finite
    assert sum(probs) == pytest.approx(1.0)
    assert probs[0] > probs[1] > probs[2]


def test_softmax_temperature_flattens():
    logits = np.array([3.0, 0.0, 0.0])
    sharp = dm.softmax(logits, temperature=0.5)
    flat = dm.softmax(logits, temperature=5.0)
    # Higher temperature -> lower peak probability (flatter).
    assert max(sharp) > max(flat)


def test_softmax_rejects_nonpositive_temperature():
    with pytest.raises(ValueError):
        dm.softmax(np.array([1.0, 2.0]), temperature=0.0)


# ---------------------------------------------------------------------------
# confidence formulas (match Jev's documented formulas)
# ---------------------------------------------------------------------------
def test_choice_confidence_bounds():
    assert dm.choice_confidence([1.0, 0.0, 0.0]) == pytest.approx(1.0)
    assert dm.choice_confidence([1 / 3, 1 / 3, 1 / 3]) == pytest.approx(0.0)


def test_choice_confidence_only_top_counts():
    # (0.6,0.3,0.1) and (0.6,0.2,0.2) both -> (3*0.6-1)/2 = 0.4
    assert dm.choice_confidence([0.6, 0.3, 0.1]) == pytest.approx(0.4)
    assert dm.choice_confidence([0.6, 0.2, 0.2]) == pytest.approx(0.4)


def test_score_confidence_neighbor_vs_ends():
    # Documented: three levels, torn between neighbours -> 0.25; between ends -> 0.
    assert dm.score_confidence([0.0, 0.5, 0.5]) == pytest.approx(0.25)
    assert dm.score_confidence([0.5, 0.0, 0.5]) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# DecisionModel: Choice / Score / Noul
# ---------------------------------------------------------------------------
def _model():
    return dm.DecisionModel(embedder=make_fake_embedder(), temperature=1.0)


def test_choice_picks_matching_option():
    model = _model()
    q = dm.Choice(
        instructions="severity",
        options={
            "CRITICAL": "critical remote code execution full compromise",
            "LOW": "low minor information disclosure",
        },
    )
    ans = model.ask_choice("critical remote code execution full compromise", q)
    assert isinstance(ans, dm.ChoiceAnswer)
    assert ans.choice == "CRITICAL"
    assert ans.probabilities["CRITICAL"] > ans.probabilities["LOW"]
    assert sum(ans.probabilities.values()) == pytest.approx(1.0)
    assert 0.0 <= ans.confidence <= 1.0


def test_score_returns_weighted_value_and_legend():
    model = _model()
    q = dm.Score(instructions="detail", levels=["none", "some", "thorough"])
    ans = model.ask_score("thorough detail everywhere", q)
    assert isinstance(ans, dm.ScoreAnswer)
    assert set(ans.legend) == {"0", "1", "2"}
    assert 0.0 <= ans.score <= 2.0
    assert sum(ans.probabilities.values()) == pytest.approx(1.0)


def test_noul_returns_probability_in_unit_interval():
    model = _model()
    q = dm.Noul(instructions="remote network exploit", yes="remote network exploit",
                no="local only physical access")
    ans = model.ask_noul("remote network exploit over the internet", q)
    assert isinstance(ans, dm.NoulAnswer)
    assert 0.0 <= ans.noul <= 1.0
    # The 'yes' prototype matches the state better than 'no'.
    assert ans.noul > 0.5


def test_ask_batches_mixed_questions_against_one_state():
    model = _model()
    answers = model.ask(
        "remote code execution full compromise",
        {
            "sev": dm.Choice(instructions="severity",
                             options={"CRITICAL": "critical remote code execution",
                                      "LOW": "low minor issue"}),
            "detail": dm.Score(instructions="detail", levels=["none", "lots"]),
            "remote": dm.Noul(instructions="remote exploit"),
        },
    )
    assert set(answers) == {"sev", "detail", "remote"}
    assert isinstance(answers["sev"], dm.ChoiceAnswer)
    assert isinstance(answers["detail"], dm.ScoreAnswer)
    assert isinstance(answers["remote"], dm.NoulAnswer)


def test_default_embedder_is_not_invoked_without_a_call():
    # Constructing the model must NOT load sentence-transformers.
    model = dm.DecisionModel()
    assert callable(model.embedder)


# ---------------------------------------------------------------------------
# calibration
# ---------------------------------------------------------------------------
def test_brier_perfect_and_worst():
    assert calib.brier_score([1.0, 1.0], [True, True]) == pytest.approx(0.0)
    assert calib.brier_score([1.0, 0.0], [False, True]) == pytest.approx(1.0)


def test_reliability_table_bins_and_accuracy():
    confs = [0.95, 0.92, 0.1, 0.15]
    correct = [True, True, False, True]
    bins = calib.reliability_table(confs, correct, n_bins=10)
    # Two populated bins: ~0.9 (both right) and ~0.1 (one of two right).
    high = [b for b in bins if b.low >= 0.9][0]
    assert high.count == 2
    assert high.accuracy == pytest.approx(1.0)


def test_ece_zero_when_perfectly_calibrated():
    # Confidence 1.0 and always correct -> no gap.
    ece = calib.expected_calibration_error([1.0, 1.0, 1.0], [True, True, True])
    assert ece == pytest.approx(0.0)


def test_fit_temperature_softens_overconfident_logits():
    # Large-magnitude logits whose argmax is often WRONG -> softening (t>1) helps.
    rng = np.random.default_rng(0)
    logits, truth = [], []
    for _ in range(200):
        t = int(rng.integers(3))
        base = rng.normal(0, 1.0, size=3) * 4.0  # inflated -> overconfident
        base[t] += 2.0
        logits.append(base.tolist())
        truth.append(t)
    best = calib.fit_temperature(logits, truth)
    assert best >= 1.0


def test_fit_temperature_empty_defaults_to_one():
    assert calib.fit_temperature([], []) == 1.0


# ---------------------------------------------------------------------------
# routing
# ---------------------------------------------------------------------------
def _choice_answer(choice, probs, conf):
    return dm.ChoiceAnswer(choice=choice, probabilities=probs, confidence=conf)


def test_gate_choice_acts_above_threshold():
    ans = _choice_answer("CRITICAL", {"CRITICAL": 0.9, "LOW": 0.1}, 0.8)
    decision = routing.gate_choice(ans, threshold=0.5)
    assert decision.route is routing.Route.ACT
    assert decision.label == "CRITICAL"


def test_gate_choice_escalates_below_threshold():
    ans = _choice_answer("CRITICAL", {"CRITICAL": 0.4, "LOW": 0.3, "MED": 0.3}, 0.1)
    decision = routing.gate_choice(ans, threshold=0.5)
    assert decision.route is routing.Route.ESCALATE


def test_gate_noul_fence_escalates():
    on_fence = routing.gate_noul(0.52, threshold=0.5, margin=0.2)
    assert on_fence.route is routing.Route.ESCALATE
    confident_yes = routing.gate_noul(0.95, threshold=0.5, margin=0.2)
    assert confident_yes.route is routing.Route.ACT
    assert confident_yes.label == "yes"


def test_coverage_accuracy_curve_monotonic_coverage():
    answers = [
        _choice_answer("A", {"A": 0.9, "B": 0.1}, 0.9),
        _choice_answer("A", {"A": 0.6, "B": 0.4}, 0.5),
        _choice_answer("B", {"A": 0.45, "B": 0.55}, 0.1),  # wrong vs truth
    ]
    truths = ["A", "A", "A"]
    curve = routing.coverage_accuracy_curve(answers, truths, thresholds=[0.0, 0.3, 0.7])
    coverages = [p.coverage for p in curve]
    # Coverage never increases as the threshold rises.
    assert coverages == sorted(coverages, reverse=True)
    # At the strictest threshold only the high-confidence correct one is acted on.
    assert curve[-1].accuracy == pytest.approx(1.0)


def test_composite_score_normalizes_weights():
    readings = {"a": 1.0, "b": 0.0}
    # Weights need not sum to 1; only relative size matters.
    assert routing.composite_score(readings, {"a": 3.0, "b": 1.0}) == pytest.approx(0.75)


def test_composite_score_ignores_missing_and_rejects_empty():
    assert routing.composite_score({"a": 0.5}, {"a": 1.0, "missing": 2.0}) == pytest.approx(0.5)
    with pytest.raises(ValueError):
        routing.composite_score({"a": 0.5}, {"b": 1.0})


# ---------------------------------------------------------------------------
# labeled_cases.json integrity (labels must match the repo enums)
# ---------------------------------------------------------------------------
def test_labeled_cases_valid_against_enums(repo_root: Path):
    path = repo_root / "16_decision_models" / "labeled_cases.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data["cases"]
    assert 24 <= len(cases) <= 40
    ids = set()
    valid_types = {t.value for t in VulnerabilityType}
    valid_sev = {s.value for s in SeverityLevel}
    for c in cases:
        assert c["id"] not in ids, f"duplicate id {c['id']}"
        ids.add(c["id"])
        assert c["text"].strip()
        assert c["type"] in valid_types, f"{c['id']} bad type {c['type']}"
        assert c["severity"] in valid_sev, f"{c['id']} bad severity {c['severity']}"
        assert isinstance(c["remote_exploit"], bool)



# ---------------------------------------------------------------------------
# jev_client: request payload only (never calls the network)
# ---------------------------------------------------------------------------
def test_jev_payload_matches_the_documented_request_shape():
    import importlib

    jev = load_module("16_decision_models/jev_client.py", "jev_client")
    # A second copy of decision_model, loaded the way `python -m` users get it:
    dm_pkg = importlib.import_module("16_decision_models.decision_model")
    questions = {
        "severity": dm.Choice(instructions="How severe", options={"LOW": "minor", "HIGH": "major"}),
        "risk": dm_pkg.Score(instructions="How risky", levels=["low", "medium", "high"]),
        "remote": dm_pkg.Noul(instructions="Is it remotely exploitable?"),
        "raw": {"type": "noul", "instructions": "Passed through untouched"},
    }

    payload = jev._question_payload(questions)

    assert payload["severity"] == {
        "type": "choice", "instructions": "How severe", "criteria": {"LOW": "minor", "HIGH": "major"},
    }
    assert payload["risk"] == {
        "type": "score", "instructions": "How risky", "criteria": ["low", "medium", "high"],
    }
    assert payload["remote"] == {"type": "noul", "instructions": "Is it remotely exploitable?"}
    assert payload["raw"] is questions["raw"]


def test_jev_client_refuses_to_run_without_a_key(monkeypatch):
    jev = load_module("16_decision_models/jev_client.py", "jev_client")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(jev.JevClientError):
        jev.system_one("state", {"q": {"type": "noul", "instructions": "x"}})

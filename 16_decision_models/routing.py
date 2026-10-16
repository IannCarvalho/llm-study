"""
Routing and composition: turning typed answers into system behaviour.

Two patterns from the TypeSafe playbook, both pure code over the typed answers
decision_model.py returns. No LLM and no network.

1. Confidence-gated routing
   The answer tells you WHAT; confidence tells you WHETHER to act. Above a
   threshold the code acts automatically (ACT); below it, it escalates to an
   LLM or a human (ESCALATE). Raising the threshold trades COVERAGE (how often
   you act automatically) for ACCURACY (how often those automatic actions are
   right). ``coverage_accuracy_curve`` sweeps the threshold so you can pick the
   operating point your stakes justify.

2. Composite scoring
   Hard judgments are decomposed into atomic questions the model answers well,
   then recombined in code with weights YOU control -- not folded into one vague
   prompt. ``composite_score`` takes per-question scalar readings and a weight
   map and returns the weighted blend, so the combination rule stays inspectable
   and testable.

Run as a demo from the repo root (PYTHONPATH=.):
    python -m 16_decision_models.routing
"""
from __future__ import annotations

import importlib.util
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


def _load_sibling(module_name: str):
    """Load a sibling module from this digit-prefixed package (see calibration.py)."""
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = Path(__file__).resolve().parent / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load sibling module {module_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_dm = _load_sibling("decision_model")
Choice = _dm.Choice
Score = _dm.Score
Noul = _dm.Noul
DecisionModel = _dm.DecisionModel
ChoiceAnswer = _dm.ChoiceAnswer


class Route(StrEnum):
    """Where a decision goes after the gate."""

    ACT = "act"
    ESCALATE = "escalate"


@dataclass
class RoutingDecision:
    """The outcome of gating one answer."""

    route: Route
    label: str
    confidence: float
    threshold: float


def gate_choice(answer: ChoiceAnswer, threshold: float) -> RoutingDecision:
    """ACT on a Choice answer when its confidence clears the threshold.

    Below the threshold the model is telling you it is not sure enough; escalate
    instead of guessing.
    """
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be in [0, 1]")
    route = Route.ACT if answer.confidence >= threshold else Route.ESCALATE
    return RoutingDecision(
        route=route,
        label=answer.choice,
        confidence=answer.confidence,
        threshold=threshold,
    )


def gate_noul(
    noul: float,
    threshold: float = 0.5,
    margin: float = 0.0,
) -> RoutingDecision:
    """Gate a Noul probability into a yes/no act-or-escalate decision.

    A Noul carries no separate confidence; its certainty IS its distance from
    0.5. Within ``margin`` of 0.5 we escalate (the model is on the fence);
    otherwise we ACT with label "yes"/"no" by comparing against ``threshold``.
    """
    certainty = abs(2.0 * noul - 1.0)  # Jev's Noul-as-Choice confidence
    if certainty < margin:
        return RoutingDecision(Route.ESCALATE, "uncertain", certainty, threshold)
    label = "yes" if noul >= threshold else "no"
    return RoutingDecision(Route.ACT, label, certainty, threshold)


@dataclass
class CoveragePoint:
    """One operating point on the coverage/accuracy curve."""

    threshold: float
    coverage: float  # fraction of items acted on automatically
    accuracy: float  # accuracy AMONG the acted-on items (nan-free: 0 if none)
    acted: int
    total: int


def coverage_accuracy_curve(
    answers: Sequence[ChoiceAnswer],
    truths: Sequence[str],
    thresholds: Sequence[float] | None = None,
) -> list[CoveragePoint]:
    """Sweep the confidence threshold over a labelled set of Choice answers.

    For each threshold, ACT on every answer whose confidence clears it and
    measure how many that covers and how accurate those automatic actions are.
    Higher thresholds act on fewer items but get more of them right -- the curve
    is the evidence for choosing a threshold.
    """
    if len(answers) != len(truths):
        raise ValueError("answers and truths must be the same length")
    if thresholds is None:
        thresholds = [i / 10 for i in range(11)]

    total = len(answers)
    points: list[CoveragePoint] = []
    for t in thresholds:
        acted = [
            (a, truth)
            for a, truth in zip(answers, truths, strict=False)
            if a.confidence >= t
        ]
        n_acted = len(acted)
        n_correct = sum(1 for a, truth in acted if a.choice == truth)
        points.append(
            CoveragePoint(
                threshold=float(t),
                coverage=n_acted / total if total else 0.0,
                accuracy=n_correct / n_acted if n_acted else 0.0,
                acted=n_acted,
                total=total,
            )
        )
    return points


def composite_score(readings: dict[str, float], weights: dict[str, float]) -> float:
    """Combine atomic scalar readings into one score with code-controlled weights.

    ``readings`` maps a question id to a scalar (a Score's value, a Noul's
    probability, a Choice's top probability -- whatever you reduced it to).
    ``weights`` maps the same ids to weights; they are normalised to sum to 1,
    so only their RELATIVE size matters. Ids in ``weights`` but absent from
    ``readings`` are ignored.
    """
    used = {k: w for k, w in weights.items() if k in readings and w != 0.0}
    total_w = sum(abs(w) for w in used.values())
    if total_w == 0.0:
        raise ValueError("no overlapping, non-zero weights to combine")
    return float(sum(readings[k] * (w / total_w) for k, w in used.items()))


def main() -> None:
    """Synthetic demo: gate CVE-severity Choices and build a composite risk score.

    Uses a FAKE deterministic embedder so the demo is offline and reproducible
    (the same trick the tests use): the real embedder is only exercised by
    decision_model.main(). This keeps the routing logic the thing on display.
    """
    import numpy as np

    # A tiny deterministic "embedder": hashes each text into a fixed vector.
    def fake_embedder(texts: Sequence[str]) -> np.ndarray:
        dim = 24
        out = np.zeros((len(texts), dim), dtype=np.float64)
        for r, text in enumerate(texts):
            for tok in text.lower().split():
                out[r, hash(tok) % dim] += 1.0
        return out

    model = DecisionModel(embedder=fake_embedder, temperature=1.0)
    severity = Choice(
        instructions="How severe is this vulnerability",
        options={
            "CRITICAL": "critical remote code execution full system compromise",
            "HIGH": "high impact serious compromise authentication bypass",
            "MEDIUM": "medium limited conditional cross site scripting",
            "LOW": "low minor information disclosure hard to exploit",
        },
    )

    states = [
        ("critical remote code execution full system compromise", "CRITICAL"),
        ("high authentication bypass serious compromise", "HIGH"),
        ("medium cross site scripting conditional", "MEDIUM"),
        ("low minor information disclosure", "LOW"),
        ("some vague unspecified issue", "LOW"),  # deliberately ambiguous
    ]

    print("=" * 70)
    print("Confidence-gated routing over CVE-severity Choices (fake embedder)")
    print("=" * 70)

    answers = [model.ask_choice(s, severity) for s, _ in states]
    truths = [t for _, t in states]

    for (state, truth), ans in zip(states, answers, strict=False):
        decision = gate_choice(ans, threshold=0.4)
        mark = "OK " if ans.choice == truth else "ERR"
        print(
            f"  [{decision.route.value:8s}] pred={ans.choice:8s} true={truth:8s} "
            f"conf={ans.confidence:.2f} {mark}  <- {state[:38]}"
        )

    print("\nCoverage/accuracy as the confidence threshold rises:")
    print(f"{'thr':>5}  {'coverage':>8}  {'accuracy':>8}  acted/total")
    for p in coverage_accuracy_curve(answers, truths):
        print(
            f"  {p.threshold:.1f}  {p.coverage:8.2f}  {p.accuracy:8.2f}  "
            f"{p.acted}/{p.total}"
        )

    print("\nComposite risk score (atomic readings combined in code):")
    readings = {"severity_top_p": answers[0].probabilities[answers[0].choice],
                "remote": 0.9, "exploited_in_wild": 0.3}
    weights = {"severity_top_p": 0.5, "remote": 0.3, "exploited_in_wild": 0.2}
    risk = composite_score(readings, weights)
    for k, w in weights.items():
        print(f"    {k:18s} reading={readings[k]:.2f} weight={w:.2f}")
    print(f"    => composite risk = {risk:.3f}")


if __name__ == "__main__":
    main()

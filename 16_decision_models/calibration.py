"""
Calibration: does a probability of 0.8 actually come true ~80% of the time?

A decision is only as useful as its probabilities are honest. A model that says
"CRITICAL, p=0.95" and is right 60% of the time is *overconfident*: downstream
confidence-gated routing (routing.py) will auto-act on answers it should have
escalated. Calibration measures and corrects that mismatch, with no LLM and no
network.

Metrics
-------
- Brier score: mean squared error between the predicted probability of the
  realised outcome and 1.0. Lower is better (0 = perfect).
- ECE (Expected Calibration Error): bin predictions by confidence, and in each
  bin compare average confidence against observed accuracy. The gap, weighted by
  bin size, is the ECE. Lower is better.
- Reliability table: the per-bin (confidence, accuracy, count) rows ECE sums up,
  useful to SEE whether the miscalibration is over- or under-confidence.

Correction
----------
``fit_temperature`` does a simple 1-D grid search for the softmax temperature
that minimises Brier score on a held-out calibration split. Temperature > 1
softens an overconfident model; < 1 sharpens an underconfident one. It is the
single knob DecisionModel exposes (temperature scaling -- the standard, rank-
preserving post-hoc calibration: it never changes which option wins, only how
confident the probabilities are).

Run as a demo from the repo root (PYTHONPATH=.):
    python -m 16_decision_models.calibration
"""
from __future__ import annotations

import importlib.util
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np


def _load_sibling(module_name: str):
    """Import a sibling module from this digit-prefixed package.

    ``16_decision_models`` cannot be imported with a plain ``import`` (the name
    starts with a digit), so a sibling file is loaded by path. If the tests
    already registered it under its bare alias (via conftest.load_module), reuse
    that so both halves share one module object.
    """
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


softmax = _load_sibling("decision_model").softmax


@dataclass
class ReliabilityBin:
    """One confidence bucket of a reliability table."""

    low: float
    high: float
    count: int
    avg_confidence: float
    accuracy: float

    @property
    def gap(self) -> float:
        """|confidence - accuracy| in this bin (0 == perfectly calibrated)."""
        return abs(self.avg_confidence - self.accuracy)


def brier_score(confidences: Sequence[float], correct: Sequence[bool]) -> float:
    """Mean squared error between confidence and the 0/1 outcome.

    ``confidences[i]`` is the model's probability for the outcome it predicted;
    ``correct[i]`` is whether that prediction was right.
    """
    if len(confidences) != len(correct):
        raise ValueError("confidences and correct must be the same length")
    if not confidences:
        return 0.0
    conf = np.asarray(confidences, dtype=np.float64)
    hit = np.asarray(correct, dtype=np.float64)
    return float(np.mean((conf - hit) ** 2))


def reliability_table(
    confidences: Sequence[float],
    correct: Sequence[bool],
    n_bins: int = 10,
) -> list[ReliabilityBin]:
    """Group predictions into equal-width confidence bins.

    Returns one :class:`ReliabilityBin` per non-empty bin, lowest first.
    """
    if len(confidences) != len(correct):
        raise ValueError("confidences and correct must be the same length")
    if n_bins < 1:
        raise ValueError("n_bins must be >= 1")

    conf = np.asarray(confidences, dtype=np.float64)
    hit = np.asarray(correct, dtype=np.float64)
    edges = np.linspace(0.0, 1.0, n_bins + 1)

    bins: list[ReliabilityBin] = []
    for b in range(n_bins):
        low, high = edges[b], edges[b + 1]
        # Last bin is closed on the right so confidence == 1.0 lands somewhere.
        mask = (
            (conf >= low) & (conf <= high)
            if b == n_bins - 1
            else (conf >= low) & (conf < high)
        )
        count = int(mask.sum())
        if count == 0:
            continue
        bins.append(
            ReliabilityBin(
                low=float(low),
                high=float(high),
                count=count,
                avg_confidence=float(conf[mask].mean()),
                accuracy=float(hit[mask].mean()),
            )
        )
    return bins


def expected_calibration_error(
    confidences: Sequence[float],
    correct: Sequence[bool],
    n_bins: int = 10,
) -> float:
    """Size-weighted mean gap between confidence and accuracy across bins."""
    total = len(confidences)
    if total == 0:
        return 0.0
    bins = reliability_table(confidences, correct, n_bins=n_bins)
    return float(sum(b.count / total * b.gap for b in bins))


def fit_temperature(
    logits_per_item: Sequence[Sequence[float]],
    correct_index: Sequence[int],
    candidates: Sequence[float] | None = None,
) -> float:
    """Grid-search the softmax temperature that minimises Brier score.

    Args:
        logits_per_item: for each calibration item, the raw (pre-softmax)
            similarity logits across its options/levels.
        correct_index: the index of the TRUE option/level for each item.
        candidates: temperatures to try. Defaults to a log-spaced-ish grid.

    Returns:
        The best temperature found. ``> 1`` softens an overconfident model.
    """
    if len(logits_per_item) != len(correct_index):
        raise ValueError("logits_per_item and correct_index must align")
    if not logits_per_item:
        return 1.0
    if candidates is None:
        candidates = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 8.0]

    best_t, best_brier = 1.0, float("inf")
    for t in candidates:
        confs: list[float] = []
        hits: list[bool] = []
        for logits, true_idx in zip(logits_per_item, correct_index, strict=False):
            probs = softmax(np.asarray(logits, dtype=np.float64), temperature=t)
            pred_idx = int(np.argmax(probs))
            # Confidence in the predicted class is the honest number to grade:
            # Brier then rewards a probability that matches whether it was right.
            confs.append(float(probs[pred_idx]))
            hits.append(pred_idx == true_idx)
        brier = brier_score(confs, hits)
        if brier < best_brier:
            best_brier, best_t = brier, t
    return best_t


def print_reliability_table(bins: Sequence[ReliabilityBin]) -> None:
    """Pretty-print a reliability table for the demo."""
    print(f"{'bin':>12}  {'count':>5}  {'conf':>6}  {'acc':>6}  {'gap':>6}")
    for b in bins:
        print(
            f"  [{b.low:.1f},{b.high:.1f}]  {b.count:5d}  "
            f"{b.avg_confidence:6.3f}  {b.accuracy:6.3f}  {b.gap:6.3f}"
        )


def main() -> None:
    """Synthetic demo: an overconfident model, then its calibrated Brier/ECE.

    Fully offline and deterministic (fixed RNG seed). No embedder, no LLM: we
    fabricate logits so the calibration machinery is the thing on display.
    """
    rng = np.random.default_rng(42)
    n = 400
    n_options = 4

    # Build items whose TRUE class is weakly separated in the logits, so a
    # temperature of 1.0 is overconfident and softening helps.
    logits_per_item: list[list[float]] = []
    correct_index: list[int] = []
    for _ in range(n):
        true_idx = int(rng.integers(n_options))
        base = rng.normal(0.0, 0.3, size=n_options)
        base[true_idx] += 1.1  # true class is favoured, but noisily
        logits_per_item.append([float(x) for x in base])
        correct_index.append(true_idx)

    def grade(temperature: float) -> tuple[list[float], list[bool]]:
        confs, hits = [], []
        for logits, true_idx in zip(logits_per_item, correct_index, strict=False):
            probs = softmax(np.asarray(logits), temperature=temperature)
            pred = int(np.argmax(probs))
            confs.append(float(probs[pred]))
            hits.append(pred == true_idx)
        return confs, hits

    print("=" * 70)
    print("Calibration demo (synthetic, offline): temperature scaling")
    print("=" * 70)

    confs1, hits1 = grade(1.0)
    print("\nBefore (temperature = 1.0):")
    print(f"  accuracy : {np.mean(hits1):.3f}")
    print(f"  Brier    : {brier_score(confs1, hits1):.4f}")
    print(f"  ECE      : {expected_calibration_error(confs1, hits1):.4f}")
    print_reliability_table(reliability_table(confs1, hits1, n_bins=5))

    best_t = fit_temperature(logits_per_item, correct_index)
    confs2, hits2 = grade(best_t)
    print(f"\nFitted temperature: {best_t}")
    print(f"After (temperature = {best_t}):")
    print(f"  accuracy : {np.mean(hits2):.3f}  (unchanged -- scaling preserves ranking)")
    print(f"  Brier    : {brier_score(confs2, hits2):.4f}")
    print(f"  ECE      : {expected_calibration_error(confs2, hits2):.4f}")
    print_reliability_table(reliability_table(confs2, hits2, n_bins=5))


if __name__ == "__main__":
    main()

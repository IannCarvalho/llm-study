"""
Local baseline for System One typed decisions (no LLM, no network).

A "System One" decision model takes a `state` plus one or more *typed questions*
and returns *typed answers with calibrated probabilities* -- never free text.
This module reimplements that contract locally so the whole study module runs
offline, deterministically, and in CI. The three question primitives mirror
TypeSafe's Jev API (see README): Choice, Score, and Noul.

How the baseline decides
------------------------
Every option / level / yes-no criterion is turned into a short *prototype* text.
The `state` and each prototype are embedded into vectors; the cosine similarity
between the state and each prototype becomes a logit. A softmax with an
adjustable temperature turns those logits into a probability distribution, and
`confidence` is derived from the distribution with the *same* formulas Jev
documents, so a local answer is drop-in comparable with a real Jev answer.

The embedder is INJECTABLE. The default resolves ``utils.semantic_embeddings.
embed_texts`` lazily (so importing this module never loads a model); tests pass a
fake deterministic embedder and never touch the network. Nothing here downloads
a model at import time, and nothing calls an LLM.

Run as a demo from the repo root (PYTHONPATH=.):
    python -m 16_decision_models.decision_model
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import numpy as np

# Type of an embedder: many texts in, one (n, dim) array out.
Embedder = Callable[[Sequence[str]], np.ndarray]


# ---------------------------------------------------------------------------
# Typed questions (the request contract)
# ---------------------------------------------------------------------------
@dataclass
class Choice:
    """Pick one option from a fixed set.

    Args:
        instructions: what the model should decide.
        options: mapping ``option -> short rubric description``. The description
            is what gets embedded as that option's prototype, so make it
            self-contained ("remote, network-exploitable vulnerability").
    """

    instructions: str
    options: dict[str, str]

    def prototypes(self) -> list[str]:
        return [f"{self.instructions}: {desc}" for desc in self.options.values()]

    def labels(self) -> list[str]:
        return list(self.options.keys())


@dataclass
class Score:
    """Rate the state on an ordered rubric.

    Args:
        instructions: what the model should rate.
        levels: ordered level descriptions, lowest first. Index 0..n-1 is the
            returned ``score`` axis, matching Jev's Score (which returns a
            probability-weighted value that can land between levels).
    """

    instructions: str
    levels: list[str]

    def prototypes(self) -> list[str]:
        return [f"{self.instructions}: {level}" for level in self.levels]


@dataclass
class Noul:
    """A yes/no question. The answer is the probability the statement is true.

    Args:
        instructions: the yes/no statement to evaluate.
        yes: optional description of what a "yes" means (embedded as the yes
            prototype). Defaults to the statement itself.
        no: optional description of what a "no" means.
    """

    instructions: str
    yes: str | None = None
    no: str | None = None

    def prototypes(self) -> list[str]:
        yes = self.yes or self.instructions
        no = self.no or f"not: {self.instructions}"
        return [no, yes]  # index 1 == "yes"


Question = Choice | Score | Noul


# ---------------------------------------------------------------------------
# Typed answers (the response contract)
# ---------------------------------------------------------------------------
@dataclass
class ChoiceAnswer:
    choice: str
    probabilities: dict[str, float]
    confidence: float
    type: str = "choice"


@dataclass
class ScoreAnswer:
    score: float
    probabilities: dict[str, float]  # level index (as str) -> probability
    legend: dict[str, str]
    confidence: float
    type: str = "score"


@dataclass
class NoulAnswer:
    noul: float  # probability the answer is "yes", 0..1
    type: str = "noul"


Answer = ChoiceAnswer | ScoreAnswer | NoulAnswer


# ---------------------------------------------------------------------------
# Math: softmax + Jev-compatible confidence
# ---------------------------------------------------------------------------
def softmax(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    """Numerically stable softmax with a temperature.

    Lower temperature -> sharper (more confident) distribution; higher
    temperature -> flatter. Temperature is the single knob the calibration step
    tunes (see calibration.py).
    """
    if temperature <= 0.0:
        raise ValueError("temperature must be > 0")
    scaled = np.asarray(logits, dtype=np.float64) / temperature
    scaled -= scaled.max()
    exp = np.exp(scaled)
    return exp / exp.sum()


def choice_confidence(probabilities: Sequence[float]) -> float:
    """Jev's Choice confidence: how far the top probability sits above 1/n.

    0 when the distribution is uniform, 1 when all mass is on one option.
    """
    probs = list(probabilities)
    n = len(probs)
    if n <= 1:
        return 1.0
    conf = (max(probs) - 1.0 / n) / (1.0 - 1.0 / n)
    return float(min(1.0, max(0.0, conf)))


def score_confidence(probabilities: Sequence[float]) -> float:
    """Jev's Score confidence: ordered-level spread around the peak.

    Mass on a neighbouring level lowers confidence less than mass far away.
    Floored at 0 when the answer is at least as spread as a uniform one.
    """
    probs = list(probabilities)
    n = len(probs)
    if n <= 1:
        return 1.0
    m = int(np.argmax(probs))
    spread = sum(p * abs(i - m) for i, p in enumerate(probs))
    even_spread = sum(abs(i - (n - 1) / 2) for i in range(n)) / n
    if even_spread == 0.0:
        return 1.0
    return float(max(0.0, 1.0 - spread / even_spread))


# ---------------------------------------------------------------------------
# The model
# ---------------------------------------------------------------------------
def _default_embedder(texts: Sequence[str]) -> np.ndarray:
    """Lazy default embedder: utils.semantic_embeddings.embed_texts.

    Imported inside the call so this module imports with no model download and
    no sentence-transformers dependency at import time. Never used by the tests.
    """
    from utils.semantic_embeddings import embed_texts

    return embed_texts(list(texts))


def _cosine_matrix(state_vec: np.ndarray, proto_vecs: np.ndarray) -> np.ndarray:
    """Cosine similarity of one state vector against each prototype row."""
    sn = float(np.linalg.norm(state_vec))
    if sn == 0.0:
        return np.zeros(proto_vecs.shape[0], dtype=np.float64)
    pn = np.linalg.norm(proto_vecs, axis=1)
    pn[pn == 0.0] = 1.0
    return (proto_vecs @ state_vec) / (pn * sn)


@dataclass
class DecisionModel:
    """Local System One model over an injectable embedder.

    Args:
        embedder: ``texts -> (n, dim)`` array. Defaults to the lazy
            sentence-transformers embedder; tests inject a fake one.
        temperature: softmax temperature. 1.0 by default; tune it with
            ``calibration.fit_temperature`` on a held-out split.
    """

    embedder: Embedder = field(default=_default_embedder)
    temperature: float = 1.0

    def _distribution(self, state: str, prototypes: list[str]) -> np.ndarray:
        """Embed state + prototypes in one batch and softmax the similarities."""
        vectors = np.asarray(self.embedder([state, *prototypes]), dtype=np.float64)
        state_vec, proto_vecs = vectors[0], vectors[1:]
        sims = _cosine_matrix(state_vec, proto_vecs)
        return softmax(sims, temperature=self.temperature)

    def ask_choice(self, state: str, question: Choice) -> ChoiceAnswer:
        labels = question.labels()
        probs = self._distribution(state, question.prototypes())
        prob_map = {label: float(p) for label, p in zip(labels, probs, strict=False)}
        winner = labels[int(np.argmax(probs))]
        return ChoiceAnswer(
            choice=winner,
            probabilities=prob_map,
            confidence=choice_confidence(probs),
        )

    def ask_score(self, state: str, question: Score) -> ScoreAnswer:
        probs = self._distribution(state, question.prototypes())
        expected = float(sum(i * p for i, p in enumerate(probs)))
        legend = {str(i): level for i, level in enumerate(question.levels)}
        prob_map = {str(i): float(p) for i, p in enumerate(probs)}
        return ScoreAnswer(
            score=expected,
            probabilities=prob_map,
            legend=legend,
            confidence=score_confidence(probs),
        )

    def ask_noul(self, state: str, question: Noul) -> NoulAnswer:
        # Two prototypes (no, yes); the probability of "yes" is the noul value.
        probs = self._distribution(state, question.prototypes())
        return NoulAnswer(noul=float(probs[1]))

    def ask(self, state: str, questions: dict[str, Question]) -> dict[str, Answer]:
        """Answer several typed questions against ONE state, in isolation.

        Mirrors Jev's batching: each question is evaluated independently against
        the same state and returned under the id you supplied.
        """
        answers: dict[str, Answer] = {}
        for qid, question in questions.items():
            if isinstance(question, Choice):
                answers[qid] = self.ask_choice(state, question)
            elif isinstance(question, Score):
                answers[qid] = self.ask_score(state, question)
            elif isinstance(question, Noul):
                answers[qid] = self.ask_noul(state, question)
            else:  # pragma: no cover - guarded by the Question union
                raise TypeError(f"unknown question type: {type(question)!r}")
        return answers


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
def main() -> None:
    """Classify one CVE with Choice + Score + Noul in a single call.

    Uses the real sentence-transformers embedder (downloads a small model on
    first run; offline-friendly thereafter). No LLM and no network beyond the
    one-time model fetch.
    """
    from utils.data_loader import load_cves

    cves = load_cves()
    if not cves:
        print("No CVEs available -- cannot run the decision-model demo.")
        return

    cve = cves[0]
    state = f"{cve.id}: {cve.description}"

    model = DecisionModel()  # default embedder, temperature 1.0
    questions: dict[str, Question] = {
        "severity": Choice(
            instructions="How severe is this vulnerability",
            options={
                "CRITICAL": "critical, trivially exploitable, full compromise",
                "HIGH": "high impact, serious compromise likely",
                "MEDIUM": "moderate impact, limited or conditional exploit",
                "LOW": "low impact, hard to exploit or minor effect",
            },
        ),
        "remote_exploit": Noul(
            instructions="This vulnerability can be exploited remotely over a network",
        ),
        "groundedness": Score(
            instructions="How much concrete technical detail the description gives",
            levels=["almost none", "some detail", "thorough detail"],
        ),
    }

    print("=" * 70)
    print("Local System One decision model (no LLM) over one CVE")
    print(f"State: {state[:90]}{'...' if len(state) > 90 else ''}")
    print("=" * 70)

    try:
        answers = model.ask(state, questions)
    except Exception as exc:  # noqa: BLE001 - surface embedder/model issues clearly
        print(
            "\n[error] Could not embed the state. The default embedder needs "
            "sentence-transformers and a one-time model download.\n"
            f"Details: {exc}"
        )
        return

    sev = answers["severity"]
    assert isinstance(sev, ChoiceAnswer)
    print(f"\nseverity (Choice): {sev.choice}  confidence={sev.confidence:.2f}")
    for label, p in sorted(sev.probabilities.items(), key=lambda kv: -kv[1]):
        print(f"    {label:9s} {p:.3f}")

    remote = answers["remote_exploit"]
    assert isinstance(remote, NoulAnswer)
    print(f"\nremote_exploit (Noul): P(yes)={remote.noul:.3f}")

    grounded = answers["groundedness"]
    assert isinstance(grounded, ScoreAnswer)
    print(
        f"\ngroundedness (Score): {grounded.score:.2f} "
        f"confidence={grounded.confidence:.2f}"
    )
    for idx, level in grounded.legend.items():
        print(f"    {idx} {level:18s} {grounded.probabilities[idx]:.3f}")


if __name__ == "__main__":
    main()

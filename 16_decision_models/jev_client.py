"""
Optional real-Jev client -- the SAME typed contract, backed by TypeSafe's API.

This is the ONLY file in the module that talks to a network. It is import-light
(standard library only), lazy (nothing happens until you call it), and NEVER
touched by the tests. decision_model.py gives you an offline baseline with the
identical Choice/Score/Noul shape; swap this client in when you want the real
model's calibrated answers.

Verified against the official docs (read 2026-10-16; see README references):
  - Endpoint : POST https://api.typesafe.ai/v1/systemone
  - Auth     : Authorization: Bearer <API_KEY>, key from env TYPESAFE_API_KEY
  - Request  : {"state": ..., "model": "jev-latest",
                "questions": {id: {"type": "choice"|"score"|"noul",
                                   "instructions": ..., "criteria": ...}}}
  - Response : {"model": ..., "answers": {id: {...}}, "usage": {...}}
      choice answer -> {type, choice, probabilities, confidence}
      score  answer -> {type, score, legend, probabilities, confidence}
      noul   answer -> {type, noul}

There is an official typesafe-sdk Python package; this module deliberately does
NOT depend on it (the repo's CI installs no such package) and speaks the raw
HTTP API with urllib instead, so it adds no new dependency.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping

API_URL = "https://api.typesafe.ai/v1/systemone"
API_KEY_ENV = "TYPESAFE_API_KEY"
DEFAULT_MODEL = "jev-latest"


class JevClientError(RuntimeError):
    """Raised when the Jev API cannot be reached or returns an error."""


def _question_payload(questions: Mapping[str, object]) -> dict[str, dict]:
    """Translate local typed-question objects into the API's JSON question map.

    Accepts the Choice / Score / Noul dataclasses from decision_model, or ready
    dicts (passed through untouched). The dataclasses are matched by class NAME
    on purpose: this package is digit-prefixed, so decision_model may have been
    loaded under different module names (``16_decision_models.decision_model``
    via importlib, ``decision_model`` via the tests' load_module), and an
    ``isinstance`` check against one copy rejects objects from the other.
    """
    payload: dict[str, dict] = {}
    for qid, q in questions.items():
        kind = type(q).__name__
        if isinstance(q, dict):
            payload[qid] = q
        elif kind == "Choice":
            payload[qid] = {
                "type": "choice",
                "instructions": q.instructions,
                "criteria": q.options,
            }
        elif kind == "Score":
            payload[qid] = {
                "type": "score",
                "instructions": q.instructions,
                "criteria": q.levels,
            }
        elif kind == "Noul":
            entry: dict[str, object] = {"type": "noul", "instructions": q.instructions}
            if q.yes is not None or q.no is not None:
                entry["criteria"] = {"true": q.yes or "", "false": q.no or ""}
            payload[qid] = entry
        else:
            raise TypeError(f"unsupported question type for {qid!r}: {type(q)!r}")
    return payload


def system_one(
    state: object,
    questions: Mapping[str, object],
    *,
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
    timeout: float = 30.0,
) -> dict:
    """Call Jev's System One endpoint and return the parsed JSON response.

    Args:
        state: the context to evaluate (string or JSON-serialisable structure).
        questions: id -> typed question (Choice/Score/Noul or a raw dict).
        model: model alias, default ``jev-latest``.
        api_key: overrides the ``TYPESAFE_API_KEY`` environment variable.
        timeout: socket timeout in seconds.

    Raises:
        JevClientError: no API key, a transport failure, or a non-2xx status.
    """
    key = api_key or os.environ.get(API_KEY_ENV)
    if not key:
        raise JevClientError(
            f"no API key: set the {API_KEY_ENV} environment variable or pass api_key="
        )

    body = json.dumps(
        {"state": state, "model": model, "questions": _question_payload(questions)}
    ).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # 4xx / 5xx
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise JevClientError(f"Jev API returned {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:  # DNS / connection / timeout
        raise JevClientError(f"could not reach the Jev API: {exc.reason}") from exc


def main() -> None:
    """Tiny smoke demo -- only runs if TYPESAFE_API_KEY is set; else explains."""
    if not os.environ.get(API_KEY_ENV):
        print(
            f"[skipped] {API_KEY_ENV} is not set, so the real Jev client cannot "
            "run. Set it to a key from the TypeSafe console (https://console.typesafe.ai) "
            "to try this file; the offline baseline (decision_model.py) needs no key."
        )
        return

    try:
        response = system_one(
            state="Our payment API has been returning 500 errors for an hour.",
            questions={"is_urgent": {"type": "noul", "instructions": "Does this convey urgency?"}},
        )
    except JevClientError as exc:
        print(f"[error] {exc}")
        return
    print(json.dumps(response, indent=2))


if __name__ == "__main__":
    main()

"""
Retry Parser — Generic parse / validate / retry for structured LLM output

This module isolates the production pattern that stops "sometimes the model
returns invalid JSON" from leaking into every call site:

    1. Ask a generator function for raw text (an LLM reply, or a canned string
       in tests).
    2. Strip Markdown code fences the model loves to wrap JSON in.
    3. Parse the JSON and VALIDATE it against a Pydantic model.
    4. On failure, call the generator AGAIN, this time handing it the exact
       validation error so the next attempt can fix itself — up to N tries.

The generator is a plain callable `fn(feedback: Optional[str]) -> str`. On the
first attempt `feedback` is None; on every retry it carries a human-readable
description of why the previous output was rejected. Keeping the generator
abstract is the whole point: the same retry engine drives a real LLM in
`schema_extraction.py` and a deterministic stub in this file's `__main__`, with
no LLM required to prove the parser works.

Run the self-test (no Ollama needed):

    python -m 10_structured_output.retry_parser
"""

import json
import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple, Type, TypeVar

from pydantic import BaseModel, ValidationError

# The model type the generic parser validates against.
M = TypeVar("M", bound=BaseModel)

# A generator takes optional feedback (why the last attempt failed) and returns
# the next raw candidate string.
Generator = Callable[[Optional[str]], str]


# Match an outer ```...``` fence, optionally tagged with a language like ```json.
_FENCE_RE = re.compile(
    r"```[a-zA-Z0-9_-]*\s*(.*?)\s*```",
    re.DOTALL,
)


def strip_code_fences(text: str) -> str:
    """
    Remove a surrounding Markdown code fence if present.

    Models frequently answer with ```json\n{...}\n``` even when told to return
    raw JSON. We return the fence body when a fence exists, otherwise the input
    is returned unchanged (trimmed).
    """
    if text is None:
        return ""
    match = _FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def extract_json_block(text: str) -> str:
    """
    Best-effort isolation of a single JSON object from noisy model output.

    After fence stripping, small models may still wrap the object in prose
    ("Here is the JSON: {...}. Hope it helps!"). We grab the outermost
    balanced {...} span if the whole string is not already clean JSON.
    """
    cleaned = strip_code_fences(text)
    # Fast path: it already looks like a bare object/array.
    if cleaned[:1] in ("{", "["):
        return cleaned
    # Fall back to the first {...} span (greedy to catch nested braces).
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        return match.group(0)
    return cleaned


@dataclass
class ParseResult:
    """Outcome of a parse_with_retry run."""

    model: Optional[BaseModel]
    attempts: int
    success: bool
    errors: List[str] = field(default_factory=list)
    last_raw: str = ""


def _validate_once(
    model_cls: Type[M], raw: str
) -> Tuple[Optional[M], Optional[str]]:
    """
    Try to turn one raw string into a validated model instance.

    Returns (instance, None) on success or (None, error_message) on failure.
    The error message is phrased so it can be fed straight back to the model.
    """
    candidate = extract_json_block(raw)

    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as exc:
        return None, f"the output was not valid JSON ({exc.msg} at char {exc.pos})"

    try:
        instance = model_cls.model_validate(data)
    except ValidationError as exc:
        # Compact, model-friendly rendering of each field problem.
        problems = "; ".join(
            f"field '{'.'.join(str(p) for p in err['loc'])}': {err['msg']}"
            for err in exc.errors()
        )
        return None, f"the JSON failed schema validation - {problems}"

    return instance, None


def parse_with_retry(
    model_cls: Type[M],
    generator: Generator,
    max_attempts: int = 3,
) -> ParseResult:
    """
    Drive a generator until it produces output that validates, or give up.

    Args:
        model_cls: the Pydantic model the output must satisfy.
        generator: fn(feedback) -> raw text. feedback is None on the first call
            and an error description on every retry.
        max_attempts: hard cap on generator calls (>= 1).

    Returns:
        ParseResult with the validated instance (or None), the number of
        attempts used, and the collected error messages.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    errors: List[str] = []
    feedback: Optional[str] = None
    last_raw = ""

    for attempt in range(1, max_attempts + 1):
        last_raw = generator(feedback)
        instance, error = _validate_once(model_cls, last_raw)

        if error is None:
            return ParseResult(
                model=instance,
                attempts=attempt,
                success=True,
                errors=errors,
                last_raw=last_raw,
            )

        errors.append(error)
        # Feed the failure back so the next attempt can self-correct.
        feedback = (
            f"Your previous output failed validation because {error}. "
            "Return ONLY a corrected JSON object that satisfies the schema, "
            "with no prose and no Markdown fences."
        )

    return ParseResult(
        model=None,
        attempts=max_attempts,
        success=False,
        errors=errors,
        last_raw=last_raw,
    )


# ---------------------------------------------------------------------------
# Deterministic self-test — no LLM required.
# ---------------------------------------------------------------------------

def main() -> None:
    """Exercise the parser against simulated generator outputs."""
    from enum import Enum

    from pydantic import Field

    class Color(str, Enum):
        RED = "red"
        GREEN = "green"
        BLUE = "blue"

    class Widget(BaseModel):
        name: str
        count: int = Field(ge=0)
        color: Color

    print("=" * 70)
    print("retry_parser self-test (deterministic, no LLM)")
    print("=" * 70)

    # --- Case 1: valid bare JSON on the first try ------------------------
    def gen_valid(_feedback: Optional[str]) -> str:
        return '{"name": "alpha", "count": 3, "color": "green"}'

    r1 = parse_with_retry(Widget, gen_valid, max_attempts=3)
    print("\n[case 1] valid JSON, first attempt")
    print(f"  success={r1.success} attempts={r1.attempts} model={r1.model!r}")
    assert r1.success and r1.attempts == 1, "case 1 should pass on attempt 1"

    # --- Case 2: JSON wrapped in a ```json fence -------------------------
    def gen_fenced(_feedback: Optional[str]) -> str:
        return (
            "Sure, here is the result:\n"
            "```json\n"
            '{"name": "beta", "count": 0, "color": "blue"}\n'
            "```\n"
            "Let me know if you need anything else!"
        )

    r2 = parse_with_retry(Widget, gen_fenced, max_attempts=3)
    print("\n[case 2] JSON inside a Markdown fence + prose")
    print(f"  success={r2.success} attempts={r2.attempts} model={r2.model!r}")
    assert r2.success and r2.attempts == 1, "case 2 should strip the fence and pass"

    # --- Case 3: invalid first, then corrected via feedback --------------
    # The stub returns bad output until it is told what was wrong, proving the
    # retry/feedback loop drives the fix.
    def make_self_correcting() -> Generator:
        state = {"calls": 0}

        def gen(feedback: Optional[str]) -> str:
            state["calls"] += 1
            if feedback is None:
                # Attempt 1: not even JSON.
                return "I think the count is five, color blue."
            if "not valid JSON" in feedback and state["calls"] == 2:
                # Attempt 2: JSON now, but 'count' violates ge=0 and color is bad.
                return '{"name": "gamma", "count": -1, "color": "teal"}'
            # Attempt 3: fully corrected.
            return '{"name": "gamma", "count": 5, "color": "blue"}'

        return gen

    r3 = parse_with_retry(Widget, make_self_correcting(), max_attempts=3)
    print("\n[case 3] invalid -> schema error -> corrected across retries")
    print(f"  success={r3.success} attempts={r3.attempts} model={r3.model!r}")
    for i, err in enumerate(r3.errors, 1):
        print(f"    attempt {i} rejected: {err}")
    assert r3.success and r3.attempts == 3, "case 3 should succeed on attempt 3"

    # --- Case 4: never valid -> give up after max_attempts ---------------
    def gen_always_bad(_feedback: Optional[str]) -> str:
        return '{"name": "delta", "count": -9, "color": "mauve"}'

    r4 = parse_with_retry(Widget, gen_always_bad, max_attempts=2)
    print("\n[case 4] always invalid -> gives up cleanly")
    print(f"  success={r4.success} attempts={r4.attempts} errors={len(r4.errors)}")
    assert not r4.success and r4.attempts == 2, "case 4 should fail after 2 attempts"

    print("\nAll self-test assertions passed. [OK]")


if __name__ == "__main__":
    main()

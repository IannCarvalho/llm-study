"""
Deterministic tests for 10_structured_output/retry_parser.py.

Exercises the parse / validate / retry engine with LOCAL fake generators (no
LLM), mirroring the module's own main(): valid-first-try, fenced JSON, prose-
wrapped JSON, self-correction across retries, and clean give-up. Also tests the
two text-cleaning helpers directly.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from conftest import load_module

rp = load_module("10_structured_output/retry_parser.py", "retry_parser")


# A small schema the parser validates against (mirrors the Widget used by the module's main()).
class Color(str, Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


class Widget(BaseModel):
    name: str
    count: int = Field(ge=0)
    color: Color


# ---------------------------------------------------------------------------
# strip_code_fences
# ---------------------------------------------------------------------------
def test_strip_code_fences_plain_text():
    assert rp.strip_code_fences("  hello  ") == "hello"


def test_strip_code_fences_json_fence():
    assert rp.strip_code_fences('```json\n{"a": 1}\n```') == '{"a": 1}'


def test_strip_code_fences_untagged_fence():
    assert rp.strip_code_fences('```\n{"a": 1}\n```') == '{"a": 1}'


def test_strip_code_fences_none_returns_empty():
    assert rp.strip_code_fences(None) == ""


# ---------------------------------------------------------------------------
# extract_json_block
# ---------------------------------------------------------------------------
def test_extract_json_block_bare_object():
    assert rp.extract_json_block('{"a": 1}') == '{"a": 1}'


def test_extract_json_block_wrapped_in_prose():
    assert rp.extract_json_block('Here it is: {"a": 1}. Thanks!') == '{"a": 1}'


def test_extract_json_block_strips_fence_then_extracts():
    assert rp.extract_json_block('```json\n{"a": 1}\n```') == '{"a": 1}'


def test_extract_json_block_no_json_returns_cleaned_input():
    assert rp.extract_json_block("there is no json here") == "there is no json here"


# ---------------------------------------------------------------------------
# parse_with_retry
# ---------------------------------------------------------------------------
def test_parse_with_retry_valid_first_attempt():
    def gen(_feedback: Optional[str]) -> str:
        return '{"name": "alpha", "count": 3, "color": "green"}'

    result = rp.parse_with_retry(Widget, gen, max_attempts=3)
    assert result.success is True
    assert result.attempts == 1
    assert isinstance(result.model, Widget)
    assert result.model.name == "alpha"
    assert result.model.count == 3


def test_parse_with_retry_strips_fence_and_prose():
    def gen(_feedback: Optional[str]) -> str:
        return (
            "Sure, here is the result:\n"
            "```json\n"
            '{"name": "beta", "count": 0, "color": "blue"}\n'
            "```\n"
            "Hope that helps!"
        )

    result = rp.parse_with_retry(Widget, gen, max_attempts=3)
    assert result.success is True
    assert result.attempts == 1
    assert result.model.color == Color.BLUE


def test_parse_with_retry_self_corrects_across_attempts():
    """
    Fake generator that is wrong until it receives feedback, proving the
    feedback loop drives a fix (no LLM involved).
    """
    state = {"calls": 0}

    def gen(feedback: Optional[str]) -> str:
        state["calls"] += 1
        if feedback is None:
            return "I think the count is five, color blue."  # not JSON
        if state["calls"] == 2:
            return '{"name": "gamma", "count": -1, "color": "teal"}'  # schema fail
        return '{"name": "gamma", "count": 5, "color": "blue"}'  # corrected

    result = rp.parse_with_retry(Widget, gen, max_attempts=3)
    assert result.success is True
    assert result.attempts == 3
    assert result.model.count == 5
    # Two rejections were recorded before success.
    assert len(result.errors) == 2


def test_parse_with_retry_gives_up_cleanly():
    def gen(_feedback: Optional[str]) -> str:
        return '{"name": "delta", "count": -9, "color": "mauve"}'  # always invalid

    result = rp.parse_with_retry(Widget, gen, max_attempts=2)
    assert result.success is False
    assert result.attempts == 2
    assert result.model is None
    assert len(result.errors) == 2


def test_parse_with_retry_rejects_bad_max_attempts():
    import pytest

    with pytest.raises(ValueError):
        rp.parse_with_retry(Widget, lambda _f: "{}", max_attempts=0)

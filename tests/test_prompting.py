"""
Deterministic tests for 00_prompting/prompt_variants.py.

Everything here is offline: no LLM, no network, no model download. We exercise
the pure prompt builders (shape, determinism, no cross-contamination between
variants) and the structured-output validator (JSON extraction from fenced and
raw replies, required-key checks, and the SeverityLevel enum constraint).

The live-model path in `main()` is intentionally NOT exercised — it needs
Ollama, which the golden rule excludes from tests.
"""

import json

from conftest import load_module

from utils.data_loader import get_cve_by_id, load_cves
from utils.models import SeverityLevel

prompt_variants = load_module("00_prompting/prompt_variants.py", "prompt_variants")


# ---------------------------------------------------------------------------
# Fixtures (plain helpers — the dataset is deterministic and offline)
# ---------------------------------------------------------------------------
def _target_and_examples():
    cves = load_cves()
    target = get_cve_by_id("CVE-2024-1234") or cves[0]
    examples = [cve for cve in cves if cve.id != target.id][:2]
    return target, examples


# ---------------------------------------------------------------------------
# Builders — determinism
# ---------------------------------------------------------------------------
def test_builders_are_deterministic():
    """Same CVE in -> byte-identical prompt out, for every builder."""
    target, examples = _target_and_examples()
    assert prompt_variants.build_zero_shot(target) == prompt_variants.build_zero_shot(
        target
    )
    assert prompt_variants.build_role(target) == prompt_variants.build_role(target)
    assert prompt_variants.build_chain_of_thought(
        target
    ) == prompt_variants.build_chain_of_thought(target)
    assert prompt_variants.build_contract_contrast(
        target
    ) == prompt_variants.build_contract_contrast(target)
    assert prompt_variants.build_structured(
        target
    ) == prompt_variants.build_structured(target)
    assert prompt_variants.build_few_shot(
        target, examples
    ) == prompt_variants.build_few_shot(target, examples)


def test_build_all_variants_has_six_named_variants():
    """build_all_variants returns exactly the six expected keys."""
    target, examples = _target_and_examples()
    variants = prompt_variants.build_all_variants(target, examples)
    assert set(variants) == {
        "zero_shot",
        "few_shot",
        "role",
        "chain_of_thought",
        "contract_contrast",
        "structured",
    }
    # Every prompt is a non-empty string that mentions the target CVE id.
    for prompt in variants.values():
        assert isinstance(prompt, str) and prompt.strip()
        assert target.id in prompt


# ---------------------------------------------------------------------------
# Builders — content distinguishes the variants
# ---------------------------------------------------------------------------
def test_zero_shot_is_bare_task():
    """Zero-shot carries the bare instruction and no role/example scaffolding."""
    target, _ = _target_and_examples()
    prompt = prompt_variants.build_zero_shot(target)
    assert prompt.startswith("Resuma este CVE.")
    assert "analista de seguranca" not in prompt
    assert "Exemplo" not in prompt and "exemplos" not in prompt


def test_role_sets_persona():
    """Role variant assigns the security-analyst persona."""
    target, _ = _target_and_examples()
    prompt = prompt_variants.build_role(target)
    assert "analista de seguranca" in prompt
    assert "gestor" in prompt


def test_cot_requests_step_by_step_and_conclusion():
    """CoT variant asks for step-by-step reasoning and a final conclusion."""
    target, _ = _target_and_examples()
    prompt = prompt_variants.build_chain_of_thought(target)
    assert "passo a passo" in prompt
    assert "Conclusao:" in prompt


def test_contract_contrast_states_do_and_dont():
    """Contract+contrast lists both what to do and what not to do."""
    target, _ = _target_and_examples()
    prompt = prompt_variants.build_contract_contrast(target)
    assert "O QUE FAZER" in prompt
    assert "O QUE NAO FAZER" in prompt


def test_structured_prompt_names_every_schema_key():
    """The structured prompt names all four required JSON keys."""
    target, _ = _target_and_examples()
    prompt = prompt_variants.build_structured(target)
    for key in prompt_variants.STRUCTURED_KEYS:
        assert key in prompt
    assert prompt_variants.STRUCTURED_KEYS == (
        "id",
        "severidade",
        "resumo",
        "acao_recomendada",
    )


def test_few_shot_includes_examples_and_excludes_none():
    """Few-shot embeds every example CVE id plus the target, in order."""
    target, examples = _target_and_examples()
    assert examples, "dataset should have at least one non-target CVE"
    prompt = prompt_variants.build_few_shot(target, examples)
    for ex in examples:
        assert ex.id in prompt
    # The target appears after the examples (it is the final 'resume this' CVE).
    assert prompt.index(target.id) > prompt.index(examples[0].id)


def test_few_shot_never_uses_target_as_its_own_example():
    """The target CVE is never one of the worked examples (would leak the answer)."""
    target, examples = _target_and_examples()
    assert all(ex.id != target.id for ex in examples)


# ---------------------------------------------------------------------------
# extract_json
# ---------------------------------------------------------------------------
def test_extract_json_from_fenced_block():
    """A ```json fenced object is extracted without the fences."""
    text = '```json\n{"id": "CVE-2024-1234"}\n```'
    extracted = prompt_variants.extract_json(text)
    assert extracted is not None
    assert json.loads(extracted) == {"id": "CVE-2024-1234"}


def test_extract_json_from_bare_fence():
    """A bare ``` fence (no language tag) also works."""
    text = '```\n{"a": 1}\n```'
    assert json.loads(prompt_variants.extract_json(text)) == {"a": 1}


def test_extract_json_from_raw_object():
    """Raw JSON that is the whole reply is returned as-is."""
    text = '{"a": 1, "b": 2}'
    assert json.loads(prompt_variants.extract_json(text)) == {"a": 1, "b": 2}


def test_extract_json_embedded_in_prose():
    """A balanced object embedded in surrounding prose is extracted."""
    text = 'Claro! Aqui esta: {"id": "X", "n": 2} — espero que ajude.'
    assert json.loads(prompt_variants.extract_json(text)) == {"id": "X", "n": 2}


def test_extract_json_returns_none_when_absent():
    """No object -> None, and empty input -> None."""
    assert prompt_variants.extract_json("sem json aqui") is None
    assert prompt_variants.extract_json("") is None


# ---------------------------------------------------------------------------
# validate_structured_output
# ---------------------------------------------------------------------------
def _valid_payload() -> dict:
    return {
        "id": "CVE-2024-1234",
        "severidade": "CRITICAL",
        "resumo": "RCE nao autenticada via buffer overflow.",
        "acao_recomendada": "Atualizar para a versao 2.2 ou superior.",
    }


def test_validate_accepts_valid_fenced_json():
    """A complete, fenced, enum-valid reply passes and returns the parsed dict."""
    text = "```json\n" + json.dumps(_valid_payload()) + "\n```"
    result = prompt_variants.validate_structured_output(text)
    assert result.ok is True
    assert result.error is None
    assert result.data == _valid_payload()


def test_validate_accepts_every_severity_level():
    """Each SeverityLevel member is accepted in the severidade field."""
    for level in SeverityLevel:
        payload = _valid_payload()
        payload["severidade"] = level.value
        result = prompt_variants.validate_structured_output(json.dumps(payload))
        assert result.ok is True, f"{level.value} should be accepted"


def test_validate_rejects_unknown_severity():
    """A severidade outside SeverityLevel is rejected with a clear reason."""
    payload = _valid_payload()
    payload["severidade"] = "URGENTE"
    result = prompt_variants.validate_structured_output(json.dumps(payload))
    assert result.ok is False
    assert result.data is None
    assert "severidade" in result.error


def test_validate_rejects_missing_keys():
    """A reply missing a required key is rejected and names the missing key."""
    payload = _valid_payload()
    del payload["acao_recomendada"]
    result = prompt_variants.validate_structured_output(json.dumps(payload))
    assert result.ok is False
    assert "acao_recomendada" in result.error


def test_validate_rejects_malformed_json():
    """Non-JSON input is rejected without raising."""
    result = prompt_variants.validate_structured_output("isto nao e json {")
    assert result.ok is False
    assert result.error


def test_validate_rejects_non_object_json():
    """Valid JSON that is not an object (e.g. a list) is rejected."""
    result = prompt_variants.validate_structured_output("[1, 2, 3]")
    assert result.ok is False
    assert result.error


def test_validate_rejects_empty_string():
    """Empty input is rejected, not crashed."""
    result = prompt_variants.validate_structured_output("")
    assert result.ok is False
    assert result.error

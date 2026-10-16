"""
Prompt Variants — Six Ways to Ask the Same Thing About One CVE

Day 0 of the roadmap: before you retrieve context (RAG) or hand the model tools
(agents), you have to ask well. This module makes the "how you ask" layer
concrete and *deterministic* by building — never calling — six prompts over the
SAME real CVE from the single project dataset (`utils.data_loader`):

    1. zero-shot          — "Resuma este CVE." No examples, no role, no format.
    2. few-shot (2 ex.)   — two worked examples derived from the dataset itself,
                            then the target. Shows the model the pattern to copy.
    3. role               — assigns a persona ("security analyst writing for a
                            manager") that steers tone and audience.
    4. chain-of-thought   — asks the model to reason step by step before the
                            verdict (Wei et al. 2022).
    5. contract+contrast  — an explicit contract of what TO do AND what NOT to do.
    6. structured (JSON)  — demands a single JSON object with a fixed schema so
                            the reply is machine-parseable.

Why builders and not calls? The teaching value — and the test value — is in the
*text we send*, which must be identical every run. The builders are pure
functions of a `CVEData`; given the same CVE they return byte-identical prompts.

The structured variant is paired with `validate_structured_output`, a pure
validator that extracts the JSON (even when the model wraps it in a ```json
fence), checks the four required keys, and confirms `severidade` is a member of
`utils.models.SeverityLevel`. That is the honest signal of whether a reply is
usable by code, independent of any model.

LLM is OPTIONAL. The deterministic path (building and printing every prompt, and
validating a sample reply) runs with no Ollama, no network and no key. `main()`
only tries a live model inside a lazy import + try/except; without a backend it
explains how to start Ollama and exits 0.

Run from the repository root (digit-prefixed packages are not importable with a
plain ``import``):

    python -m 00_prompting.prompt_variants
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from utils.data_loader import get_cve_by_id, load_cves
from utils.models import CVEData, SeverityLevel

# The CVE the whole demo is built around; falls back to the first available CVE
# if the dataset ever changes.
DEFAULT_CVE_ID = "CVE-2024-1234"

# The exact keys the structured variant must emit, in Portuguese to match the
# roadmap's exercise ({id, severidade, resumo, acao_recomendada}).
STRUCTURED_KEYS: tuple[str, ...] = ("id", "severidade", "resumo", "acao_recomendada")

# Matches a ```json ... ``` or ``` ... ``` fenced block and captures its body.
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ValidationResult:
    """Outcome of validating a structured (JSON) reply.

    `ok` is the single boolean a pipeline would branch on; `data` carries the
    parsed object when valid, and `error` the first human-readable reason it was
    rejected otherwise. Exactly one of (`data`, `error`) is set.
    """

    ok: bool
    data: dict | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def _format_cve(cve: CVEData) -> str:
    """Render a CVE as the stable report block every prompt embeds."""
    versions = ", ".join(cve.affected_versions) or "n/a"
    return (
        f"CVE ID: {cve.id}\n"
        f"Severidade informada: {cve.severity.value} (CVSS {cve.score})\n"
        f"Vetor CVSS: {cve.cvss_vector}\n"
        f"Versoes afetadas: {versions}\n"
        f"Descricao: {cve.description}"
    )


def _example_block(cve: CVEData) -> str:
    """A compact worked example used by the few-shot builder.

    The "answer" is derived deterministically from the CVE's own fields — no
    model, no randomness — so the example is always consistent with the data.
    """
    versions = ", ".join(cve.affected_versions) or "n/a"
    answer = (
        f"{cve.id} e uma vulnerabilidade de severidade {cve.severity.value} "
        f"(CVSS {cve.score}) que afeta as versoes {versions}. "
        "Recomenda-se atualizar para uma versao corrigida o quanto antes."
    )
    return f"CVE:\n{_format_cve(cve)}\nResumo:\n{answer}"


# ---------------------------------------------------------------------------
# Prompt builders — pure, deterministic, one per variant
# ---------------------------------------------------------------------------
def build_zero_shot(cve: CVEData) -> str:
    """Variant 1 — zero-shot: the bare task, no examples, no role, no format."""
    return f"Resuma este CVE.\n\n{_format_cve(cve)}"


def build_few_shot(cve: CVEData, examples: list[CVEData]) -> str:
    """Variant 2 — few-shot: show the pattern with worked examples, then ask.

    `examples` are OTHER CVEs from the same dataset (never the target), each
    turned into a deterministic CVE->Resumo pair. This demonstrates the k-shot
    idea (Brown et al. 2020): the model infers the task from demonstrations.
    """
    shots = "\n\n".join(_example_block(ex) for ex in examples)
    return (
        "Siga o padrao dos exemplos e resuma o ultimo CVE no mesmo estilo.\n\n"
        f"{shots}\n\n"
        "Agora resuma este:\n"
        f"CVE:\n{_format_cve(cve)}\n"
        "Resumo:"
    )


def build_role(cve: CVEData) -> str:
    """Variant 3 — role prompting: a persona that steers tone and audience."""
    return (
        "Voce e um analista de seguranca. Resuma este CVE para um gestor "
        "nao-tecnico, destacando o risco de negocio em linguagem simples.\n\n"
        f"{_format_cve(cve)}"
    )


def build_chain_of_thought(cve: CVEData) -> str:
    """Variant 4 — chain-of-thought: reason step by step, then conclude."""
    return (
        "Analise passo a passo a severidade deste CVE e entao conclua.\n"
        "Primeiro liste o raciocinio (vetor de ataque, impacto, facilidade de "
        "exploracao); depois escreva uma linha final iniciada por 'Conclusao:' "
        "com o veredito de severidade.\n\n"
        f"{_format_cve(cve)}"
    )


def build_contract_contrast(cve: CVEData) -> str:
    """Variant 5 — contract + contrast: say what TO do AND what NOT to do."""
    return (
        "Resuma este CVE seguindo o contrato abaixo.\n\n"
        "O QUE FAZER:\n"
        "- Escrever no maximo 3 frases.\n"
        "- Citar a severidade e o impacto principal.\n"
        "- Terminar com uma acao de remediacao concreta.\n\n"
        "O QUE NAO FAZER:\n"
        "- Nao inventar CVEs, versoes ou numeros que nao estejam no relatorio.\n"
        "- Nao incluir codigo de exploracao nem instrucoes de ataque.\n"
        "- Nao usar jargao sem explicar.\n\n"
        f"{_format_cve(cve)}"
    )


def build_structured(cve: CVEData) -> str:
    """Variant 6 — structured output: demand one JSON object, fixed schema."""
    schema_hint = (
        "{\n"
        '  "id": "<o id do CVE, string>",\n'
        '  "severidade": "<um de: CRITICAL, HIGH, MEDIUM, LOW, INFO>",\n'
        '  "resumo": "<uma a duas frases>",\n'
        '  "acao_recomendada": "<uma acao concreta de remediacao>"\n'
        "}"
    )
    return (
        "Responda APENAS com um unico objeto JSON, exatamente neste formato, "
        "sem texto antes ou depois e sem cercas de codigo:\n"
        f"{schema_hint}\n\n"
        f"{_format_cve(cve)}"
    )


def build_all_variants(cve: CVEData, examples: list[CVEData]) -> dict[str, str]:
    """Build every variant for one CVE, keyed by a stable variant name."""
    return {
        "zero_shot": build_zero_shot(cve),
        "few_shot": build_few_shot(cve, examples),
        "role": build_role(cve),
        "chain_of_thought": build_chain_of_thought(cve),
        "contract_contrast": build_contract_contrast(cve),
        "structured": build_structured(cve),
    }


# ---------------------------------------------------------------------------
# Deterministic validator for the structured variant
# ---------------------------------------------------------------------------
def extract_json(text: str) -> str | None:
    """Return the JSON substring from `text`, or None if none is found.

    Handles three shapes a model emits in practice:
    1. a ```json ... ``` (or bare ``` ... ```) fenced block,
    2. raw JSON that is the whole reply,
    3. JSON embedded in prose — the first balanced {...} object is extracted.
    """
    if not text:
        return None

    fenced = _FENCE_RE.search(text)
    if fenced:
        return fenced.group(1).strip()

    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    # Fall back to the first balanced top-level object anywhere in the text.
    start = stripped.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(stripped)):
        char = stripped[i]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return stripped[start : i + 1]
    return None


def validate_structured_output(text: str) -> ValidationResult:
    """Validate a structured-variant reply with no model and no network.

    Checks, in order: a JSON object can be extracted and parsed; it is a dict;
    every key in `STRUCTURED_KEYS` is present; and `severidade` is a valid
    `SeverityLevel` member. The first failure wins and is reported in `error`.
    """
    candidate = extract_json(text)
    if candidate is None:
        return ValidationResult(ok=False, error="nenhum objeto JSON encontrado na saida")

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        return ValidationResult(ok=False, error=f"JSON invalido: {exc.msg}")

    if not isinstance(parsed, dict):
        return ValidationResult(ok=False, error="o JSON de topo nao e um objeto")

    missing = [key for key in STRUCTURED_KEYS if key not in parsed]
    if missing:
        return ValidationResult(
            ok=False, error=f"chaves obrigatorias ausentes: {', '.join(missing)}"
        )

    severity = parsed["severidade"]
    valid_levels = {level.value for level in SeverityLevel}
    if not isinstance(severity, str) or severity not in valid_levels:
        return ValidationResult(
            ok=False,
            error=(
                f"severidade {severity!r} fora de SeverityLevel "
                f"({', '.join(sorted(valid_levels))})"
            ),
        )

    return ValidationResult(ok=True, data=parsed)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
def _pick_cves() -> tuple[CVEData, list[CVEData]]:
    """Choose the target CVE and up to two OTHER CVEs for the few-shot examples."""
    cves = load_cves()
    target = get_cve_by_id(DEFAULT_CVE_ID) or (cves[0] if cves else None)
    if target is None:
        raise RuntimeError("No CVEs available — cannot build the prompt demo.")
    examples = [cve for cve in cves if cve.id != target.id][:2]
    return target, examples


def _print_prompts(variants: dict[str, str]) -> None:
    """Print every built prompt — this is the deterministic, no-LLM demo."""
    for name, prompt in variants.items():
        print("\n" + "-" * 70)
        print(f"VARIANTE: {name}")
        print("-" * 70)
        print(prompt)


def _demo_validator() -> None:
    """Show the structured validator on a good and a bad sample, no model needed."""
    print("\n" + "=" * 70)
    print("Validador deterministico da saida estruturada (sem LLM)")
    print("=" * 70)
    good = (
        "```json\n"
        '{"id": "CVE-2024-1234", "severidade": "CRITICAL", '
        '"resumo": "RCE nao autenticada via buffer overflow.", '
        '"acao_recomendada": "Atualizar para a versao 2.2 ou superior."}\n'
        "```"
    )
    bad = (
        '{"id": "CVE-2024-1234", "severidade": "URGENTE", '
        '"resumo": "x", "acao_recomendada": "y"}'
    )
    for label, sample in (("valida", good), ("invalida", bad)):
        result = validate_structured_output(sample)
        verdict = "OK" if result.ok else f"REJEITADA ({result.error})"
        print(f"  amostra {label:9s}: {verdict}")


def main() -> None:
    """Build + print every variant, validate a sample, then try the LLM if up."""
    target, examples = _pick_cves()
    variants = build_all_variants(target, examples)

    print("=" * 70)
    print("Day 0 — Prompting: seis variacoes sobre o MESMO CVE")
    print(f"CVE alvo: {target.id} ({target.severity.value}, CVSS {target.score})")
    print(f"Exemplos few-shot: {', '.join(ex.id for ex in examples) or 'nenhum'}")
    print("=" * 70)

    _print_prompts(variants)
    _demo_validator()

    # Optional live run. Lazy import so the deterministic path never needs the
    # LLM dependency chain; try/except so a missing backend degrades cleanly.
    print("\n" + "=" * 70)
    print("Execucao ao vivo (opcional — requer Ollama)")
    print("=" * 70)
    try:
        from utils.llm_client import get_llm_client  # lazy: only when running live

        client = get_llm_client()
        for name, prompt in variants.items():
            reply = client.generate(prompt, temperature=0.0, max_tokens=400)
            print(f"\n[{name}] resposta do modelo:\n{reply.strip()}")
            if name == "structured":
                result = validate_structured_output(reply)
                verdict = "OK" if result.ok else f"REJEITADA ({result.error})"
                print(f"  validacao estruturada: {verdict}")
    except Exception as exc:  # noqa: BLE001 — surface backend errors clearly
        print(
            "\n[info] Nenhum backend de LLM acessivel — a parte determinist"
            "ica acima ja rodou por completo.\n"
            "Para rodar as variantes contra um modelo local:\n"
            "  1. Instale e inicie o Ollama (https://ollama.com) com `ollama serve`.\n"
            "  2. Baixe um modelo, ex.: `ollama pull mistral`.\n"
            "  3. Rode novamente: `python -m 00_prompting.prompt_variants`.\n"
            f"Detalhe: {exc}"
        )


if __name__ == "__main__":
    main()

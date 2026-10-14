"""
Spec-Driven Development (SDD) applied to agents.

Core idea: instead of a loose, ad-hoc prompt ("analyze this CVE"), we define a
*spec* — a prior, structured artifact that pins down WHAT the agent must produce:
the required output fields, the output format, and the constraints. The spec is a
single source of truth that (a) is compiled into the system prompt the LLM sees,
and (b) is used to VALIDATE whatever the LLM returns.

This module demonstrates the contrast on a real CVE:
    - WITHOUT spec: a loose prompt. Free-form prose. Nothing to validate against.
    - WITH    spec: structured system prompt derived from the spec, JSON output,
                     then programmatic validation of that output against the spec.

The human-readable twin of the spec object below lives in `spec_example.md`.

Run from the repo root (PYTHONPATH="."):
    python -m 07_sdd.spec_driven_analysis
"""

import json
from typing import Optional

from pydantic import BaseModel, Field

from utils.llm_client import get_llm_client
from utils.data_loader import get_cve_by_id
from utils.models import CVEData


# ---------------------------------------------------------------------------
# THE SPEC (structured artifact)
# ---------------------------------------------------------------------------
# This is the "spec as artifact": a declarative description of the task that
# exists BEFORE any model call. It is the same thing spec_example.md expresses
# in prose. Because it is data, it can be compiled into a prompt AND used to
# check the result — the two never drift apart.

VALID_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}


class CVEAnalysisSpec(BaseModel):
    """Structured specification for the 'analyze a CVE' task."""

    task: str = Field(
        default="analyze_cve",
        description="Stable task identifier.",
    )
    # Output fields the model MUST produce. Order is the contract.
    required_fields: list[str] = Field(
        default_factory=lambda: [
            "id",             # CVE identifier, echoed from input
            "severidade",     # one of VALID_SEVERITIES
            "vetor_ataque",   # how the flaw is exploited
            "mitigacao",      # concrete remediation
            "risco_negocio",  # business-level impact
        ]
    )
    output_format: str = Field(default="json")
    constraints: list[str] = Field(
        default_factory=lambda: [
            "Output ONLY the JSON object. No markdown fences, no prose around it.",
            "All required fields must be present and non-empty.",
            "'severidade' must be one of CRITICAL, HIGH, MEDIUM, LOW, INFO.",
            "'id' must echo the input CVE id exactly.",
            "Do not invent CVEs, versions, or attack vectors not derivable from input.",
        ]
    )

    def to_system_prompt(self) -> str:
        """Compile the spec into a system prompt. This is the 'spec drives agent' step."""
        fields = "\n".join(f"  - {f}" for f in self.required_fields)
        rules = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(self.constraints))
        return (
            "You are a security analyst. Analyze the given CVE and return a result "
            "that strictly follows this specification.\n\n"
            f"TASK: {self.task}\n"
            f"OUTPUT FORMAT: {self.output_format.upper()}\n"
            "REQUIRED OUTPUT FIELDS (all mandatory):\n"
            f"{fields}\n\n"
            "CONSTRAINTS:\n"
            f"{rules}\n"
        )

    def build_user_prompt(self, cve: CVEData) -> str:
        """Render the CVE record as the task input for the model."""
        return (
            f"CVE to analyze:\n"
            f"  id: {cve.id}\n"
            f"  severity: {cve.severity.value}\n"
            f"  score: {cve.score}\n"
            f"  cvss_vector: {cve.cvss_vector}\n"
            f"  affected_versions: {', '.join(cve.affected_versions)}\n"
            f"  description: {cve.description}\n"
        )


# ---------------------------------------------------------------------------
# VALIDATION (spec checks the output)
# ---------------------------------------------------------------------------

class ValidationReport(BaseModel):
    """Result of validating a model output against the spec."""

    is_valid: bool
    valid_json: bool
    missing_fields: list[str] = Field(default_factory=list)
    empty_fields: list[str] = Field(default_factory=list)
    severity_ok: bool = False
    parsed: Optional[dict] = None
    error: Optional[str] = None


def _strip_fences(text: str) -> str:
    """Best-effort removal of ```json ... ``` fences a model may add anyway."""
    t = text.strip()
    if t.startswith("```"):
        # drop first line (``` or ```json) and a trailing fence if present
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def validate_against_spec(output: str, spec: CVEAnalysisSpec) -> ValidationReport:
    """Validate a raw model output string against the spec's contract."""
    cleaned = _strip_fences(output)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        return ValidationReport(
            is_valid=False, valid_json=False, error=f"invalid JSON: {e}"
        )

    if not isinstance(parsed, dict):
        return ValidationReport(
            is_valid=False, valid_json=True,
            error="JSON is valid but is not an object/dict.",
        )

    missing = [f for f in spec.required_fields if f not in parsed]
    empty = [
        f for f in spec.required_fields
        if f in parsed and (parsed[f] is None or str(parsed[f]).strip() == "")
    ]
    severity_ok = str(parsed.get("severidade", "")).upper() in VALID_SEVERITIES

    is_valid = not missing and not empty and severity_ok
    return ValidationReport(
        is_valid=is_valid,
        valid_json=True,
        missing_fields=missing,
        empty_fields=empty,
        severity_ok=severity_ok,
        parsed=parsed,
    )


# ---------------------------------------------------------------------------
# DEMO: without-spec vs with-spec
# ---------------------------------------------------------------------------

def analyze_without_spec(client, cve: CVEData) -> str:
    """The 'loose prompt' baseline: no structure, no contract, nothing to check."""
    prompt = f"Analyze this security vulnerability: {cve.id} — {cve.description}"
    return client.generate(prompt, max_tokens=300)


def analyze_with_spec(client, cve: CVEData, spec: CVEAnalysisSpec) -> str:
    """Spec-driven: the spec compiles the system prompt and the output is checked."""
    system_prompt = spec.to_system_prompt()
    user_prompt = spec.build_user_prompt(cve)
    # Low temperature: we want the model to obey a contract, not to be creative.
    return client.generate(user_prompt, system_prompt=system_prompt,
                           temperature=0.1, max_tokens=400)


def main() -> None:
    spec = CVEAnalysisSpec()

    # Pick a real CVE from the single source of truth (utils/data/cves.json).
    cve = get_cve_by_id("CVE-2024-1234")
    if cve is None:
        print("CVE not found in utils/data/cves.json — cannot run demo.")
        return

    print("=" * 70)
    print("SPEC-DRIVEN ANALYSIS")
    print("=" * 70)
    print(f"\nTarget CVE: {cve.id} ({cve.severity.value}, score {cve.score})\n")

    print("--- THE SPEC (structured artifact) ---")
    print(spec.model_dump_json(indent=2))
    print("\n--- COMPILED SYSTEM PROMPT (spec -> prompt) ---")
    print(spec.to_system_prompt())

    # The LLM is only reachable when Ollama is up. Fail with a clear message
    # instead of hanging or dumping a stack trace, but keep the code correct.
    try:
        client = get_llm_client()

        print("=" * 70)
        print("WITHOUT SPEC (loose prompt — free-form, unvalidatable)")
        print("=" * 70)
        loose = analyze_without_spec(client, cve)
        print(loose)
        print("\n[note] There is no contract here, so nothing can be validated.\n")

        print("=" * 70)
        print("WITH SPEC (structured prompt — JSON, then validated)")
        print("=" * 70)
        structured = analyze_with_spec(client, cve, spec)
        print(structured)

        print("\n--- VALIDATION AGAINST SPEC ---")
        report = validate_against_spec(structured, spec)
        print(f"valid JSON        : {report.valid_json}")
        print(f"missing fields    : {report.missing_fields or 'none'}")
        print(f"empty fields      : {report.empty_fields or 'none'}")
        print(f"severity in enum  : {report.severity_ok}")
        print(f"=> OUTPUT ACCEPTED: {report.is_valid}")
        if not report.is_valid:
            print("   (a real pipeline would reject and retry/repair here)")

    except Exception as e:  # noqa: BLE001 - surface any LLM/connectivity error cleanly
        print("=" * 70)
        print("LLM NOT AVAILABLE")
        print("=" * 70)
        print(f"Could not reach the LLM backend: {e}")
        print(
            "\nStart Ollama (e.g. `ollama serve` and pull the configured model), "
            "then re-run:\n    python -m 07_sdd.spec_driven_analysis\n"
            "The spec, prompt compilation, and validator above do not need the LLM "
            "and ran fine — only the live generation step requires Ollama."
        )


if __name__ == "__main__":
    main()

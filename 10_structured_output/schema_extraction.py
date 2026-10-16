"""
Schema Extraction — Forcing a Validated Pydantic Object out of an LLM

The production problem: an LLM asked for JSON "mostly" returns valid JSON. The
rare malformed reply (an extra sentence, a trailing comma, a wrong enum value,
a number out of range) is exactly what breaks a pipeline at 3 a.m. The fix is
not a better prompt alone — it is prompt + VALIDATE + RETRY-WITH-FEEDBACK:

    1. Define the exact shape we want as a Pydantic model (`CVEAssessment`).
    2. Ask the LLM to extract that shape from a real CVE (`get_cve_by_id`).
    3. Parse + validate against the schema (via retry_parser).
    4. If validation fails, re-prompt the model with the precise error so it can
       correct itself — up to N attempts.

The generic parse/validate/retry engine lives in `retry_parser.py`; this file
is the LLM-backed caller that supplies the schema, the prompt, and the per-retry
feedback injection. It prints how many attempts the model needed, which is the
honest signal of how reliable the model is at structured output.

Requires Ollama (or another configured backend) to be running. If the backend
is unavailable the script fails with a clear, instructive message instead of
hanging.

Run:

    python -m 10_structured_output.schema_extraction
"""

from enum import Enum

from pydantic import BaseModel, Field

from utils.data_loader import get_cve_by_id, load_cves
from utils.llm_client import get_llm_client
from utils.models import CVEData

from .retry_parser import Generator, parse_with_retry

MAX_ATTEMPTS = 3


class Severity(str, Enum):
    """The severity the model must choose from — an exact enum, no free text."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class CVEAssessment(BaseModel):
    """
    The structured verdict we force the LLM to produce for one CVE.

    Every field is a validation lever: the enum rejects invented severities, the
    1-10 bound rejects nonsense scores, and the bool/str fields must be present
    and well-typed or the whole object is rejected and retried.
    """

    id: str = Field(description="The CVE identifier, e.g. CVE-2024-1234")
    severity: Severity = Field(description="One of CRITICAL/HIGH/MEDIUM/LOW/INFO")
    exploitability: int = Field(
        ge=1, le=10, description="How easy to exploit, 1 (hard) to 10 (trivial)"
    )
    is_exploitable: bool = Field(
        description="True if a remote/unauthenticated attacker can realistically exploit it"
    )
    remediation: str = Field(
        min_length=1, description="A one-sentence remediation recommendation"
    )


def build_extraction_prompt(cve: CVEData) -> str:
    """The initial instruction: here is the CVE, return exactly this JSON shape."""
    schema_hint = (
        "{\n"
        '  "id": "<the CVE id, string>",\n'
        '  "severity": "<one of: CRITICAL, HIGH, MEDIUM, LOW, INFO>",\n'
        '  "exploitability": <integer 1-10>,\n'
        '  "is_exploitable": <true or false>,\n'
        '  "remediation": "<one short sentence>"\n'
        "}"
    )
    return (
        "You are a security analyst. Read the vulnerability report below and "
        "produce a structured assessment.\n\n"
        "Return ONLY a single JSON object in exactly this shape, with no prose "
        "and no Markdown code fences:\n"
        f"{schema_hint}\n\n"
        "VULNERABILITY REPORT:\n"
        f"CVE ID: {cve.id}\n"
        f"Reported severity: {cve.severity.value} (CVSS {cve.score})\n"
        f"CVSS vector: {cve.cvss_vector}\n"
        f"Affected versions: {', '.join(cve.affected_versions) or 'n/a'}\n"
        f"Description: {cve.description}"
    )


def make_llm_generator(client, base_prompt: str) -> Generator:
    """
    Build the generator the retry engine calls each attempt.

    First attempt sends `base_prompt`; every retry appends the validation
    feedback the parser produced so the model can self-correct. The temperature
    is 0.0 to make the extraction as deterministic as the backend allows.
    """

    def generate(feedback: str | None) -> str:
        prompt = base_prompt
        if feedback:
            prompt = f"{base_prompt}\n\n{feedback}"
        return client.generate(
            prompt,
            system_prompt="You output only strict JSON that matches the requested schema.",
            temperature=0.0,
            max_tokens=400,
        )

    return generate


def main() -> None:
    """Extract one real CVE into a validated CVEAssessment, with retry."""
    cves = load_cves()
    if not cves:
        print("No CVEs available — cannot run the structured-output demo.")
        return

    # Use a real, known CVE from the single project dataset.
    target_id = "CVE-2024-1234"
    cve = get_cve_by_id(target_id) or cves[0]

    print("=" * 70)
    print("Structured Output: extract -> validate -> retry on failure")
    print(f"Subject CVE: {cve.id}")
    print(f"Schema: {CVEAssessment.__name__} "
          f"(fields: {', '.join(CVEAssessment.model_fields)})")
    print("=" * 70)

    try:
        client = get_llm_client()
        generator = make_llm_generator(client, build_extraction_prompt(cve))
        result = parse_with_retry(
            CVEAssessment, generator, max_attempts=MAX_ATTEMPTS
        )
    except Exception as exc:  # noqa: BLE001 — surface backend errors clearly
        print(
            "\n[error] Could not reach the LLM backend. Is Ollama running "
            "(e.g. `ollama serve`) and the configured model pulled?\n"
            f"Details: {exc}"
        )
        return

    print(f"\nAttempts used: {result.attempts} / {MAX_ATTEMPTS}")
    for i, err in enumerate(result.errors, 1):
        print(f"  attempt {i} rejected: {err}")

    if result.success and result.model is not None:
        assessment = result.model
        print("\n[OK] Validated assessment:")
        # model_dump() is only reachable because validation succeeded.
        for field_name, value in assessment.model_dump().items():
            print(f"  {field_name:16s}: {value}")
    else:
        print("\n[fail] The model never produced schema-valid output within "
              f"the {MAX_ATTEMPTS} attempts. Last raw reply:")
        print(result.last_raw.strip() or "<empty>")


if __name__ == "__main__":
    main()

"""
LLM-as-Judge — Scoring a Generated Summary with a Second LLM Call

Pattern demonstrated here:

1. GENERATE: take one or two real CVEs from `load_cves()` and ask the LLM to
   write a short security summary of them (the "candidate" output).
2. JUDGE: send a *second* prompt to the LLM — the "judge" — containing the
   source CVE context and the candidate summary, and ask it to score the summary
   on three axes (1-5 scale) with a short justification, returning strict JSON:
     - groundedness:  is every claim supported by the source CVE context?
     - completeness:  are the key facts (id, severity, impact) covered?
     - clarity:       is it well written and unambiguous?

Why a separate judge call? The model that *writes* text is a poor grader of its
own single response in the same turn; isolating evaluation into its own prompt
with an explicit rubric and a machine-readable output is the core of the
"LLM-as-judge" technique used to score outputs at scale when no human label and
no exact reference answer exist.

The judge is still an LLM, so its scores are approximate and should be sanity-
checked against deterministic metrics (see rag_metrics.py). Requires Ollama (or
another configured backend) to be running; it fails with a clear message if not.
"""

import json
import re
from typing import Dict, List, Optional

from utils.llm_client import get_llm_client
from utils.data_loader import load_cves
from utils.models import CVEData


def format_cve_context(cves: List[CVEData]) -> str:
    """Render the source CVEs as plain-text context for both the writer and judge."""
    blocks = []
    for cve in cves:
        blocks.append(
            f"CVE ID: {cve.id}\n"
            f"Severity: {cve.severity.value} (CVSS {cve.score})\n"
            f"Affected versions: {', '.join(cve.affected_versions) or 'n/a'}\n"
            f"Description: {cve.description}"
        )
    return "\n\n".join(blocks)


def generate_summary(client, context: str) -> str:
    """Step 1 — produce the candidate summary to be judged."""
    prompt = (
        "You are a security analyst. Write a concise summary (3-4 sentences) of "
        "the following vulnerability report(s) for an engineering audience. State "
        "the affected software, the type of vulnerability, and the impact.\n\n"
        f"{context}"
    )
    return client.generate(prompt, temperature=0.7, max_tokens=400)


def build_judge_prompt(context: str, summary: str) -> str:
    """Step 2 — the rubric + strict-JSON instruction for the judge call."""
    return (
        "You are a strict evaluator. Given the SOURCE CONTEXT and a CANDIDATE "
        "SUMMARY written from it, score the summary on three criteria using an "
        "integer scale from 1 (poor) to 5 (excellent):\n"
        "- groundedness: every claim is supported by the source context, with no "
        "invented facts.\n"
        "- completeness: the key facts (CVE id, severity, affected software, "
        "impact) are present.\n"
        "- clarity: the summary is clear, well structured, and unambiguous.\n\n"
        "Respond with ONLY a JSON object, no prose before or after, in exactly "
        "this shape:\n"
        '{"groundedness": {"score": <1-5>, "justification": "<one sentence>"}, '
        '"completeness": {"score": <1-5>, "justification": "<one sentence>"}, '
        '"clarity": {"score": <1-5>, "justification": "<one sentence>"}}\n\n'
        f"SOURCE CONTEXT:\n{context}\n\n"
        f"CANDIDATE SUMMARY:\n{summary}"
    )


def parse_judge_json(raw: str) -> Optional[Dict]:
    """
    Extract the JSON verdict from the judge's reply.

    Small models often wrap JSON in prose or code fences, so we try a direct
    parse first and fall back to grabbing the outermost {...} block.
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def print_verdict(verdict: Dict) -> None:
    """Pretty-print the judge's scores."""
    criteria = ["groundedness", "completeness", "clarity"]
    print("\nJudge verdict:")
    scores = []
    for criterion in criteria:
        entry = verdict.get(criterion, {})
        score = entry.get("score", "?")
        justification = entry.get("justification", "")
        if isinstance(score, (int, float)):
            scores.append(float(score))
        print(f"  {criterion:13s}: {score}/5 — {justification}")
    if scores:
        print(f"  {'average':13s}: {sum(scores) / len(scores):.2f}/5")


def main() -> None:
    """Run the generate -> judge pipeline over one or two real CVEs."""
    cves = load_cves()
    if not cves:
        print("No CVEs available — cannot run the LLM-as-judge demo.")
        return

    # Use one or two real CVEs as the subject of the summary.
    sample = cves[:2]
    context = format_cve_context(sample)

    print("=" * 70)
    print("LLM-as-Judge: generate a summary, then score it with a second prompt")
    print(f"Subject CVEs: {[c.id for c in sample]}")
    print("=" * 70)

    client = get_llm_client()

    try:
        # Step 1: generate the candidate summary.
        summary = generate_summary(client, context)
        print("\nGenerated summary:")
        print(summary.strip())

        # Step 2: judge the summary.
        judge_prompt = build_judge_prompt(context, summary)
        raw_verdict = client.generate(
            judge_prompt,
            system_prompt="You are a meticulous evaluator that returns only JSON.",
            temperature=0.0,  # deterministic-as-possible grading
            max_tokens=400,
        )
    except Exception as exc:  # noqa: BLE001 — surface any backend error clearly
        print(
            "\n[error] Could not reach the LLM backend. Is Ollama running "
            "(e.g. `ollama serve`) and the configured model pulled?\n"
            f"Details: {exc}"
        )
        return

    verdict = parse_judge_json(raw_verdict)
    if verdict is None:
        print("\n[warn] Judge did not return parseable JSON. Raw response:")
        print(raw_verdict.strip())
        return

    print_verdict(verdict)


if __name__ == "__main__":
    main()

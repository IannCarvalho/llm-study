"""
Langfuse Integration: Open-Source Observability for LLM Applications

Langfuse provides detailed tracing and evaluation of LLM calls.
This example demonstrates:
- Automatic generation tracing with Langfuse's OpenAI wrapper
- Custom evaluators (accuracy, response length)
- Batch execution with results evaluation

Requires: LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY in .env

The endpoint, model and API key come from the project config (.env), so the
same switch between Ollama, LM Studio and OpenAI applies here. The questions
are grounded in the CVE base (utils.agentic_utils.get_cve_qa_examples).
"""

import os
from functools import lru_cache

from langfuse import Evaluation, get_client
from langfuse.openai import OpenAI

from utils.agentic_utils import get_cve_qa_examples
from utils.config import get_config
from utils.prompts import ASSISTANT_QA_SYSTEM

config = get_config()


@lru_cache(maxsize=1)
def llm_client() -> OpenAI:
    """
    OpenAI-compatible client for the endpoint configured in .env (Ollama by default).

    langfuse.openai.OpenAI is a drop-in wrapper: every completion becomes a
    'generation' trace in Langfuse with model name, input, output, token counts.
    Ollama ignores the api_key, but the OpenAI library requires one.
    """
    return OpenAI(base_url=config.ollama_base_url, api_key=config.openai_api_key)


def call_llm(prompt: str) -> str:
    """Call the configured model through the Langfuse-instrumented client."""
    response = llm_client().chat.completions.create(
        model=config.ollama_model,
        messages=[{"role": "user", "content": prompt}],
        name="llm-completion",
    )
    return response.choices[0].message.content


def process_task(item: dict, **kwargs) -> str:
    """Execute task: process input through LLM using centralized Q&A template."""
    question = item["input"]
    print(f"  Processing: {question[:50]}...")

    # Use centralized Q&A template
    prompt = ASSISTANT_QA_SYSTEM.format(question=question)
    response = call_llm(prompt)
    return response.strip()


def evaluate_accuracy(
    output: str,
    expected: str,
    **kwargs
) -> Evaluation:
    """Evaluate if response contains expected keywords."""
    if not output or not expected:
        return Evaluation(
            name="accuracy",
            value=0.0,
            comment="Output or expected is empty",
        )

    expected_lower = expected.lower()
    output_lower = output.lower()

    if (
        expected_lower in output_lower
        or any(word in output_lower for word in expected_lower.split())
    ):
        return Evaluation(
            name="accuracy",
            value=1.0,
            comment="Response contains expected keywords",
        )
    else:
        return Evaluation(
            name="accuracy",
            value=0.0,
            comment="Response does not contain expected keywords",
        )


def evaluate_response_length(output: str, **kwargs) -> Evaluation:
    """Evaluate if response length is within acceptable range."""
    length = len(output)
    if 50 <= length <= 500:
        value = 1.0
    elif length < 50:
        value = 0.5
    else:
        value = 0.7

    return Evaluation(
        name="response_length",
        value=value,
        comment=f"{length} characters",
    )


def evaluate_average_accuracy(item_results: list, **kwargs) -> Evaluation:
    """Calculate average accuracy across all items."""
    accuracies = [
        eval.value
        for result in item_results
        for eval in result.evaluations
        if eval.name == "accuracy"
    ]

    if not accuracies:
        return Evaluation(name="avg_accuracy", value=None)

    avg = sum(accuracies) / len(accuracies)
    return Evaluation(
        name="avg_accuracy",
        value=avg,
        comment=f"Average accuracy: {avg:.1%} ({len(accuracies)} items)"
    )


def evaluate_average_response_length(*, item_results, **kwargs) -> Evaluation:
    """Calculate average response length score across all items."""
    lengths = [
        eval.value for result in item_results
        for eval in result.evaluations
        if eval.name == "response_length"
    ]

    if not lengths:
        return Evaluation(name="avg_response_length_score", value=None)

    avg = sum(lengths) / len(lengths)
    return Evaluation(
        name="avg_response_length_score",
        value=avg,
        comment=f"Average response length score: {avg:.2f}"
    )


def main() -> None:
    os.environ.setdefault("LANGFUSE_TRACING_ENVIRONMENT", "local")
    langfuse_client = get_client()

    # CVE-grounded examples in Langfuse's dataset format
    test_data = [
        {
            "input": ex["question"],
            "expected": ex["expected"]
        }
        for ex in get_cve_qa_examples()
    ]

    print("Running Langfuse Experiment with Evaluators\n")
    print(f"Testing {len(test_data)} queries with {config.ollama_model} + Evaluators\n")

    result = langfuse_client.run_experiment(
        name="Observability Examples",
        run_name="CVE QA Run",
        description=(
            f"CVE-grounded questions with {config.ollama_model} "
            "+ Accuracy + Response Length evaluations"
        ),
        data=test_data,
        task=process_task,
        evaluators=[evaluate_accuracy, evaluate_response_length],
        run_evaluators=[evaluate_average_accuracy, evaluate_average_response_length],
        max_concurrency=1,
        metadata={
            "model": config.ollama_model,
            "base_url": config.ollama_base_url,
            "environment": "local",
            "version": "v2"
        }
    )

    print("\n" + "="*80)
    print("Experiment with Evaluators completed!\n")

    print(result.format())

    # Ensure all traces and scores are sent before script terminates.
    # Critical for short scripts; otherwise data may be missing from dashboard.
    langfuse_client.flush()

    print("\n" + "="*80)
    print("Results sent to Langfuse (see the experiment in your project).")


if __name__ == "__main__":
    main()

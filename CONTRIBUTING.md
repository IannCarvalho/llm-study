# Contributing

Thanks for your interest in this learning repository. It is an educational
project — examples are meant to stay small, readable, and runnable locally.

## Setup

```bash
# 1. Clone and enter the repo
git clone https://github.com/IannCarvalho/llm-study.git
cd llm-study

# 2. Create a virtual environment (Python 3.11)
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy the env template and fill what you need
cp .env.example .env
```

For the LLM-backed examples, run a local model with
[Ollama](https://ollama.ai): `ollama serve` then `ollama pull mistral`.
No cloud API key is required for local use — see `.env.example` for the OpenAI
and other cloud options.

## Running examples

Every module runs as a package from the repo root:

```bash
python -m 01_vector_databases.hybrid_search
python -m 12_agentic_rag.agentic_rag
```

Many examples have a **deterministic path that runs without Ollama** (search,
reranking, guardrails, metrics, memory windows). Those are what the test suite
and CI exercise.

## Tests and linting

```bash
# Run the deterministic test suite (no LLM / no network needed)
python -m pytest tests/ -q

# Lint
ruff check .
```

CI runs both on every push and pull request (see
`.github/workflows/ci.yml`). Please keep the suite green and add tests for new
deterministic behavior.

## Style

- Code, names, docstrings and comments in **English**.
- Keep examples self-contained and runnable; prefer the shared helpers in
  `utils/` over duplicating logic.
- A README or comment must only reference files that actually exist.

## License

By contributing, you agree that your contributions are licensed under the
[MIT License](LICENSE).

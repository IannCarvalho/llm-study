"""
Prompt templates for agentic AI patterns.

Each prompt is stored in a separate file for clarity and maintainability.
Prompts are loaded on demand to keep memory footprint low.
"""

from pathlib import Path

_PROMPT_DIR = Path(__file__).parent


class PromptTemplates:
    """Load and manage system prompts for agentic patterns."""

    _cache: dict[str, str] = {}

    @staticmethod
    def _load_prompt(name: str) -> str:
        """Load prompt from file with caching."""
        if name in PromptTemplates._cache:
            return PromptTemplates._cache[name]

        prompt_file = _PROMPT_DIR / f"{name}.txt"
        if not prompt_file.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

        with open(prompt_file) as f:
            content = f.read().strip()

        PromptTemplates._cache[name] = content
        return content

    @staticmethod
    @property
    def REACT_SYSTEM() -> str:
        """ReAct pattern: Think-Act-Observe loop."""
        return PromptTemplates._load_prompt("react")

    @staticmethod
    @property
    def TOOL_USE_SYSTEM() -> str:
        """Tool Use pattern: Function calling."""
        return PromptTemplates._load_prompt("tool_use")


# Export as module-level constants for backward compatibility
REACT_SYSTEM = PromptTemplates._load_prompt("react")
TOOL_USE_SYSTEM = PromptTemplates._load_prompt("tool_use")
ASSISTANT_SYSTEM = PromptTemplates._load_prompt("assistant")
ASSISTANT_QA_SYSTEM = PromptTemplates._load_prompt("assistant_qa")
RAG_SYSTEM = PromptTemplates._load_prompt("rag")

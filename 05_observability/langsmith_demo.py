"""
LangSmith Integration: Automatic Tracing for LangChain

LangSmith automatically traces all LangChain operations when configured.
No manual instrumentation needed - just use LangChain normally and observe!

Environment variables (in .env):
  LANGCHAIN_TRACING_V2=true
  LANGCHAIN_API_KEY=your_key
  LANGCHAIN_PROJECT=project_name

The chat model comes from utils.llm_client, so the same .env switch (Ollama,
LM Studio or OpenAI) applies here. The questions are grounded in the CVE base
(utils.agentic_utils.get_cve_qa_examples): the CVE text goes in the question.
"""

import os

from langchain_core.prompts import ChatPromptTemplate

from utils.agentic_utils import get_cve_qa_examples
from utils.llm_client import get_llm_client
from utils.prompts import ASSISTANT_QA_SYSTEM


def tracing_enabled() -> bool:
    """LangSmith only records runs when LANGCHAIN_TRACING_V2 is 'true'."""
    return os.getenv("LANGCHAIN_TRACING_V2", "").strip().lower() == "true"


def main() -> None:
    print("LangSmith Integration with Local LLM\n")
    print(f"LANGCHAIN_TRACING_V2: {os.getenv('LANGCHAIN_TRACING_V2')}")
    print(f"LANGCHAIN_PROJECT: {os.getenv('LANGCHAIN_PROJECT')}\n")

    # The same LangChain chat model every module uses (.env decides the provider).
    llm = get_llm_client().get_chat_model()

    # Simple chain with the Q&A template from utils/prompts
    prompt = ChatPromptTemplate.from_template(ASSISTANT_QA_SYSTEM)
    chain = prompt | llm

    examples = get_cve_qa_examples()
    print("=" * 80)
    print(f"Processing {len(examples)} examples...\n")

    for i, example in enumerate(examples, 1):
        question = example["question"]
        print(f"({i}) {question[:80]}...")
        try:
            # Call chain - LangSmith traces automatically when enabled
            response = chain.invoke({"question": question})
            print(f"    {response.content[:80]}...\n")
        except Exception as e:
            print(f"    Error: {e}\n")

    print("=" * 80)
    if tracing_enabled():
        print("All executions have been traced to LangSmith!")
    else:
        print("Tracing is OFF: set LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY in .env.")


if __name__ == "__main__":
    main()

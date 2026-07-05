"""
LangSmith Integration: Automatic Tracing for LangChain

LangSmith automatically traces all LangChain operations when configured.
No manual instrumentation needed - just use LangChain normally and observe!

Environment variables (in .env):
  LANGCHAIN_TRACING_V2=true
  LANGCHAIN_API_KEY=your_key
  LANGCHAIN_PROJECT=project_name
"""

import os
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from utils.config import get_config
from utils.agentic_utils import SHARED_EXAMPLES
from utils.prompts import ASSISTANT_QA_SYSTEM

load_dotenv()

config = get_config()

print("LangSmith Integration with Local LLM\n")
print(f"LANGCHAIN_TRACING_V2: {os.getenv('LANGCHAIN_TRACING_V2')}")
print(f"LANGCHAIN_PROJECT: {os.getenv('LANGCHAIN_PROJECT')}\n")

# Use ChatOpenAI for LangChain compatibility
llm = ChatOpenAI(
    model=config.ollama_model,
    base_url=config.ollama_base_url,
    api_key="ollama",
    temperature=config.llm_temperature,
    max_tokens=config.llm_max_tokens
)

# Create a simple chain with Q&A template from utils/prompts
prompt = ChatPromptTemplate.from_template(ASSISTANT_QA_SYSTEM)
chain = prompt | llm

print("="*80)
print(f"Processing {len(SHARED_EXAMPLES)} examples with automatic LangSmith tracing...\n")

for i, example in enumerate(SHARED_EXAMPLES, 1):
    question = example["question"]
    print(f"({i}) {question}")
    try:
        # Call chain - LangSmith traces automatically!
        response = chain.invoke({"question": question})
        print(f"    {response.content[:80]}...\n")
    except Exception as e:
        print(f"    Error: {e}\n")

print("="*80)
print("All executions have been traced to LangSmith!")

print("="*80)
print("All executions have been traced to LangSmith!")

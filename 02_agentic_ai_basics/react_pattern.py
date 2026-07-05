"""
ReAct Pattern: Thought -> Action -> Observation, repeated until the model
has enough information to give a Final Answer.

This is the "manual" ReAct from the original paper: no native function
calling, the model just writes its intent as text and we parse it.

Compare with tool_use.py: same tool, but here reasoning is explicit and
actions can chain across multiple steps.
"""

import re
from utils.llm_client import get_llm_client
from utils.tools import TOOL_REGISTRY
from utils.prompts import REACT_SYSTEM
from utils.agentic_utils import QUERY

MAX_STEPS = 5
ACTION_RE = re.compile(r"Action:\s*(\w+)\[(.*?)\]")
FINAL_RE = re.compile(r"Final Answer:\s*(.*)", re.DOTALL)


def run_react_agent(user_query: str) -> None:
    print(f"\n{'='*70}\nReAct Pattern: {user_query}\n{'='*70}\n")

    llm = get_llm_client(temperature=0.2)
    messages = [{"role": "user", "content": user_query}]

    for step in range(1, MAX_STEPS + 1):
        print(f"[Iteration {step}]")
        response_text = llm.chat(messages=messages, system_prompt=REACT_SYSTEM, max_tokens=256)
        print(response_text)
        messages.append({"role": "assistant", "content": response_text})

        if final_match := FINAL_RE.search(response_text):
            print(f"\nFinal answer: {final_match.group(1).strip()}")
            return

        action_match = ACTION_RE.search(response_text)
        if not action_match:
            print("Model didn't request an action or a final answer — stopping.")
            return

        tool_name, tool_arg = action_match.groups()
        tool_fn = TOOL_REGISTRY.get(tool_name)
        observation = tool_fn.invoke(tool_arg.strip()) if tool_fn else f"Unknown tool: {tool_name}"
        print(f"Observation: {observation}\n")
        messages.append({"role": "user", "content": f"Observation: {observation}"})

    print("Reached max iterations without a final answer.")


if __name__ == "__main__":
    run_react_agent(QUERY)
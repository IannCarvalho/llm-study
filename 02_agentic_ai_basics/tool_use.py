"""
Tool Use (Function Calling)

Model decides which tool to call (one-shot decision, no reasoning loop).
Differences from ReAct: direct tool selection vs explicit reasoning chain.

Compare with react_pattern.py: same tool, but here decision is direct.
"""

import json
import re
from utils.llm_client import get_llm_client
from utils.tools import TOOL_REGISTRY
from utils.prompts import TOOL_USE_SYSTEM
from utils.agentic_utils import QUERY


def extract_tool_call(text: str) -> dict:
    """Extract tool call from model response (handles JSON format)."""
    # Try to find JSON array with tool calls
    json_match = re.search(r'\[\s*\{.*?"name".*?\}\s*\]', text, re.DOTALL)
    if json_match:
        try:
            calls = json.loads(json_match.group(0))
            if calls and len(calls) > 0:
                return calls[0]
        except json.JSONDecodeError:
            pass
    return None


def run_tool_use_agent(user_query: str) -> None:
    print(f"\n{'='*70}\nTool Use Pattern: {user_query}\n{'='*70}\n")

    llm = get_llm_client(temperature=0.2)
    messages = [{"role": "user", "content": user_query}]

    # Initial request to model to decide which tool to use
    print("[Request Tool]")
    response = llm.chat(messages=messages, system_prompt=TOOL_USE_SYSTEM, max_tokens=256)
    print(f"{response}\n")
    
    # Extract and execute tool
    tool_call = extract_tool_call(response)
    if not tool_call:
        print("Model did not request a tool.")
        return
    
    tool_name = tool_call.get("name")
    tool_args = tool_call.get("arguments", {})
    
    print("[Execute Tool]")
    tool_fn = TOOL_REGISTRY.get(tool_name)
    if not tool_fn:
        print(f"Unknown tool: {tool_name}")
        return
    
    # Convert args dict to the tool's expected format
    result = tool_fn.invoke(tool_args.get("cve_id", ""))
    print(f"Tool: {tool_name}({tool_args})")
    print(f"Result: {result}\n")
    
    # Model analyzes the result
    print("[Analysis]")
    messages.append({"role": "assistant", "content": response})
    messages.append({
        "role": "user",
        "content": f"Tool result: {result}. Provide your analysis.",
    })
    
    final_response = llm.chat(
        messages=messages, 
        system_prompt=TOOL_USE_SYSTEM, 
        max_tokens=256
    )
    print(f"Analysis: {final_response}")


if __name__ == "__main__":
    run_tool_use_agent(QUERY)
"""
prompts.py — ультракороткие промпты для экономии токенов.
"""

PLANNER_SYSTEM = "Role: Lua Code Task Splitter. Output: JSON array of atomic steps. No prose."

def planner_user(prompt: str) -> str:
    return f"Input: {prompt}"


CODER_SYSTEM = "Role: Lua Programmer. Output: Pure code. No markdown, no explanations, no backticks."

def coder_user(step_description: str, signature: str, snippet: str) -> str:
    parts = [f"Task: {step_description}"]
    if snippet:
        parts.append(f"Context:\n{snippet}")
    return "\n".join(parts)


FIXER_SYSTEM = "Role: Lua Code Debugger. Output: Fixed code only. No prose."

def fixer_user(code_block: str, error: str) -> str:
    return f"Error: {error}\nCode:\n{code_block}"

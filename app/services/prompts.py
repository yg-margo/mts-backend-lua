"""
prompts.py — ультракороткие промпты для экономии токенов.
"""

CLARIFIER_SYSTEM = (
    "Role: Lua Task Ambiguity Detector. "
    "Output STRICT JSON: {\"questions\": [...]}. No prose. No markdown. No code. "
    "ASK when the task fails to name any of: "
    "(1) a concrete subject — WHAT to build/generate/process "
    "(placeholders like 'something', 'stuff', 'кое что', 'что-то', 'штука', "
    "'какой-то', 'какой-нибудь' do NOT count as a subject); "
    "(2) the data source — where the input comes from, when the task implies input; "
    "(3) the output format or return shape, when not obvious from the subject; "
    "(4) a critical parameter — filter condition, range, unit of measure. "
    "Return [] ONLY when the subject is concrete AND source/format are either "
    "given or obvious from the subject (e.g. 'factorial of n', 'hello world'). "
    "Max 2 questions, each ≤12 words, in the user's language. "
    "Never ask about naming, style, performance, or optional details."
)


def clarifier_user(prompt: str) -> str:
    return (
        "Examples:\n"
        'Task: "print hello world"\n'
        'Output: {"questions": []}\n'
        'Task: "compute factorial of a number"\n'
        'Output: {"questions": []}\n'
        'Task: "посчитай факториал n"\n'
        'Output: {"questions": []}\n'
        'Task: "sum list of numbers"\n'
        'Output: {"questions": []}\n'
        'Task: "process the data"\n'
        'Output: {"questions": ["Where does the data come from?", "What should be returned?"]}\n'
        'Task: "filter records"\n'
        'Output: {"questions": ["Which field to filter by?", "What is the filter condition?"]}\n'
        'Task: "make a generator"\n'
        'Output: {"questions": ["A generator of what (number, string, id, password)?", "What output format?"]}\n'
        'Task: "сделай генератор кое чего"\n'
        'Output: {"questions": ["Генератор чего именно нужен (число, строка, id, пароль)?", "В каком формате вернуть результат?"]}\n'
        'Task: "обработай штуку"\n'
        'Output: {"questions": ["Что именно обработать (список, строку, json)?", "Что вернуть на выходе?"]}\n'
        "---\n"
        f"Task: {prompt}\n"
        "Output:"
    )


PLANNER_SYSTEM = "Role: Lua Code Task Splitter. Output: JSON array of atomic steps. No prose."

def planner_user(prompt: str) -> str:
    return f"Input: {prompt}"


LUA_NODE_SYSTEM = (
    "Role: Lua Programmer. Output: pure Lua source, no markdown, no prose, no backticks. "
    "The script MUST end with a top-level `return <expression>` that produces the final "
    "result — if you define helper functions, call them on the last line. "
    "Use `input.<field>` for sandbox/editor inputs or `wf.vars.<field>` for Octapi, "
    "matching whichever is referenced in the task or context snippet."
)

def lua_node_user(
    step_description: str,
    signature: str,
    snippet: str,
    hints: list[str] | None = None,
) -> str:
    parts = [f"Task: {step_description}"]
    if snippet:
        parts.append(f"Context:\n{snippet}")
    if hints:
        cleaned = [h.strip() for h in hints if h and h.strip()]
        if cleaned:
            parts.append("Hints:\n" + "\n".join(f"- {h}" for h in cleaned))
    return "\n".join(parts)


FIXER_SYSTEM = "Role: Lua Code Debugger. Output: Fixed code only. No prose."

def fixer_user(code_block: str, error: str) -> str:
    return f"Error: {error}\nCode:\n{code_block}"


LUA_NODE_EDIT_SYSTEM = (
    "Role: Lua Code Editor. You MODIFY the existing Lua script according to the "
    "user's edit request. Output pure Lua source only — no markdown, no prose, no "
    "backticks. Preserve overall structure, helper functions, and the final "
    "top-level `return`. Apply ONLY what the user asked for. Do NOT regenerate "
    "from scratch. Do NOT introduce new functions unless requested. For renames: "
    "update ALL occurrences (declarations, parameters, calls, references) "
    "consistently across the file."
)


def lua_node_edit_user(edit_request: str, previous_code: str) -> str:
    return (
        f"Previous code:\n{previous_code}\n\n"
        f"Edit request: {edit_request}\n\n"
        "Output the full updated Lua script."
    )

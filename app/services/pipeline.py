"""
pipeline.py — оркестратор: Planner → Searcher → Coder → Validator/Fixer.
"""

from __future__ import annotations
import logging
import re
import html

from app.core.config import settings
from app.services.llm_client import chat, chat_json
from app.models.models import ErrorDetail, Plan, ValidationResult
from app.services.prompts import (
    CODER_SYSTEM,
    FIXER_SYSTEM,
    PLANNER_SYSTEM,
    coder_user,
    fixer_user,
    planner_user,
)
from app.services.rag import search_snippets
from app.services.validator import validate

log = logging.getLogger(__name__)


async def run_planner(user_prompt: str) -> Plan:
    try:
        raw = await chat_json(
            messages=[
                {"role": "system", "content": PLANNER_SYSTEM},
                {"role": "user", "content": planner_user(user_prompt)},
            ],
            max_tokens=settings.planner_max_tokens,
        )

        steps_raw = raw if isinstance(raw, list) else raw.get("steps", [])

        normalized: list[str] = []
        for item in steps_raw:
            if isinstance(item, str):
                text = item
            elif isinstance(item, dict):
                text = next(
                    (item[k] for k in ("step", "description", "text", "content", "task")
                     if isinstance(item.get(k), str)),
                    "",
                )
                if not text:
                    text = " ".join(str(v) for v in item.values() if isinstance(v, str))
            else:
                text = str(item)

            text = text.strip()
            if text:
                normalized.append(text)

        if not normalized:
            raise ValueError("empty plan after normalization")

        return Plan(steps=normalized)
    except Exception as e:
        log.warning("Planner failed: %s. Fallback to 1 step.", e)
        return Plan(steps=[user_prompt])


def run_searcher(step: str) -> str:
    keywords = step.split()[:5]
    return search_snippets(keywords, top_k=2)


async def run_coder(step: str, snippet: str) -> str:
    code = await chat(
        messages=[
            {"role": "system", "content": CODER_SYSTEM},
            {"role": "user", "content": coder_user(step, "", snippet)},
        ],
        max_tokens=settings.coder_max_tokens,
    )
    code = _strip_fences(code)

    if not code or len(code) < 5:
        return "-- Ошибка: пустой ответ модели\nreturn nil"

    return code


async def run_fixer(code_block: str, error: str) -> str:
    fixed = await chat(
        messages=[
            {"role": "system", "content": FIXER_SYSTEM},
            {"role": "user", "content": fixer_user(code_block, error)},
        ],
        max_tokens=settings.coder_max_tokens,
    )
    return _strip_fences(fixed)


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:lua)?\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()

def _format_multistep_task(user_prompt: str, steps: list[str]) -> str:
    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))
    return (
        f"{user_prompt}\n\n"
        f"Implement as ONE coherent Lua script (single file, no duplicate "
        f"functions, no top-level returns between functions). "
        f"Sub-tasks to cover:\n{numbered}"
    )


def _merge_steps(step_codes: list[tuple[str, str]]) -> str:
    return "\n\n".join([code for step, code in step_codes])

async def generate_code(user_prompt: str) -> str:
    log.info("Planner: generating plan for prompt=%r", user_prompt)
    plan = await run_planner(user_prompt)
    log.info("Plan has %d steps", len(plan.steps))

    if len(plan.steps) == 1:
        step = plan.steps[0]
        log.info("Step: %s", step)
        snippet = run_searcher(step)
        full_code = await run_coder(step, snippet)
    else:
        combined_task = _format_multistep_task(user_prompt, plan.steps)
        log.info("Multi-step task (%d steps) merged into single coder call", len(plan.steps))
        snippet = run_searcher(user_prompt)
        full_code = await run_coder(combined_task, snippet)

    full_code = await _fix_loop(full_code)

    return full_code


async def _fix_loop(full_code: str) -> str:
    for cycle in range(1, settings.max_fix_cycles + 1):
        result: ValidationResult = validate(full_code)
        if result.success:
            log.info("Validation passed on cycle %d", cycle)
            return full_code

        log.warning("Validation failed (cycle %d): %d errors", cycle, len(result.errors))

        err: ErrorDetail = result.errors[0]
        block_to_fix = err.code_block

        occurrences = full_code.count(block_to_fix) if block_to_fix else 0
        if occurrences == 1:
            fixed_block = await run_fixer(block_to_fix, err.message)
            full_code = full_code.replace(block_to_fix, fixed_block, 1)
        else:
            full_code = await run_fixer(full_code, err.message)

    result = validate(full_code)
    if result.success:
        return full_code

    raise PipelineError(
        message="Не удалось исправить ошибки после нескольких попыток.",
        errors=result.errors,
        code=full_code,
    )


class PipelineError(Exception):
    def __init__(self, message: str, errors: list[ErrorDetail], code: str):
        super().__init__(message)
        self.errors = errors
        self.code = code

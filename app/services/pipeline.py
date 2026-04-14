"""
pipeline.py — оркестратор: Planner → Searcher → Coder → Validator/Fixer.
"""

from __future__ import annotations
import logging
import re

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
        if isinstance(raw, list):
            return Plan(steps=raw)
        return Plan(**raw)
    except Exception as e:
        log.warning("Planner failed: %s. Fallback to 1 step.", e)
        # Если JSON сломался — делаем один шаг из всего промпта
        return Plan(steps=[user_prompt])


def run_searcher(step: str) -> str:
    # Берем ключевые слова из шага для RAG
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
    text = re.sub(r'<[^>]*>', '', text)

    text = re.sub(r'"{1,2}(kw|cmt|str|num|fn|op|tag)"?\s*>?\s*', '', text)

    text = re.sub(r"^```(?:lua)?\s*\n?", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\n?```$", "", text.strip())

    lua_start = re.search(
        r"(?i)^(.*?)(?=\bfunction\b|\blocal\b|\breturn\b|\bif\b|\bfor\b|\bwhile\b|--)",
        text
    )
    if lua_start and lua_start.lastindex and lua_start.lastindex >= 2:
        text = text[lua_start.start(2):]

    text = re.sub(r'^[^a-zA-Z0-9_-]+', '', text)

    return text.strip()

def _merge_steps(step_codes: list[tuple[str, str]]) -> str:
    return "\n\n".join([code for step, code in step_codes])

async def generate_code(user_prompt: str) -> str:
    log.info("Planner: generating plan for prompt=%r", user_prompt)
    plan = await run_planner(user_prompt)
    log.info("Plan has %d steps", len(plan.steps))

    step_codes: list[tuple[str, str]] = []
    for step in plan.steps:
        log.info("Step: %s", step)
        snippet = run_searcher(step)
        code = await run_coder(step, snippet)
        step_codes.append((step, code))

    full_code = _merge_steps(step_codes)
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
        fixed_block = await run_fixer(block_to_fix, err.message)

        if block_to_fix in full_code:
            full_code = full_code.replace(block_to_fix, fixed_block, 1)
        else:
            full_code = fixed_block

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

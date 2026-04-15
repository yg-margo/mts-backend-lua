"""
pipeline.py — оркестратор: Clarifier → Planner → Searcher → LuaNode → Validator/Fixer.

LuaNode is the final stage: it produces a complete Lua script plus an
algorithmically-inferred input contract (the set of `input.<field>` paths the
script reads from). The HTTP layer returns both so the frontend can auto-fill
the connected InputNode.
"""

from __future__ import annotations
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from app.core.config import settings
from app.services.llm_client import chat, chat_json, chat_stream
from app.models.models import ClarifierResult, ErrorDetail, Plan, ValidationResult

Emit = Callable[[dict], Awaitable[None]] | None
from app.services.prompts import (
    CLARIFIER_SYSTEM,
    LUA_NODE_SYSTEM,
    LUA_NODE_EDIT_SYSTEM,
    FIXER_SYSTEM,
    PLANNER_SYSTEM,
    clarifier_user,
    lua_node_user,
    lua_node_edit_user,
    fixer_user,
    planner_user,
)
from app.services.chat_sessions import is_edit_intent, truncate_code_for_context
from app.services.chunker import PackResult, chunk_lua, pack_chunks
from app.services.input_extractor import extract_entry_point, extract_inputs
from app.services.rag import search_snippets
from app.services.validator import validate

log = logging.getLogger(__name__)


# Минимальный guard от «ку»-образного мусора: нужна хоть какая-то буква и ≥3 символа,
# иначе не стартуем пайплайн (иначе получим заглушку вроде `function understandTask ... end`).
def _is_task_like(prompt: str) -> bool:
    s = (prompt or "").strip()
    if len(s) < 3:
        return False
    return bool(re.search(r"[A-Za-zА-Яа-яЁё]", s))


# На бессмысленный ввод lua_node иногда отдаёт английскую прозу вида
# "I'm sorry, but I don't understand...". Fixer тогда оборачивает её в
# fake-Lua (`function understandTask(task) return ... end`) и валидатор
# это принимает. Грубая проверка «есть ли в тексте хоть один Lua-токен»
# ловит такие случаи до fixer'а.
# Ключевые слова намеренно сужены до Lua-специфичных (function/local/elseif/
# nil/repeat/until) плюс `return` — он обязателен в выводе lua_node согласно
# LUA_NODE_SYSTEM. Общеанглийские if/do/for/true/false убраны, чтобы не ловить
# прозу. `\w+\(` требует вызова функции (а не одиночной скобки в прозе).
_LUA_TOKEN_RE = re.compile(
    r"\b(function|local|elseif|nil|repeat|until|return)\b"
    r"|="
    r"|\.\."
    r"|\w+\("
)


def _looks_like_lua(code: str) -> bool:
    return bool(_LUA_TOKEN_RE.search(code or ""))


@dataclass
class GenerationOutcome:
    """Результат первого шага пайплайна: либо код + inputs, либо вопросы."""
    code: str | None = None
    inputs: dict[str, Any] = field(default_factory=dict)
    entry_point: dict[str, Any] | None = None
    questions: list[str] | None = None


async def run_clarifier(user_prompt: str) -> ClarifierResult:
    raw_text = ""
    try:
        raw_text = await chat(
            messages=[
                {"role": "system", "content": CLARIFIER_SYSTEM},
                {"role": "user", "content": clarifier_user(user_prompt)},
            ],
            max_tokens=settings.clarifier_max_tokens,
            expect_json=True,
        )
        log.info("Clarifier raw: %.500s", raw_text)
        raw = json.loads(raw_text)

        if isinstance(raw, list):
            items = raw
        elif isinstance(raw, dict):
            items = raw.get("questions", [])
            if not isinstance(items, list):
                items = []
        else:
            items = []

        cleaned: list[str] = []
        for q in items:
            if q is None:
                continue
            text = str(q).strip()
            # отсекаем мусорные "ответы" типа пустых/слишком коротких строк
            if len(text) >= 3:
                cleaned.append(text)

        # max 2 вопроса — страховка от разговорчивой модели
        return ClarifierResult(questions=cleaned[:2])
    except Exception as e:
        # fail-open: если clarifier сломался — считаем задачу ясной и идём дальше.
        # raw_text логируем, чтобы отличить "модель вернула []" от "JSON битый".
        log.warning(
            "Clarifier failed: %s. Raw: %.500s. Treating prompt as clear.",
            e,
            raw_text,
        )
        return ClarifierResult(questions=[])


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


async def run_searcher(step: str) -> str:
    # Hybrid BM25 + dense + RRF; токенизация/стоп-слова — внутри search_snippets.
    return await search_snippets(step)


async def run_lua_node(
    step: str,
    snippet: str,
    hints: list[str] | None = None,
    emit: Emit = None,
) -> str:
    messages = [
        {"role": "system", "content": LUA_NODE_SYSTEM},
        {"role": "user", "content": lua_node_user(step, "", snippet, hints=hints)},
    ]
    if emit is None:
        code = await chat(messages=messages, max_tokens=settings.lua_node_max_tokens)
    else:
        async def on_token(t: str) -> None:
            await emit({"type": "token", "stage": "coder", "text": t})

        code = await chat_stream(
            messages=messages,
            max_tokens=settings.lua_node_max_tokens,
            on_token=on_token,
        )

    code = _strip_fences(code)

    if not code or len(code) < 5:
        return "-- Ошибка: пустой ответ модели\nreturn nil"

    return code


async def run_lua_node_edit(
    edit_request: str,
    previous_code: str,
    emit: Emit = None,
) -> str:
    """Одноходовая правка существующего Lua-артефакта.

    Один LLM-вызов, ≤ lua_node_max_tokens (=256) output-токенов. Planner и
    searcher намеренно пропускаем: RAG-сниппеты конкурировали бы за input-токены
    с previous_code, а сам previous_code уже содержит всё необходимое для
    локальной правки.
    """
    messages = [
        {"role": "system", "content": LUA_NODE_EDIT_SYSTEM},
        {
            "role": "user",
            "content": lua_node_edit_user(
                edit_request, truncate_code_for_context(previous_code)
            ),
        },
    ]
    if emit is None:
        code = await chat(messages=messages, max_tokens=settings.lua_node_max_tokens)
    else:
        async def on_token(t: str) -> None:
            await emit({"type": "token", "stage": "coder", "text": t})

        code = await chat_stream(
            messages=messages,
            max_tokens=settings.lua_node_max_tokens,
            on_token=on_token,
        )

    code = _strip_fences(code)
    if not code or len(code) < 5:
        # На правке лучше вернуть исходник, чем заглушку — пользователь увидит
        # что модель ничего не меняла и сможет переформулировать.
        return previous_code
    return code


async def run_fixer(
    code_block: str,
    error: str,
    emit: Emit = None,
    cycle: int | None = None,
) -> str:
    messages = [
        {"role": "system", "content": FIXER_SYSTEM},
        {"role": "user", "content": fixer_user(code_block, error)},
    ]
    if emit is None:
        fixed = await chat(messages=messages, max_tokens=settings.lua_node_max_tokens)
    else:
        async def on_token(t: str) -> None:
            await emit(
                {"type": "token", "stage": "fixer", "text": t, "cycle": cycle}
            )

        fixed = await chat_stream(
            messages=messages,
            max_tokens=settings.lua_node_max_tokens,
            on_token=on_token,
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


def _enrich_with_clarifications(prompt: str, qa: list[tuple[str, str]]) -> str:
    base = prompt.strip()
    lines: list[str] = []
    for q, a in qa:
        q_clean = (q or "").strip()
        a_clean = (a or "").strip()
        if q_clean and a_clean:
            lines.append(f"- {q_clean}: {a_clean}")
    if not lines:
        return base
    return f"{base}\n\nAdditional details:\n" + "\n".join(lines)


_NUMBERED_STEPS_RE = re.compile(r"(?m)^\s*\d+[.)]\s")


def _looks_single_task(prompt: str) -> bool:
    # Если промпт короткий и без нумерованных шагов — planner ничего не
    # добавит, кроме 10–15с латентности. Консервативный порог длины: enriched
    # (prompt + clarifier Q&A) в benchmark'е не превышает ~350 символов.
    if len(prompt) > 800:
        return False
    if _NUMBERED_STEPS_RE.search(prompt):
        return False
    return True


# Маркеры размытости, которые CLARIFIER_SYSTEM (prompts.py) уже считает
# неконкретными. Если ни один маркер не встречается в коротком промпте —
# clarifier почти гарантированно вернёт [], и его можно пропустить.
_VAGUE_MARKERS_RE = re.compile(
    r"\b(?:something|stuff|thing|кое|что-то|что-нибудь|какой-то|какой-нибудь|штук[ауи])\b",
    re.IGNORECASE,
)


def _clarifier_fast_path(prompt: str) -> bool:
    s = prompt.strip()
    if len(s) > 60:
        return False
    if _VAGUE_MARKERS_RE.search(s):
        return False
    return True


async def _emit_stage(emit: Emit, stage: str, **extra: Any) -> None:
    if emit is None:
        return
    await emit({"type": "stage", "stage": stage, **extra})


async def _emit_validator(emit: Emit, result: ValidationResult) -> None:
    if emit is None:
        return
    await emit(
        {
            "type": "validator",
            "success": result.success,
            "errors": [
                {"line": e.line, "message": e.message} for e in result.errors
            ],
        }
    )


async def _plan_and_code(user_prompt: str, emit: Emit = None) -> str:
    """Общий пост-clarifier пайплайн: [planner →] searcher → lua_node → fix loop."""
    if _looks_single_task(user_prompt):
        log.info("[pipeline] single-task shortcut: skipping planner")
        await _emit_stage(emit, "searcher")
        t = time.perf_counter()
        snippet = await run_searcher(user_prompt)
        log.info("[pipeline] searcher done in %.2fs (snippet_chars=%d)", time.perf_counter() - t, len(snippet))
        if emit is not None:
            await emit({"type": "snippet", "preview": snippet[:200]})
        await _emit_stage(emit, "coder")
        t = time.perf_counter()
        full_code = await run_lua_node(user_prompt, snippet, emit=emit)
        log.info("[pipeline] coder done in %.2fs (code_chars=%d)", time.perf_counter() - t, len(full_code))
        if emit is not None:
            await emit({"type": "stage_done", "stage": "coder", "code": full_code})
        return await _fix_loop(full_code, emit=emit)

    log.info("Planner: generating plan for prompt=%r", user_prompt)
    await _emit_stage(emit, "planner")
    plan = await run_planner(user_prompt)
    log.info("Plan has %d steps", len(plan.steps))
    if emit is not None:
        await emit({"type": "plan", "steps": plan.steps})

    await _emit_stage(emit, "searcher")
    if len(plan.steps) == 1:
        step = plan.steps[0]
        log.info("Step: %s", step)
        snippet = await run_searcher(step)
        if emit is not None:
            await emit({"type": "snippet", "preview": snippet[:200]})
        await _emit_stage(emit, "coder")
        full_code = await run_lua_node(step, snippet, emit=emit)
    else:
        combined_task = _format_multistep_task(user_prompt, plan.steps)
        log.info("Multi-step task (%d steps) merged into single lua_node call", len(plan.steps))
        snippet = await run_searcher(user_prompt)
        if emit is not None:
            await emit({"type": "snippet", "preview": snippet[:200]})
        await _emit_stage(emit, "coder")
        full_code = await run_lua_node(combined_task, snippet, emit=emit)

    if emit is not None:
        await emit({"type": "stage_done", "stage": "coder", "code": full_code})
    return await _fix_loop(full_code, emit=emit)


async def generate_code(
    user_prompt: str,
    emit: Emit = None,
    previous_code: str | None = None,
) -> GenerationOutcome:
    """Полный пайплайн нового запроса: сначала clarifier, потом (опционально) код.

    Если передан previous_code и промпт выглядит как правка (is_edit_intent),
    идём по короткой ветке: только coder + fixer, без clarifier/planner/searcher.
    """
    log.info("[pipeline] === START prompt=%r (len=%d) ===", user_prompt[:80], len(user_prompt))
    t_total = time.perf_counter()

    if not _is_task_like(user_prompt):
        msg = (
            "Опиши задачу полнее — что должна делать Lua-нода, "
            "какие поля ждёт на входе, что возвращать."
        )
        log.info("[pipeline] rejected non-task prompt: %r", (user_prompt or "")[:80])
        if emit is not None:
            await emit({"type": "error", "message": msg})
        return GenerationOutcome(questions=[msg])

    if previous_code and is_edit_intent(user_prompt):
        log.info("[pipeline] edit branch: previous_code=%d chars", len(previous_code))
        await _emit_stage(emit, "coder")
        t = time.perf_counter()
        full_code = await run_lua_node_edit(user_prompt, previous_code, emit=emit)
        log.info("[pipeline] coder (edit) done in %.2fs (code_chars=%d)",
                 time.perf_counter() - t, len(full_code))
        if emit is not None:
            await emit({"type": "stage_done", "stage": "coder", "code": full_code})
        code = await _fix_loop(full_code, emit=emit)
        ep = extract_entry_point(code)
        log.info("[pipeline] === END in %.2fs (edit, code_chars=%d) ===",
                 time.perf_counter() - t_total, len(code))
        return GenerationOutcome(
            code=code,
            inputs=extract_inputs(code, params=ep["params"] if ep else None),
            entry_point=ep,
        )

    await _emit_stage(emit, "clarifier")
    if _clarifier_fast_path(user_prompt):
        log.info("[pipeline] clarifier fast-path: skipping LLM call (len=%d)",
                 len(user_prompt))
        if emit is not None:
            await emit({"type": "stage_done", "stage": "clarifier", "skipped": True})
    else:
        t = time.perf_counter()
        clarification = await run_clarifier(user_prompt)
        log.info("[pipeline] clarifier done in %.2fs (questions=%d)",
                 time.perf_counter() - t, len(clarification.questions or []))
        if clarification.questions:
            log.info("[pipeline] Clarifier returned questions; pausing pipeline")
            log.info("[pipeline] === END in %.2fs (clarification) ===", time.perf_counter() - t_total)
            return GenerationOutcome(questions=clarification.questions)
        log.info("[pipeline] Clarifier clear, proceeding")

    code = await _plan_and_code(user_prompt, emit=emit)
    ep = extract_entry_point(code)
    log.info("[pipeline] === END in %.2fs (code_chars=%d) ===", time.perf_counter() - t_total, len(code))
    return GenerationOutcome(
        code=code,
        inputs=extract_inputs(code, params=ep["params"] if ep else None),
        entry_point=ep,
    )


async def generate_code_from_clarified(
    original_prompt: str,
    qa: list[tuple[str, str]],
    emit: Emit = None,
) -> GenerationOutcome:
    """Follow-up после уточнений: clarifier пропускаем, идём сразу в планер."""
    enriched = _enrich_with_clarifications(original_prompt, qa)
    log.info("Resuming after clarification, enriched prompt length=%d", len(enriched))
    code = await _plan_and_code(enriched, emit=emit)
    ep = extract_entry_point(code)
    return GenerationOutcome(
        code=code,
        inputs=extract_inputs(code, params=ep["params"] if ep else None),
        entry_point=ep,
    )


async def _fix_loop(full_code: str, emit: Emit = None) -> str:
    # Если lua_node вернул чистую прозу (англ. "I'm sorry..." и т.п.) —
    # fixer всё равно «починит» это в fake-Lua. Лучше сразу 422 с понятным
    # сообщением, чем отдавать пользователю мусорный скрипт.
    if not _looks_like_lua(full_code):
        log.warning(
            "[pipeline] lua_node returned non-Lua content (%d chars); "
            "skipping fix loop",
            len(full_code),
        )
        raise PipelineError(
            message=(
                "Модель не смогла интерпретировать запрос как Lua-задачу. "
                "Переформулируйте задачу — опишите, что нужно реализовать."
            ),
            errors=[],
            code=full_code,
        )

    for cycle in range(1, settings.max_fix_cycles + 1):
        await _emit_stage(emit, "validator", cycle=cycle)
        result: ValidationResult = validate(full_code)
        await _emit_validator(emit, result)
        if result.success:
            log.info("Validation passed on cycle %d", cycle)
            return full_code

        log.warning("Validation failed (cycle %d): %d errors", cycle, len(result.errors))

        err: ErrorDetail = result.errors[0]
        block_to_fix = err.code_block

        await _emit_stage(emit, "fixer", cycle=cycle, error=err.message)
        occurrences = full_code.count(block_to_fix) if block_to_fix else 0
        if occurrences == 1:
            fixed_block = await run_fixer(
                block_to_fix, err.message, emit=emit, cycle=cycle
            )
            full_code = full_code.replace(block_to_fix, fixed_block, 1)
        else:
            # блок не уникален (или не найден) — переписываем весь файл целиком,
            # иначе str.replace либо правит не тот кусок, либо стирает всё остальное.
            full_code = await run_fixer(
                full_code, err.message, emit=emit, cycle=cycle
            )
        if emit is not None:
            await emit(
                {"type": "stage_done", "stage": "fixer", "cycle": cycle, "code": full_code}
            )

    await _emit_stage(emit, "validator", cycle=settings.max_fix_cycles + 1, final=True)
    result = validate(full_code)
    await _emit_validator(emit, result)
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


# ---------------------------------------------------------------------------
# /generate-from-context flow — user-composed nodes drive the lua_node context
# instead of RAG retrieval. Clarifier is skipped by design (building nodes
# IS the clarification step).
# ---------------------------------------------------------------------------


@dataclass
class ContextGenerationOutcome:
    code: str
    used_tokens: int
    kept_chunks: int
    total_chunks: int
    inputs: dict[str, Any] = field(default_factory=dict)
    entry_point: dict[str, Any] | None = None


def _split_blocks(blocks: list) -> tuple[list[str], list[str], list[str]]:
    """Sort context blocks by kind, preserving authoring order within each."""
    prompts: list[str] = []
    examples: list[str] = []
    hints: list[str] = []
    for b in blocks or []:
        kind = getattr(b, "kind", None)
        content = (getattr(b, "content", "") or "").strip()
        if not content:
            continue
        if kind == "prompt":
            prompts.append(content)
        elif kind == "example":
            examples.append(content)
        elif kind == "hint":
            hints.append(content)
    return prompts, examples, hints


def _query_from(prompt: str, hints: list[str]) -> str:
    return prompt + " " + " ".join(hints)


async def generate_code_from_context(
    prompt: str,
    blocks: list,
) -> ContextGenerationOutcome:
    """
    Generate Lua from a user-composed node graph.

    - Prompt-blocks are appended to the main prompt (never issued as separate
      LLM calls — that would break the 256-output-token rule).
    - Example-blocks pass through tree-sitter chunking + tiktoken packing.
    - Hint-blocks are appended to the lua_node user message as a bullet list.
    - Planner + fix loop run unchanged.
    """
    prompts, examples, hints = _split_blocks(blocks)

    merged_prompt = prompt.strip()
    if prompts:
        merged_prompt = merged_prompt + "\n\n" + "\n\n".join(prompts)

    joined_examples = "\n\n".join(examples)
    chunks = chunk_lua(joined_examples) if joined_examples else []
    query = _query_from(merged_prompt, hints)
    pack: PackResult = pack_chunks(
        chunks, query, settings.context_budget_tokens
    )

    log.info(
        "context: blocks=%d (prompt=%d example=%d hint=%d) chunks=%d kept=%d tokens=%d",
        len(blocks or []),
        len(prompts),
        len(examples),
        len(hints),
        pack.total,
        pack.kept,
        pack.used_tokens,
    )

    plan = await run_planner(merged_prompt)
    if len(plan.steps) == 1:
        step = plan.steps[0]
        full_code = await run_lua_node(step, pack.snippet, hints=hints)
    else:
        combined_task = _format_multistep_task(merged_prompt, plan.steps)
        full_code = await run_lua_node(combined_task, pack.snippet, hints=hints)

    final_code = await _fix_loop(full_code)
    ep = extract_entry_point(final_code)
    return ContextGenerationOutcome(
        code=final_code,
        used_tokens=pack.used_tokens,
        kept_chunks=pack.kept,
        total_chunks=pack.total,
        inputs=extract_inputs(final_code, params=ep["params"] if ep else None),
        entry_point=ep,
    )

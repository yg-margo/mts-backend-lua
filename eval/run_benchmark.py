"""
run_benchmark.py — прогон пайплайна по eval/kong_benchmark.yaml
и замер трёх метрик:
  1. pipeline_completion_rate — доля задач, где пайплайн вернул код
     без exception/timeout (clarifier-с-вопросами считается не-completion)
  2. syntax_valid_rate        — luac -p на сгенерированном коде
  3. llm_judge_score          — средняя оценка 1-5 от того же Qwen

Запуск (из mts-backend-lua/):
    python -m eval.run_benchmark
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

import yaml

# Запуск из mts-backend-lua/ — иначе env_file = "../../.env" в config.py не
# резолвится, и .env молча игнорируется.
REPO_ROOT = Path(__file__).resolve().parent.parent
if Path.cwd() != REPO_ROOT:
    os.chdir(REPO_ROOT)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.pipeline import (
    GenerationOutcome,
    PipelineError,
    generate_code,
    generate_code_from_clarified,
)
from app.services.llm_client import chat
from app.services.validator import validate
from app.core.config import settings

TIMEOUT_SEC = 90
REFERENCE_MAX_CHARS = 2000
JUDGE_MAX_TOKENS = 10
DEFAULT_CLARIFIER_ANSWER = "Используй разумные значения по умолчанию"

JUDGE_TEMPLATE = """Оцени по шкале 1-5 насколько сгенерированный Lua-код решает задачу.
Задача: {task}
Сгенерированный код:
{generated}

Эталон (для справки):
{reference}

Верни только одно число от 1 до 5 без пояснений.
5 = полностью решает, идиоматичный код
4 = решает, но неоптимально
3 = частично решает, есть логические проблемы
2 = не решает, но близко к теме
1 = не решает совсем"""


async def score_judge(task: str, generated: str, reference: str) -> int | None:
    ref = reference
    if len(ref) > REFERENCE_MAX_CHARS:
        ref = ref[:REFERENCE_MAX_CHARS] + "\n-- (reference truncated)"
    prompt = JUDGE_TEMPLATE.format(task=task, generated=generated, reference=ref)
    try:
        resp = await chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=JUDGE_MAX_TOKENS,
            temperature=0.0,
        )
    except Exception as e:
        print(f"    judge call failed: {e}", file=sys.stderr)
        return None
    m = re.search(r"[1-5]", resp)
    return int(m.group(0)) if m else None


async def _generate_auto_clarifier(task_desc: str) -> tuple[str | None, int]:
    """
    Полный пайплайн, но если clarifier спросил — отвечаем дефолтом и идём дальше.
    Возвращает (code, clarifier_questions_count).
    """
    outcome: GenerationOutcome = await generate_code(task_desc)
    if outcome.code is not None:
        return outcome.code, 0

    questions = outcome.questions or []
    if not questions:
        return None, 0

    qa = [(q, DEFAULT_CLARIFIER_ANSWER) for q in questions]
    clarified: GenerationOutcome = await generate_code_from_clarified(task_desc, qa)
    return clarified.code, len(questions)


async def run_one(entry: dict) -> dict:
    task_id = entry["id"]
    task_desc = entry["task_description"]
    reference = entry["reference_code"]

    generated: str | None = None
    completed = False
    clarifier_qs = 0
    error: str | None = None

    t0 = time.monotonic()
    try:
        generated, clarifier_qs = await asyncio.wait_for(
            _generate_auto_clarifier(task_desc), timeout=TIMEOUT_SEC
        )
        if generated:
            completed = True
        else:
            error = "pipeline returned no code"
    except asyncio.TimeoutError:
        error = f"timeout after {TIMEOUT_SEC}s"
    except PipelineError as e:
        generated = e.code  # partial code available
        error = f"PipelineError: {e}"
    except Exception as e:
        error = f"{type(e).__name__}: {e}"

    elapsed = time.monotonic() - t0

    syntax_valid = False
    if generated:
        try:
            syntax_valid = validate(generated).success
        except Exception as e:
            error = (error or "") + f" | validate: {e}"

    judge_score: int | None = None
    if generated:
        judge_score = await score_judge(task_desc, generated, reference)

    return {
        "id": task_id,
        "category": entry["category"],
        "complexity": entry["complexity"],
        "completed": completed,
        "syntax_valid": syntax_valid,
        "judge_score": judge_score,
        "clarifier_questions": clarifier_qs,
        "elapsed_sec": round(elapsed, 1),
        "error": error,
        "generated": generated,
    }


def _rate(results: list[dict], key: str) -> float:
    return sum(bool(r[key]) for r in results) / len(results) if results else 0.0


def _judge_avg(results: list[dict]) -> tuple[float, int]:
    scores = [r["judge_score"] for r in results if r["judge_score"] is not None]
    if not scores:
        return 0.0, 0
    return sum(scores) / len(scores), len(scores)


async def main() -> None:
    bench_path = Path("eval/kong_benchmark.yaml")
    entries = yaml.safe_load(bench_path.read_text(encoding="utf-8"))
    n = len(entries)

    print(f"Model: {settings.llm_model} @ {settings.llm_base_url}")
    print(f"Running {n} tasks (per-task timeout {TIMEOUT_SEC}s)\n")

    results: list[dict] = []
    for i, e in enumerate(entries, 1):
        print(f"[{i:2d}/{n}] {e['id']:38s} ", end="", flush=True)
        r = await run_one(e)
        c = "✓" if r["completed"] else "✗"
        l = "L=✓" if r["syntax_valid"] else "L=✗"
        j = f"J={r['judge_score']}" if r["judge_score"] is not None else "J=—"
        q = f" q={r['clarifier_questions']}" if r["clarifier_questions"] else ""
        err = f"  ({r['error']})" if r["error"] else ""
        print(f"{c} {l} {j} {r['elapsed_sec']:5.1f}s{q}{err}")
        results.append(r)

    completion_rate = _rate(results, "completed")
    syntax_rate = _rate(results, "syntax_valid")
    judge_avg, judge_n = _judge_avg(results)

    clarifier_triggered = sum(1 for r in results if r["clarifier_questions"] > 0)
    summary = {
        "model": settings.llm_model,
        "timeout_sec": TIMEOUT_SEC,
        "total": n,
        "clarifier_triggered": clarifier_triggered,
        "clarifier_default_answer": DEFAULT_CLARIFIER_ANSWER,
        "pipeline_completion_rate": completion_rate,
        "syntax_valid_rate": syntax_rate,
        "llm_judge_avg": judge_avg,
        "llm_judge_n": judge_n,
        "results": results,
    }

    out_path = Path("eval/benchmark_results.json")
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 72)
    print(f"pipeline_completion_rate: {completion_rate:.2%}  ({sum(r['completed'] for r in results)}/{n})")
    print(f"syntax_valid_rate:        {syntax_rate:.2%}  ({sum(r['syntax_valid'] for r in results)}/{n})")
    print(f"llm_judge_score (avg):    {judge_avg:.2f} / 5  (over {judge_n} judged)")
    print(f"clarifier_triggered:      {clarifier_triggered}/{n}  (auto-answered: {DEFAULT_CLARIFIER_ANSWER!r})")
    print("=" * 72)

    print("\nBy complexity:")
    for cx in ("simple", "medium", "hard"):
        group = [r for r in results if r["complexity"] == cx]
        if not group:
            continue
        cc = _rate(group, "completed")
        sv = _rate(group, "syntax_valid")
        ja, _ = _judge_avg(group)
        print(f"  {cx:7s} n={len(group)}  completion={cc:.0%}  syntax={sv:.0%}  judge={ja:.2f}")

    print("\nBy category:")
    cats = sorted({r["category"] for r in results})
    for cat in cats:
        group = [r for r in results if r["category"] == cat]
        cc = _rate(group, "completed")
        sv = _rate(group, "syntax_valid")
        ja, _ = _judge_avg(group)
        print(f"  {cat:14s} n={len(group)}  completion={cc:.0%}  syntax={sv:.0%}  judge={ja:.2f}")

    print(f"\nDetailed results: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())

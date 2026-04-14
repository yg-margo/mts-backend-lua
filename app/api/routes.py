"""
api/routes.py — FastAPI-роутер.
"""

from __future__ import annotations
import asyncio
import contextlib
import logging
import time
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.models.models import (
    ClarificationPayload,
    GenerateFromContextRequest,
    GenerateFromContextResponse,
    GenerateRequest,
    GenerateResponse,
)
from app.services import sessions
from app.services.pipeline import (
    PipelineError,
    generate_code,
    generate_code_from_clarified,
    generate_code_from_context,
)

log = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/generate",
    response_model=GenerateResponse,
    summary="Сгенерировать код по тексту задачи (с возможным шагом уточнения)",
    operation_id="generate",
    tags=["codegen"],
    responses={
        200: {
            "description": (
                "Либо готовый Lua-код (поле `code`), либо запрос уточнений "
                "(поле `clarification` с `session_id` и списком `questions`)."
            ),
            "content": {
                "application/json": {
                    "examples": {
                        "code": {
                            "summary": "Готовый код",
                            "value": {
                                "code": (
                                    "function factorial(n)\n"
                                    "  if n <= 1 then return 1 end\n"
                                    "  return n * factorial(n - 1)\n"
                                    "end"
                                )
                            },
                        },
                        "clarification": {
                            "summary": "Нужны уточнения",
                            "value": {
                                "clarification": {
                                    "session_id": "9f1a...e7",
                                    "questions": [
                                        "Where does the data come from?",
                                        "What should be returned?",
                                    ],
                                }
                            },
                        },
                    }
                }
            },
        },
        410: {
            "description": "Сессия уточнений истекла или не найдена",
            "content": {
                "application/json": {
                    "example": {"detail": "Clarification session expired or not found"}
                }
            },
        },
        422: {
            "description": "Модель не смогла исправить ошибки автоматически",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Не удалось исправить ошибки после нескольких попыток.",
                        "errors": [{"line": 3, "message": "'}' expected near 'end'"}],
                        "partial_code": "function factorial(n)\n  ...\n",
                        "hint": "Вы можете исправить код вручную или попробовать снова.",
                    }
                }
            },
        },
    },
)
async def generate(body: GenerateRequest) -> GenerateResponse:
    try:
        if body.session_id is not None:
            return await _handle_followup(body.session_id, body.answers or [])
        return await _handle_new_prompt(body.prompt or "")

    except HTTPException:
        raise

    except PipelineError as exc:
        error_details = [
            {"line": e.line, "message": e.message}
            for e in exc.errors
        ]
        log.error("PipelineError: %s | errors=%s", exc, error_details)
        raise HTTPException(
            status_code=422,
            detail={
                "message": str(exc),
                "errors": error_details,
                "partial_code": exc.code,
                "hint": (
                    "Модель не смогла автоматически исправить ошибки. "
                    "Вы можете исправить код вручную или попробовать снова."
                ),
            },
        )

    except Exception as exc:
        log.exception("Unexpected error in /generate")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/generate-from-context",
    response_model=GenerateFromContextResponse,
    summary="Сгенерировать код из пользовательского графа контекстных нод",
    operation_id="generate_from_context",
    tags=["codegen"],
    responses={
        422: {
            "description": "Модель не смогла исправить ошибки автоматически",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Не удалось исправить ошибки после нескольких попыток.",
                        "errors": [{"line": 3, "message": "'}' expected near 'end'"}],
                        "partial_code": "function sum(t)\n  ...\n",
                        "hint": "Проверьте соединения нод и повторите генерацию.",
                    }
                }
            },
        },
    },
)
async def generate_from_context(
    body: GenerateFromContextRequest,
) -> GenerateFromContextResponse:
    try:
        outcome = await generate_code_from_context(body.prompt, body.blocks)
        return GenerateFromContextResponse(
            code=outcome.code,
            used_tokens=outcome.used_tokens,
            kept_chunks=outcome.kept_chunks,
            total_chunks=outcome.total_chunks,
            inputs=outcome.inputs,
            entry_point=outcome.entry_point,
        )

    except HTTPException:
        raise

    except PipelineError as exc:
        error_details = [
            {"line": e.line, "message": e.message} for e in exc.errors
        ]
        log.error("PipelineError (context): %s | errors=%s", exc, error_details)
        raise HTTPException(
            status_code=422,
            detail={
                "message": str(exc),
                "errors": error_details,
                "partial_code": exc.code,
                "hint": (
                    "Модель не смогла автоматически исправить ошибки. "
                    "Проверьте соединения нод и попробуйте ещё раз."
                ),
            },
        )

    except Exception as exc:
        log.exception("Unexpected error in /generate-from-context")
        raise HTTPException(status_code=500, detail=str(exc))


@router.websocket("/generate/ws")
async def generate_ws(ws: WebSocket) -> None:
    """Stream the full pipeline over WebSocket.

    Client sends one JSON message ({"prompt": "..."} or {"session_id", "answers"}),
    then receives a stream of typed events (see WS protocol in the plan doc).
    """
    await ws.accept()
    try:
        body = await ws.receive_json()
    except WebSocketDisconnect:
        return
    except Exception as exc:
        log.warning("Bad initial WS payload: %s", exc)
        await _ws_send(ws, {"type": "error", "message": "Invalid JSON payload"})
        await ws.close()
        return

    prompt = (body or {}).get("prompt")
    session_id = (body or {}).get("session_id")
    answers = (body or {}).get("answers") or []

    async def emit(event: dict) -> None:
        await _ws_send(ws, event)

    log.info("[ws] accept prompt=%r session_id=%r", (prompt or "")[:80], session_id)
    ws_t0 = time.perf_counter()
    hb_task = asyncio.create_task(_heartbeat(ws))
    try:
        if session_id:
            session = sessions.peek(session_id)
            if session is None:
                await emit(
                    {"type": "error", "message": "Clarification session expired or not found"}
                )
                return
            if len(answers) != len(session.questions):
                await emit(
                    {
                        "type": "error",
                        "message": (
                            f"Expected {len(session.questions)} answer(s), got {len(answers)}."
                        ),
                    }
                )
                return
            sessions.pop(session_id)
            qa = list(zip(session.questions, answers))
            outcome = await generate_code_from_clarified(session.prompt, qa, emit=emit)
            await emit(
                {
                    "type": "done",
                    "code": outcome.code,
                    "inputs": outcome.inputs,
                    "entry_point": outcome.entry_point,
                }
            )
            return

        if not prompt:
            await emit({"type": "error", "message": "prompt or session_id required"})
            return

        outcome = await generate_code(prompt, emit=emit)
        if outcome.questions:
            sid = sessions.create(prompt, outcome.questions)
            await emit(
                {
                    "type": "clarification",
                    "session_id": sid,
                    "questions": outcome.questions,
                }
            )
            return

        await emit(
            {
                "type": "done",
                "code": outcome.code,
                "inputs": outcome.inputs,
                "entry_point": outcome.entry_point,
            }
        )

    except PipelineError as exc:
        error_details = [{"line": e.line, "message": e.message} for e in exc.errors]
        log.error("PipelineError (ws): %s | errors=%s", exc, error_details)
        await emit(
            {
                "type": "error",
                "message": str(exc),
                "errors": error_details,
                "partial_code": exc.code,
                "hint": (
                    "Модель не смогла автоматически исправить ошибки. "
                    "Вы можете исправить код вручную или попробовать снова."
                ),
            }
        )
    except WebSocketDisconnect:
        log.info("WS disconnected mid-generation")
        return
    except Exception as exc:
        log.exception("Unexpected error in /generate/ws")
        await emit({"type": "error", "message": str(exc)})
    finally:
        log.info("[ws] total %.2fs", time.perf_counter() - ws_t0)
        hb_task.cancel()
        with contextlib.suppress(BaseException):
            await hb_task
        try:
            await ws.close()
        except Exception:
            pass


async def _heartbeat(ws: WebSocket, period: float = 15.0) -> None:
    try:
        while True:
            await asyncio.sleep(period)
            await _ws_send(ws, {"type": "heartbeat", "t": time.time()})
    except asyncio.CancelledError:
        return


async def _ws_send(ws: WebSocket, event: dict) -> None:
    try:
        await ws.send_json(event)
    except WebSocketDisconnect:
        raise
    except Exception as exc:
        log.warning("WS send failed: %s", exc)


async def _handle_new_prompt(prompt: str) -> GenerateResponse:
    outcome = await generate_code(prompt)

    if outcome.questions:
        sid = sessions.create(prompt, outcome.questions)
        return GenerateResponse(
            clarification=ClarificationPayload(
                session_id=sid, questions=outcome.questions
            )
        )

    return GenerateResponse(
        code=outcome.code,
        inputs=outcome.inputs,
        entry_point=outcome.entry_point,
    )


async def _handle_followup(session_id: str, answers: list[str]) -> GenerateResponse:
    # peek сначала — если длина ответов не совпала, сессия ещё должна быть
    # доступна для повторной отправки.
    session = sessions.peek(session_id)
    if session is None:
        raise HTTPException(
            status_code=410,
            detail="Clarification session expired or not found",
        )

    if len(answers) != len(session.questions):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Expected {len(session.questions)} answer(s), got {len(answers)}."
            ),
        )

    sessions.pop(session_id)
    qa = list(zip(session.questions, answers))
    outcome = await generate_code_from_clarified(session.prompt, qa)
    return GenerateResponse(
        code=outcome.code,
        inputs=outcome.inputs,
        entry_point=outcome.entry_point,
    )

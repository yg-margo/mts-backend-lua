"""
api/routes.py — FastAPI-роутер.
"""

from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException
from app.models.models import GenerateRequest, GenerateResponse
from app.services.pipeline import PipelineError, generate_code

log = logging.getLogger(__name__)
router = APIRouter()

@router.post(
    "/generate",
    response_model=GenerateResponse,
    summary="Сгенерировать код по тексту задачи",
    operation_id="generate",
    tags=["codegen"],
    responses={
        200: {
            "description": "Успешно сгенерированный Lua-код",
            "content": {
                "application/json": {
                    "example": {
                        "code": (
                            "function factorial(n)\n"
                            "  if n <= 1 then return 1 end\n"
                            "  return n * factorial(n - 1)\n"
                            "end"
                        )
                    }
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
        code = await generate_code(body.prompt)
        return GenerateResponse(code=code)

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

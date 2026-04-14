"""
LocalScript API — entry point
FastAPI app, mounts all routers.

Swagger UI  →  http://localhost:8080/docs
ReDoc       →  http://localhost:8080/redoc
Sandbox     →  http://localhost:8080/sandbox
OpenAPI JSON→  http://localhost:8080/openapi.json
"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pathlib import Path
from app.api.routes import router

app = FastAPI(
    title="LocalScript API",
    description=(
        "**LLM-powered Lua code generator** для платформы MWS Octapi / LowCode.\n\n"
        "Pipeline: `Planner → RAG Searcher → Coder → Validator → Fixer`\n\n"
        "Swagger UI: [/docs](/docs) · ReDoc: [/redoc](/redoc) · Sandbox: [/sandbox](/sandbox)"
    ),
    version="1.0.0",
    docs_url="/docs",        # Swagger UI
    redoc_url="/redoc",      # ReDoc
    openapi_url="/openapi.json",
    contact={
        "name": "LocalScript",
        "url": "http://localhost:8080",
    },
    license_info={
        "name": "MIT",
    },
    openapi_tags=[
        {
            "name": "codegen",
            "description": "Генерация Lua-кода по текстовому описанию задачи.",
        }
    ],
    servers=[{"url": "http://localhost:8080", "description": "Local dev"}],
)

app.include_router(router)


_SANDBOX_PATH = Path(__file__).parent / "static" / "sandbox.html"

@app.get(
    "/sandbox",
    response_class=HTMLResponse,
    include_in_schema=False,
    summary="Интерактивный sandbox для /generate",
)
async def sandbox() -> HTMLResponse:
    if not _SANDBOX_PATH.exists():
        return HTMLResponse("<h1>sandbox.html not found</h1>", status_code=404)
    return HTMLResponse(_SANDBOX_PATH.read_text(encoding="utf-8"))
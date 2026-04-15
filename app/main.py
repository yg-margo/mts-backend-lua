"""
LocalScript API — entry point
FastAPI app, mounts all routers.

Swagger UI  →  http://localhost:8080/docs
ReDoc       →  http://localhost:8080/redoc
OpenAPI JSON→  http://localhost:8080/openapi.json
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

from app.api.routes import router  # noqa: E402
from app.services.llm_client import chat  # noqa: E402
from app.services.rag import search_snippets  # noqa: E402

log = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("=== WARMUP START ===")
    t0 = time.perf_counter()
    try:
        out = await chat(
            [{"role": "user", "content": "ping"}],
            max_tokens=1,
            temperature=0.0,
        )
        log.info("LLM warmup OK (%.2fs, out=%r)", time.perf_counter() - t0, out[:30])
    except Exception as exc:
        log.warning("LLM warmup FAILED (%.2fs): %s", time.perf_counter() - t0, exc)

    t1 = time.perf_counter()
    try:
        await search_snippets("warmup", top_k=1)
        log.info("RAG warmup OK (%.2fs)", time.perf_counter() - t1)
    except Exception as exc:
        log.warning("RAG warmup FAILED (%.2fs): %s", time.perf_counter() - t1, exc)

    log.info("=== WARMUP DONE in %.2fs ===", time.perf_counter() - t0)
    yield


app = FastAPI(
    title="LocalScript API",
    lifespan=lifespan,
    description=(
        "**LLM-powered Lua code generator** для платформы MWS Octapi / LowCode.\n\n"
        "Pipeline: `Clarifier → Planner → RAG Searcher → Coder → Validator → Fixer`\n\n"
        "Swagger UI: [/docs](/docs) · ReDoc: [/redoc](/redoc)"
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

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):(5173|5174|5175|3000|4173)",
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(router)

from pathlib import Path
from fastapi.staticfiles import StaticFiles

_static_dir = Path(__file__).parent / "static"
if _static_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")

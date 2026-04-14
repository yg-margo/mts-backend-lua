"""
llm_client.py — тонкая обёртка над OpenAI-совместимым API (Ollama и т.п.).
"""

from __future__ import annotations
import json
import logging
import time
from typing import Awaitable, Callable
from openai import AsyncOpenAI
from app.core.config import settings

log = logging.getLogger("app.llm")

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
        )
    return _client


_OLLAMA_EXTRA_BODY = {"keep_alive": "30m"}


async def chat(
    messages: list[dict],
    max_tokens: int,
    temperature: float = 0.2,
    expect_json: bool = False,
) -> str:
    kwargs: dict = dict(
        model=settings.llm_model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        extra_body=_OLLAMA_EXTRA_BODY,
    )
    if expect_json:
        kwargs["response_format"] = {"type": "json_object"}

    tag = "chat.json" if expect_json else "chat"
    log.info("[%s] -> model=%s max_tokens=%d", tag, settings.llm_model, max_tokens)
    t0 = time.perf_counter()
    resp = await get_client().chat.completions.create(**kwargs)
    dt = time.perf_counter() - t0
    content = resp.choices[0].message.content.strip()
    usage = getattr(resp, "usage", None)
    log.info(
        "[%s] <- %.2fs (out_chars=%d, usage=%s)",
        tag, dt, len(content), usage,
    )
    return content


async def chat_json(messages: list[dict], max_tokens: int) -> dict:
    raw = await chat(messages, max_tokens=max_tokens, expect_json=True)
    return json.loads(raw)


OnToken = Callable[[str], Awaitable[None]]


async def chat_stream(
    messages: list[dict],
    max_tokens: int,
    temperature: float = 0.2,
    on_token: OnToken | None = None,
) -> str:
    """Streamed chat. Calls on_token(delta) per chunk; returns full accumulated string.

    Used for stages where the user benefits from seeing tokens live (coder, fixer).
    JSON-mode stages (clarifier, planner) keep the non-streaming path.
    """
    log.info("[chat.stream] -> model=%s max_tokens=%d", settings.llm_model, max_tokens)
    t0 = time.perf_counter()
    stream = await get_client().chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        stream=True,
        extra_body=_OLLAMA_EXTRA_BODY,
    )
    t_first = None
    buf: list[str] = []
    n_chunks = 0
    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content or ""
        if not delta:
            continue
        if t_first is None:
            t_first = time.perf_counter()
            log.info("[chat.stream] TTFT=%.2fs", t_first - t0)
        buf.append(delta)
        n_chunks += 1
        if on_token is not None:
            await on_token(delta)
    dt = time.perf_counter() - t0
    log.info("[chat.stream] <- %.2fs (chunks=%d, out_chars=%d)", dt, n_chunks, sum(len(x) for x in buf))
    return "".join(buf).strip()
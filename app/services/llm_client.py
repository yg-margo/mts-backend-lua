"""
llm_client.py — тонкая обёртка над OpenAI-совместимым API (Ollama и т.п.).
"""

from __future__ import annotations
import json
from openai import AsyncOpenAI
from app.core.config import settings


_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
        )
    return _client


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
    )
    if expect_json:
        kwargs["response_format"] = {"type": "json_object"}

    resp = await get_client().chat.completions.create(**kwargs)
    return resp.choices[0].message.content.strip()


async def chat_json(messages: list[dict], max_tokens: int) -> dict:
    raw = await chat(messages, max_tokens=max_tokens, expect_json=True)
    return json.loads(raw)
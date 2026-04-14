"""
rag.py — поиск релевантных сниппетов Lua-кода по ключевым словам.
"""

from __future__ import annotations
import re
from pathlib import Path
from app.core.config import settings


_BLOCKS: list[str] | None = None


def _load_blocks() -> list[str]:
    global _BLOCKS
    if _BLOCKS is not None:
        return _BLOCKS

    path = Path(settings.docs_path)
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8")
    raw_blocks = re.split(r"\n{2,}", text)
    _BLOCKS = [b.strip() for b in raw_blocks if b.strip()]
    return _BLOCKS


def _score(block: str, keywords: list[str]) -> float:
    low = block.lower()
    return sum(1.0 for kw in keywords if kw.lower() in low)


def search_snippets(keywords: list[str], top_k: int = 2) -> str:
    blocks = _load_blocks()
    if not blocks:
        return ""

    scored = sorted(
        blocks,
        key=lambda b: _score(b, keywords),
        reverse=True,
    )
    best = [b for b in scored[:top_k] if _score(b, keywords) > 0]
    if not best:
        return ""

    return "\n\n---\n\n".join(best)


def invalidate_cache() -> None:
    global _BLOCKS
    _BLOCKS = None

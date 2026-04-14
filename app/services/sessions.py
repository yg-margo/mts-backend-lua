"""
sessions.py — In-memory store уточняющих сессий.

Фронт получает session_id + вопросы, потом шлёт ответы с тем же session_id —
сервер склеивает их с исходным промптом и пропускает пайплайн дальше.
Store одноразовый: после pop() запись удаляется.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass

from app.core.config import settings


@dataclass
class Session:
    prompt: str
    questions: list[str]
    created_at: float


_SESSIONS: dict[str, Session] = {}
_LOCK = threading.Lock()


def _gc_expired_locked(now: float) -> None:
    ttl = settings.clarification_session_ttl
    expired = [sid for sid, s in _SESSIONS.items() if now - s.created_at > ttl]
    for sid in expired:
        _SESSIONS.pop(sid, None)


def create(prompt: str, questions: list[str]) -> str:
    now = time.time()
    sid = uuid.uuid4().hex
    with _LOCK:
        _gc_expired_locked(now)
        _SESSIONS[sid] = Session(prompt=prompt, questions=questions, created_at=now)
    return sid


def peek(session_id: str) -> Session | None:
    now = time.time()
    with _LOCK:
        _gc_expired_locked(now)
        return _SESSIONS.get(session_id)


def pop(session_id: str) -> Session | None:
    now = time.time()
    with _LOCK:
        _gc_expired_locked(now)
        return _SESSIONS.pop(session_id, None)

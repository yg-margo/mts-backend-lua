"""
chat_sessions.py — In-memory store для «памяти» чата внутри одной сессии.

Хранит только ПОСЛЕДНИЙ успешно сгенерированный Lua-артефакт на session_id,
не всю историю диалога. На правки (`is_edit_intent`) pipeline подаёт этот код
в coder вместо полного планирования — один LLM-вызов, ≤256 output токенов,
полностью укладывается в VRAM- и токен-бюджет.

Отдельно от sessions.py, т.к. тот работает в режиме pop() (одноразовые
clarification-токены) и смешивать два разных жизненных цикла в одном сторе
опасно.
"""

from __future__ import annotations

import re
import threading
import time
import uuid
from dataclasses import dataclass

from app.core.config import settings


@dataclass
class ChatSession:
    last_code: str
    last_prompt: str
    updated_at: float


_CHAT: dict[str, ChatSession] = {}
_LOCK = threading.Lock()


def _gc_expired_locked(now: float) -> None:
    ttl = settings.chat_session_ttl
    expired = [sid for sid, s in _CHAT.items() if now - s.updated_at > ttl]
    for sid in expired:
        _CHAT.pop(sid, None)


def create() -> str:
    """Создаёт пустую чат-сессию и возвращает её id."""
    now = time.time()
    sid = uuid.uuid4().hex
    with _LOCK:
        _gc_expired_locked(now)
        _CHAT[sid] = ChatSession(last_code="", last_prompt="", updated_at=now)
    return sid


def get_last_code(session_id: str | None) -> str | None:
    """Возвращает last_code, если сессия жива и в ней что-то есть."""
    if not session_id:
        return None
    now = time.time()
    with _LOCK:
        _gc_expired_locked(now)
        entry = _CHAT.get(session_id)
        if entry is None:
            return None
        return entry.last_code or None


def ensure(session_id: str | None) -> str:
    """Возвращает существующий id или создаёт новый. Регистрирует запись, если её нет."""
    if session_id:
        now = time.time()
        with _LOCK:
            _gc_expired_locked(now)
            if session_id in _CHAT:
                return session_id
            _CHAT[session_id] = ChatSession(
                last_code="", last_prompt="", updated_at=now
            )
            return session_id
    return create()


def update_last_code(session_id: str, code: str, prompt: str) -> None:
    """Сохраняет финальный код как новую точку опоры для будущих правок."""
    now = time.time()
    with _LOCK:
        _gc_expired_locked(now)
        _CHAT[session_id] = ChatSession(
            last_code=code or "",
            last_prompt=prompt or "",
            updated_at=now,
        )


# Глаголы-маркеры правки (RU + EN). Regex — чтобы без отдельного LLM-вызова.
# Регистр-независимо, \b работает по Unicode для str в Py3.
_EDIT_RE = re.compile(
    r"(?iu)\b("
    r"переименуй|переимен\w*|"
    r"измени|изменить|измени\w*|поменяй|поменять|"
    r"замен[ияь]\w*|вместо|также|"
    r"добав[ьи]\w*|убери|убрать|удали|удалить|"
    r"исправ[ьи]\w*|почини|починить|"
    r"rename|change|modify|edit|replace|add|remove|delete|fix|instead|also"
    r")\b"
)


def is_edit_intent(prompt: str) -> bool:
    """True, если в промпте есть явные глаголы-маркеры правки существующего кода."""
    return bool(_EDIT_RE.search(prompt or ""))


def truncate_code_for_context(code: str, max_chars: int = 6000) -> str:
    """Страховка для аномально длинного предыдущего кода.

    Coder сам выдаёт ≤256 токенов (~800-1200 символов Lua), поэтому в норме
    срабатывать не должно. Но если по какой-то причине last_code разрастётся,
    режем середину, сохраняя начало и конец — там обычно объявления и `return`.
    """
    if not code or len(code) <= max_chars:
        return code or ""
    head_n = max_chars // 2
    tail_n = max_chars - head_n - 32
    head = code[:head_n]
    tail = code[-tail_n:] if tail_n > 0 else ""
    return f"{head}\n-- ...truncated...\n{tail}"

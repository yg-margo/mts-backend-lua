"""
schema.py — Pydantic-модель одного Lua-паттерна из YAML.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LuaPattern(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    category: str
    task_description: str
    code: str

    lua_version: str = "any"
    dependencies: list[str] = Field(default_factory=list)
    complexity: str | None = None
    source: str | None = None
    signature: str | None = None

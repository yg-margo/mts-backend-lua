"""
models.py — Pydantic-схемы запросов и ответов.
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class GenerateRequest(BaseModel):
    prompt: str


class GenerateResponse(BaseModel):
    code: str


class Plan(BaseModel):
    steps: list[str]


class ErrorDetail(BaseModel):
    line: Optional[int] = None
    message: str
    code_block: str


class ValidationResult(BaseModel):
    success: bool
    errors: list[ErrorDetail]
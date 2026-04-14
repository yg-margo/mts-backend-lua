"""
models.py — Pydantic-схемы запросов и ответов.
"""

from __future__ import annotations
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, model_validator


class ClarificationPayload(BaseModel):
    session_id: str
    questions: list[str]


class GenerateRequest(BaseModel):
    prompt: Optional[str] = None
    session_id: Optional[str] = None
    answers: Optional[list[str]] = None
    chat_session_id: Optional[str] = None

    @model_validator(mode="after")
    def _exactly_one_branch(self) -> "GenerateRequest":
        has_prompt = bool(self.prompt and self.prompt.strip())
        has_followup = self.session_id is not None and self.answers is not None
        if has_prompt == has_followup:
            raise ValueError(
                "Provide either 'prompt' (new request) or "
                "'session_id' + 'answers' (clarification follow-up), not both."
            )
        return self


class EntryPoint(BaseModel):
    name: str
    params: list[str]


class GenerateResponse(BaseModel):
    code: Optional[str] = None
    inputs: Optional[dict[str, Any]] = None
    entry_point: Optional[EntryPoint] = None
    clarification: Optional[ClarificationPayload] = None
    chat_session_id: Optional[str] = None


class Plan(BaseModel):
    steps: list[str]


class ClarifierResult(BaseModel):
    questions: list[str]


class ErrorDetail(BaseModel):
    line: Optional[int] = None
    message: str
    code_block: str


class ValidationResult(BaseModel):
    success: bool
    errors: list[ErrorDetail]


class ContextBlock(BaseModel):
    kind: Literal["prompt", "example", "hint"]
    content: str


class GenerateFromContextRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    blocks: list[ContextBlock] = Field(default_factory=list)


class GenerateFromContextResponse(BaseModel):
    code: str
    used_tokens: int
    kept_chunks: int
    total_chunks: int
    inputs: dict[str, Any] = Field(default_factory=dict)
    entry_point: Optional[EntryPoint] = None

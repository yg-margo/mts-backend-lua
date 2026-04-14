"""
validator.py — запускает luac (синтаксис) через subprocess.
Selene и Busted опциональны — подключаются если установлены.
"""

from __future__ import annotations
import re
import subprocess
import tempfile
from pathlib import Path

from app.models.models import ErrorDetail, ValidationResult



def _run(cmd: list[str], input_text: str | None = None) -> tuple[int, str]:
    result = subprocess.run(
        cmd,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=15,
    )
    combined = (result.stdout + "\n" + result.stderr).strip()
    return result.returncode, combined


def _parse_line_number(error_text: str) -> int | None:
    m = re.search(r":(\d+):", error_text)
    if m:
        return int(m.group(1))
    m = re.search(r"line (\d+)", error_text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _line_to_block(code: str, line_no: int, context: int = 5) -> str:
    lines = code.splitlines()
    start = max(0, line_no - context - 1)
    end = min(len(lines), line_no + context)
    return "\n".join(lines[start:end])


def _check_luac(code: str) -> list[ErrorDetail]:
    with tempfile.NamedTemporaryFile(
        suffix=".lua", mode="w", encoding="utf-8", delete=False
    ) as f:
        f.write(code)
        tmp_path = f.name

    try:
        rc, output = _run(["luac", "-p", tmp_path])
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if rc == 0:
        return []

    line_no = _parse_line_number(output)
    block = _line_to_block(code, line_no) if line_no else code
    return [ErrorDetail(line=line_no, message=output, code_block=block)]


def _check_selene(code: str) -> list[ErrorDetail]:
    try:
        rc, output = _run(["selene", "--display-style", "json", "-"], input_text=code)
    except FileNotFoundError:
        return []

    if rc == 0:
        return []

    errors: list[ErrorDetail] = []
    for raw_line in output.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        line_no = _parse_line_number(raw_line)
        block = _line_to_block(code, line_no) if line_no else code
        errors.append(ErrorDetail(line=line_no, message=raw_line, code_block=block))
    return errors


def validate(code: str) -> ValidationResult:
    errors: list[ErrorDetail] = []
    errors.extend(_check_luac(code))
    if not errors:
        errors.extend(_check_selene(code))

    return ValidationResult(success=len(errors) == 0, errors=errors)

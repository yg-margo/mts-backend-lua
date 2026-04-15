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


_FORBIDDEN_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\bwf\s*\."),
        "Use 'input.<field>' instead of 'wf.*' — 'wf' is not available in this runtime.",
    ),
    (
        re.compile(r"\bloadstring\s*\("),
        "'loadstring' is forbidden; runtime inputs are already parsed Lua tables — access fields directly.",
    ),
    (
        re.compile(r"\bload\s*\("),
        "'load' is forbidden; runtime inputs are already parsed Lua tables — access fields directly.",
    ),
    (
        re.compile(r"\bjson\s*\.\s*decode\b|\bcjson\s*\."),
        "JSON parsers are forbidden; runtime inputs are already parsed Lua tables.",
    ),
    (
        re.compile(r"\brequire\s*\("),
        "'require' is forbidden in the sandbox.",
    ),
    (
        re.compile(r"\b_utils\s*\."),
        "'_utils' is not available in this runtime; use plain Lua tables ({}) instead.",
    ),
]


def _mask_strings_and_comments(code: str) -> str:
    """Replace string/comment content with spaces so forbidden-identifier
    regexes don't fire inside literals or comments, while preserving line
    numbers and column positions."""

    def _space(match: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    patterns = [
        r"--\[\[.*?\]\]",           # block comment (non-greedy, may span lines)
        r"--[^\n]*",                # line comment
        r"\[\[.*?\]\]",             # long-bracket string
        r'"(?:\\.|[^"\\\n])*"',   # double-quoted string
        r"'(?:\\.|[^'\\\n])*'",   # single-quoted string
    ]
    masked = code
    for pat in patterns:
        masked = re.sub(pat, _space, masked, flags=re.DOTALL)
    return masked


def _check_forbidden_identifiers(code: str) -> list[ErrorDetail]:
    """Detect forbidden identifiers (wf.*, loadstring, load, json.decode,
    cjson.*, require, _utils.*) and return a single aggregated ErrorDetail so
    the fixer sees every issue at once — MAX_FIX_CYCLES=1 only addresses the
    first error."""
    masked = _mask_strings_and_comments(code)
    hits: list[tuple[int, str]] = []
    seen_messages: set[str] = set()
    for regex, message in _FORBIDDEN_PATTERNS:
        for m in regex.finditer(masked):
            line_no = masked.count("\n", 0, m.start()) + 1
            hits.append((line_no, message))
    if not hits:
        return []
    hits.sort(key=lambda h: h[0])
    first_line = hits[0][0]
    # Dedupe messages while preserving order.
    ordered: list[str] = []
    for _, msg in hits:
        if msg not in seen_messages:
            seen_messages.add(msg)
            ordered.append(msg)
    combined = "Forbidden identifiers in generated Lua:\n- " + "\n- ".join(ordered)
    return [
        ErrorDetail(
            line=first_line,
            message=combined,
            code_block=code,
        )
    ]


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
    errors.extend(_check_forbidden_identifiers(code))
    if not errors:
        errors.extend(_check_luac(code))
    if not errors:
        errors.extend(_check_selene(code))

    return ValidationResult(success=len(errors) == 0, errors=errors)

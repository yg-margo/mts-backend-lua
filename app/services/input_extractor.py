"""
input_extractor.py — build a JSON skeleton of the `input.*` contract a generated
Lua node reads from.

The Lua node's output of the pipeline is a script that references globals
`input.<field>` (sandbox) or `wf.vars.<field>` (Octapi). We only care about
`input.*` here: the frontend InputNode feeds a JSON object into the Lua runtime
as the `input` global, so the user needs to know which fields to populate. We
scan the generated source and return a nested dict such as
`{"name": None, "items": [], "user": {"email": None}}`.

Inference is intentionally shallow — the scanner sees syntactic access paths
plus a few context clues (ipairs/pairs/#, string concat, subfields). It is NOT
a type checker. When we can't guess, we leave the leaf as `None` so the user
gets an explicit placeholder rather than silent `nil` at runtime.

Regex-based by default. tree-sitter would offer richer context (arithmetic
operator detection, etc.) but the regex is enough for the `input.*` shapes the
model produces from the current prompt + corpus.
"""

from __future__ import annotations

from typing import Any

# One access step: .field | ["key"] | ['key'] | [N]
_STEP = r"""
    \.\s*(?P<field>\w+)
  | \[\s*(?P<str1>"(?:[^"\\]|\\.)*")\s*\]
  | \[\s*(?P<str2>'(?:[^'\\]|\\.)*')\s*\]
  | \[\s*(?P<num>\d+)\s*\]
"""

# A full access expression: `input` followed by one-or-more access steps.
_INPUT_ACCESS = r"""
    \binput\b
    (?P<tail>
        (?:
            \s*\.\s*\w+
          | \s*\[\s*(?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|\d+)\s*\]
        )+
    )
"""

import re

_step_re = re.compile(_STEP, re.VERBOSE)
_access_re = re.compile(_INPUT_ACCESS, re.VERBOSE)


def _parse_path(tail: str) -> list[str | int]:
    path: list[str | int] = []
    for m in _step_re.finditer(tail):
        if m.group("field") is not None:
            path.append(m.group("field"))
        elif m.group("str1") is not None:
            path.append(_unquote(m.group("str1")))
        elif m.group("str2") is not None:
            path.append(_unquote(m.group("str2")))
        elif m.group("num") is not None:
            path.append(int(m.group("num")))
    return path


def _unquote(s: str) -> str:
    # Strip wrapping quotes and unescape \" / \' / \\ — no other escapes matter
    # for JSON keys we'll put back out.
    body = s[1:-1]
    return body.replace("\\\\", "\\").replace("\\\"", "\"").replace("\\'", "'")


def extract_inputs(
    code: str, params: list[str] | None = None
) -> dict[str, Any]:
    """
    Scan `code` for every `input.<...>` access and return a nested skeleton
    dict. Keys are inserted in first-seen order so the frontend shows fields in
    the order they appear in the script.

    If `params` is given (function signature param names), each param missing
    from the skeleton is added as a top-level `None`. Params that are already
    present with an inferred shape (dict/list) are left alone — object wins.
    """
    if not code:
        root: dict[str, Any] = {}
        for p in params or []:
            root[p] = None
        return root

    # Strip comments so an `input.x` inside `-- ...` or `--[[ ... ]]` doesn't
    # pollute the skeleton.
    stripped = _strip_lua_comments(code)

    # (path, was_indexed_numerically, has_subfield) gathered in order of
    # appearance.
    seen: list[tuple[list[str | int], bool]] = []
    for m in _access_re.finditer(stripped):
        path = _parse_path(m.group("tail"))
        if not path:
            continue
        seen.append((path, _looks_array_context(stripped, m.start(), m.end(), path)))

    # Merge.
    root = {}
    for path, forced_array in seen:
        _insert(root, path, forced_array=forced_array)

    # Union with function-signature params: keep any pre-existing inferred
    # shape, but add missing ones as `None` placeholders.
    for p in params or []:
        if p and p not in root:
            root[p] = None

    return root


# Top-level `function NAME(args)` — no `local` prefix (line starts at the
# `function` keyword), and NAME is a bare identifier (rejects `M.foo` / `obj:bar`
# since those require a `.`/`:` between name and `(`).
_FUNCTION_DEF_RE = re.compile(
    r"^\s*function\s+([A-Za-z_]\w*)\s*\(([^)]*)\)",
    re.MULTILINE,
)


def extract_entry_point(code: str) -> dict[str, Any] | None:
    """
    Find the first top-level global `function NAME(args)` definition and return
    ``{"name": NAME, "params": [...]}``. Returns ``None`` when the code defines
    only `local function`, only methods (`function M.foo`, `function obj:bar`),
    has `self` as a param (method style), or has no functions at all.

    Varargs (`...`) are filtered out of params — they're impossible to auto-feed
    from the Input JSON, but the function is still a valid auto-invoke target
    for the remaining named params.
    """
    if not code:
        return None

    stripped = _strip_lua_comments(code)
    m = _FUNCTION_DEF_RE.search(stripped)
    if not m:
        return None

    name = m.group(1)
    raw_params = m.group(2).strip()

    params: list[str] = []
    if raw_params:
        for p in raw_params.split(","):
            p = p.strip()
            if not p:
                continue
            # `self` means this is a method definition written as `function NAME(self, ...)`
            # — a bare global `NAME(obj, ...)` call doesn't make sense in the
            # sandbox's input-driven model.
            if p == "self":
                return None
            if p == "...":
                continue
            params.append(p)

    return {"name": name, "params": params}


def _looks_array_context(
    src: str, start: int, end: int, path: list[str | int]
) -> bool:
    """
    Very cheap context check: treat the accessed slot as an array when:
      - its full access chain is wrapped in `ipairs(...)` or `#...` or
      - its last indexing step was numeric ([N]) — handled by _insert via path.

    Returns True only for the ipairs / `#` cases; numeric-index handling lives
    in _insert (path-level info).
    """
    # Look ~16 chars before `start` for a bareword + "(" or a "#".
    left = src[max(0, start - 16) : start]
    # ipairs(input.x ...) / #input.x
    if re.search(r"\bipairs\s*\(\s*$", left):
        return True
    if re.search(r"#\s*$", left):
        return True
    # input.x[N] → last path step numeric → array at path[:-1]
    if path and isinstance(path[-1], int):
        return True
    return False


def _insert(root: dict[str, Any], path: list[str | int], *, forced_array: bool) -> None:
    """
    Walk/extend `root` along `path`, promoting nodes to object/array as needed.

    Rules:
      - A string step means the parent is an object (dict). A numeric step means
        the parent is an array — we represent arrays as `[]` sentinels in the
        skeleton (no indices populated, the frontend just needs to know it's an
        array).
      - When two paths disagree (scalar vs object), object wins — it's strictly
        more informative.
    """
    cur: Any = root
    for i, step in enumerate(path):
        is_last = i == len(path) - 1

        if isinstance(step, int):
            # Parent was promised to be an array in a previous pass, or we need
            # to mark it so now. Because we thread containers via the parent's
            # slot (not the array itself), we only reach this branch when the
            # caller set that slot to [] — we just stop descending (we don't
            # model per-index schemas).
            return

        # cur must be a dict for a string step.
        if not isinstance(cur, dict):
            # cur was inferred as [] or a scalar; can't nest further without
            # conflicting info — skip this path silently.
            return

        existing = cur.get(step, _MISSING)

        if is_last:
            if forced_array:
                # Force this slot to [] unless it's already an object (object
                # wins if we've also seen subfields on it).
                if not isinstance(existing, dict):
                    cur[step] = []
            else:
                if existing is _MISSING:
                    cur[step] = None
                # Otherwise: leave alone. An already-assigned dict/list/None
                # stays put — object always wins, array stays, None is fine.
            return

        # Not last — we need to descend. Next step decides container kind.
        next_step = path[i + 1]
        needs_object = isinstance(next_step, str)

        if needs_object:
            if not isinstance(existing, dict):
                # Promote None/list/missing → dict.
                cur[step] = {}
            cur = cur[step]
        else:
            # next_step is int → current slot should be an array.
            if not isinstance(existing, list) and not isinstance(existing, dict):
                cur[step] = []
            # If it's already a dict we keep it (object wins). In either case,
            # there's no further useful descent — arrays have no sub-schema and
            # dicts won't accept a numeric step anyway.
            return


_MISSING = object()


def _strip_lua_comments(code: str) -> str:
    """
    Remove Lua `--` line comments and `--[[ ... ]]` block comments (including
    the long-bracket variants with arbitrary `=` padding). Cheap best-effort —
    we do not try to respect string literals because an `input.x` inside a
    string is unlikely to matter for the skeleton.
    """
    # Block comments: --[[ ... ]] or --[=[ ... ]=] etc.
    code = re.sub(
        r"--\[(?P<eq>=*)\[.*?\](?P=eq)\]",
        "",
        code,
        flags=re.DOTALL,
    )
    # Line comments: -- ... to end of line.
    code = re.sub(r"--[^\n]*", "", code)
    return code

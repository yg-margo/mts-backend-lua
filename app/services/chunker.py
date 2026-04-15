"""
chunker.py — tree-sitter Lua AST chunker + tiktoken budget packer.

Goal: split user-supplied Lua context into semantically coherent chunks so we
can pack only the most relevant pieces into the 4096-token input window,
leaving room for the mandatory ≤256 output tokens.

Used by the /generate-from-context endpoint. Falls back to a regex splitter
(\\n{2,}) when tree-sitter fails, so a malformed Example node never blocks
generation — it just gets less-structured chunks.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from rank_bm25 import BM25Okapi

log = logging.getLogger(__name__)


_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "if", "then", "else",
    "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "doing",
    "have", "has", "had", "having",
    "of", "in", "on", "at", "to", "for", "with", "by", "from", "as",
    "that", "this", "these", "those", "it", "its", "there", "here",
    "i", "you", "he", "she", "we", "they", "me", "us", "them",
    "please", "want", "need", "should", "would", "could", "can", "may",
    "write", "make", "create", "build", "implement", "add", "use",
    "function", "code", "script", "program", "lua",
})

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [
        t for t in _TOKEN_RE.findall(text.lower())
        if len(t) > 1 and t not in _STOPWORDS
    ]


@dataclass(frozen=True)
class LuaChunk:
    text: str
    kind: str  # "ast" | "fallback"


# ---------------------------------------------------------------------------
# tree-sitter + tiktoken lazy loaders (keep import-time cheap; tiktoken pulls
# a blob on first use, parser loads the prebuilt grammar once).
# ---------------------------------------------------------------------------

_parser = None  # type: ignore[var-annotated]
_parser_load_failed = False


def _get_parser():
    global _parser, _parser_load_failed
    if _parser is not None or _parser_load_failed:
        return _parser
    try:
        import tree_sitter_lua  # type: ignore
        from tree_sitter import Language, Parser  # type: ignore

        _parser = Parser(Language(tree_sitter_lua.language()))
    except Exception as e:  # grammar install issues, ABI mismatch, etc.
        log.warning("tree-sitter Lua parser unavailable: %s", e)
        _parser_load_failed = True
        _parser = None
    return _parser


_encoding = None  # type: ignore[var-annotated]


def _count_tokens(text: str) -> int:
    global _encoding
    if _encoding is None:
        try:
            import tiktoken  # type: ignore
            _encoding = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            log.warning("tiktoken unavailable, using char/4 estimate: %s", e)
            _encoding = False  # sentinel: fall back to heuristic
    if _encoding is False:
        # Rough: 1 token ≈ 4 chars for ASCII source code.
        return max(1, len(text) // 4)
    return len(_encoding.encode(text))


# ---------------------------------------------------------------------------
# AST walking
# ---------------------------------------------------------------------------


def _node_text(source: bytes, node) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _walk_top_level(root, source: bytes) -> list[LuaChunk]:
    """
    Walk the root's direct children. Group adjacent `comment` nodes with the
    next non-comment statement so that documentation travels with its code.
    """
    chunks: list[LuaChunk] = []
    pending_comments: list[bytes] = []

    for child in root.children:
        t = child.type
        if t == "comment":
            pending_comments.append(source[child.start_byte:child.end_byte])
            continue

        # Tree-sitter grammars may expose "extra" tokens (e.g. "\n") as direct
        # children; skip anything that's whitespace-only.
        raw = source[child.start_byte:child.end_byte]
        if not raw.strip():
            continue

        # Attach leading comments to this statement.
        piece = b"\n".join(pending_comments + [raw]).decode("utf-8", errors="replace")
        pending_comments = []
        piece = piece.strip()
        if piece:
            chunks.append(LuaChunk(text=piece, kind="ast"))

    # Dangling comments with no following statement — keep them as their own
    # chunk; the model occasionally benefits from the hint even without code.
    if pending_comments:
        leftover = b"\n".join(pending_comments).decode("utf-8", errors="replace").strip()
        if leftover:
            chunks.append(LuaChunk(text=leftover, kind="ast"))

    return chunks


def _fallback_split(code: str) -> list[LuaChunk]:
    raw = re.split(r"\n{2,}", code)
    return [LuaChunk(text=b.strip(), kind="fallback") for b in raw if b.strip()]


def chunk_lua(code: str) -> list[LuaChunk]:
    """
    Split Lua code into semantically coherent chunks.

    Strategy:
      1. Try tree-sitter top-level walk (with comments attached to their
         statement).
      2. If the parser is unavailable, or the root contains an ERROR node at
         the top level, fall back to a blank-line regex splitter.

    An empty input yields [].
    """
    text = (code or "").strip()
    if not text:
        return []

    parser = _get_parser()
    if parser is None:
        return _fallback_split(text)

    try:
        source = text.encode("utf-8")
        tree = parser.parse(source)
        root = tree.root_node
        # Accept partial parses: only reject when the root itself is flagged
        # as ERROR. Individual ERROR subtrees are tolerated and we still emit
        # their raw bytes.
        if root.type == "ERROR" or root.has_error and all(
            c.type == "ERROR" for c in root.children
        ):
            log.info("tree-sitter parse errored out; using regex fallback")
            return _fallback_split(text)

        chunks = _walk_top_level(root, source)
        if not chunks:
            return _fallback_split(text)
        return chunks
    except Exception as e:
        log.warning("tree-sitter parse raised (%s); using regex fallback", e)
        return _fallback_split(text)


# ---------------------------------------------------------------------------
# Scoring + packing
# ---------------------------------------------------------------------------


@dataclass
class PackResult:
    snippet: str
    used_tokens: int
    kept: int
    total: int


def pack_chunks(
    chunks: list[LuaChunk],
    query: str,
    budget_tokens: int,
    separator: str = "\n\n---\n\n",
) -> PackResult:
    """
    Greedy-pack the highest-scoring chunks into a single snippet whose total
    token count stays ≤ budget_tokens. Scoring is BM25 over the tokenized
    query; ties (including score==0) break by original document order so the
    caller sees a stable, readable snippet even when nothing matches.
    """
    if not chunks or budget_tokens <= 0:
        return PackResult(snippet="", used_tokens=0, kept=0, total=len(chunks))

    q_tokens = tokenize(query)
    if q_tokens:
        tokenized = [tokenize(c.text) or ["<empty>"] for c in chunks]
        bm25 = BM25Okapi(tokenized)
        scores = bm25.get_scores(q_tokens)
    else:
        scores = [0.0] * len(chunks)

    indexed = list(enumerate(chunks))
    indexed.sort(key=lambda pair: (-scores[pair[0]], pair[0]))

    sep_tokens = _count_tokens(separator)
    kept: list[tuple[int, LuaChunk]] = []
    used = 0

    for idx, chunk in indexed:
        chunk_tokens = _count_tokens(chunk.text)
        additional = chunk_tokens if not kept else chunk_tokens + sep_tokens
        if used + additional > budget_tokens:
            # Single chunk bigger than the whole budget — skip it and try the
            # next (smaller, possibly less relevant) chunk rather than blowing
            # the budget.
            continue
        kept.append((idx, chunk))
        used += additional

    # Restore document order for readability.
    kept.sort(key=lambda pair: pair[0])
    snippet = separator.join(c.text for _, c in kept)
    return PackResult(
        snippet=snippet,
        used_tokens=used,
        kept=len(kept),
        total=len(chunks),
    )


def count_tokens(text: str) -> int:
    """Public alias for tests + pipeline bookkeeping."""
    return _count_tokens(text)

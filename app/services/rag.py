"""
rag.py — hybrid BM25 + dense retrieval with Reciprocal Rank Fusion.

Indexes blocks from docs/lua_examples.txt (split on blank-line runs) with:
  - BM25Okapi (rank-bm25): lexical, IDF-weighted term overlap
  - Dense cosine via Ollama embeddings (nomic-embed-text by default)
  - RRF fusion: score = Σ 1 / (rrf_k + rank_i) across both rankings

Dense index builds lazily on first query. If embeddings are unavailable
(Ollama model missing, timeout, etc.) we log a warning and serve BM25-only.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

import numpy as np
from openai import AsyncOpenAI
from rank_bm25 import BM25Okapi

from app.core.config import settings

log = logging.getLogger(__name__)


STOPWORDS = frozenset({
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
        if len(t) > 1 and t not in STOPWORDS
    ]


_BLOCKS: list[str] | None = None
_BM25: BM25Okapi | None = None
_DENSE: np.ndarray | None = None
_EMBED_CLIENT: AsyncOpenAI | None = None
_INIT_LOCK = asyncio.Lock()


def _get_embed_client() -> AsyncOpenAI:
    global _EMBED_CLIENT
    if _EMBED_CLIENT is None:
        _EMBED_CLIENT = AsyncOpenAI(
            base_url=settings.embed_base_url,
            api_key=settings.embed_api_key,
        )
    return _EMBED_CLIENT


def _load_blocks() -> list[str]:
    path = Path(settings.docs_path)
    if not path.exists():
        log.warning("docs_path %s does not exist", path)
        return []
    raw = re.split(r"\n{2,}", path.read_text(encoding="utf-8"))
    return [b.strip() for b in raw if b.strip()]


def _build_bm25(blocks: list[str]) -> BM25Okapi:
    tokenized = [tokenize(b) or ["<empty>"] for b in blocks]
    return BM25Okapi(tokenized)


async def _embed(texts: list[str]) -> np.ndarray:
    resp = await _get_embed_client().embeddings.create(
        model=settings.embed_model,
        input=texts,
    )
    vecs = np.array([d.embedding for d in resp.data], dtype=np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vecs / norms


async def _ensure_indices() -> list[str]:
    global _BLOCKS, _BM25, _DENSE

    if _BLOCKS is not None and _BM25 is not None:
        return _BLOCKS

    async with _INIT_LOCK:
        if _BLOCKS is not None and _BM25 is not None:
            return _BLOCKS

        blocks = _load_blocks()
        if not blocks:
            _BLOCKS = []
            _BM25 = BM25Okapi([["<empty>"]])
            return _BLOCKS

        bm25 = _build_bm25(blocks)

        try:
            dense = await _embed(blocks)
            _DENSE = dense
            log.info(
                "RAG index built: %d blocks, BM25 + dense(dim=%d)",
                len(blocks), dense.shape[1],
            )
        except Exception as e:
            _DENSE = None
            log.warning(
                "RAG dense index unavailable (%s); falling back to BM25-only", e,
            )

        _BLOCKS = blocks
        _BM25 = bm25
        return _BLOCKS


def _rrf_fuse(rankings: list[list[int]], rrf_k: int, n_docs: int) -> list[tuple[int, float]]:
    scores = [0.0] * n_docs
    for ranked in rankings:
        for rank, doc_idx in enumerate(ranked):
            scores[doc_idx] += 1.0 / (rrf_k + rank + 1)
    fused = [(i, s) for i, s in enumerate(scores) if s > 0]
    fused.sort(key=lambda x: -x[1])
    return fused


async def search_snippets(query: str, top_k: int | None = None) -> str:
    blocks = await _ensure_indices()
    if not blocks:
        return ""

    if top_k is None:
        top_k = settings.rag_top_k

    q_tokens = tokenize(query)

    if q_tokens:
        bm25_scores = _BM25.get_scores(q_tokens)
        bm25_ranked = [
            i for i, s in sorted(enumerate(bm25_scores), key=lambda x: -x[1])
            if s > 0
        ]
    else:
        bm25_ranked = []

    dense_ranked: list[int] = []
    if _DENSE is not None and query.strip():
        try:
            q_vec = await _embed([query])
            sims = (_DENSE @ q_vec[0])
            dense_ranked = [
                i for i, s in sorted(enumerate(sims), key=lambda x: -x[1])
                if s > 0
            ]
        except Exception as e:
            log.warning("dense query failed (%s); using BM25 only", e)

    rankings = [r for r in (bm25_ranked, dense_ranked) if r]
    if not rankings:
        return ""

    fused = _rrf_fuse(rankings, rrf_k=settings.rag_rrf_k, n_docs=len(blocks))
    if not fused:
        return ""

    best = [blocks[i] for i, _ in fused[:top_k]]
    return "\n\n---\n\n".join(best)


def invalidate_cache() -> None:
    global _BLOCKS, _BM25, _DENSE
    _BLOCKS = None
    _BM25 = None
    _DENSE = None

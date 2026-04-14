"""
indexer.py — индексация YAML-библиотеки Lua-паттернов в ChromaDB
и dense-retrieval через BGE-M3 (CPU).

Запуск:
    python -m rag.indexer index
    python -m rag.indexer query "распарсить JSON и взять email"
    python -m rag.indexer query "отдать 404" --category routing -k 2
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from rag.schema import LuaPattern


PATTERNS_DIR = Path(__file__).parent / "patterns"
CHROMA_DIR = Path(__file__).parent / "chroma_db"
COLLECTION_NAME = "lua_patterns"
EMBEDDING_MODEL = "BAAI/bge-m3"


_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
    return _embedder


def _iter_yaml_docs(raw: Any, path: Path) -> list[dict]:
    if raw is None:
        return []
    if isinstance(raw, list):
        for i, item in enumerate(raw):
            if not isinstance(item, dict):
                raise RuntimeError(
                    f"Bad pattern file {path}: item #{i} is {type(item).__name__}, expected mapping"
                )
        return raw
    if isinstance(raw, dict):
        return [raw]
    raise RuntimeError(
        f"Bad pattern file {path}: top-level is {type(raw).__name__}, expected mapping or list"
    )


def load_patterns(patterns_dir: Path) -> list[LuaPattern]:
    if not patterns_dir.exists():
        raise RuntimeError(f"Patterns directory not found: {patterns_dir}")

    files = sorted([*patterns_dir.rglob("*.yaml"), *patterns_dir.rglob("*.yml")])
    patterns: list[LuaPattern] = []
    seen: dict[str, Path] = {}

    for path in files:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            raise RuntimeError(f"Bad pattern file {path}: {e}") from e

        for doc in _iter_yaml_docs(raw, path):
            try:
                pattern = LuaPattern.model_validate(doc)
            except ValidationError as e:
                raise RuntimeError(f"Bad pattern file {path}: {e}") from e

            if pattern.id in seen:
                raise RuntimeError(
                    f"Duplicate pattern id '{pattern.id}' in {path} (already defined in {seen[pattern.id]})"
                )
            seen[pattern.id] = path
            patterns.append(pattern)

    return patterns


def build_embedding_text(p: LuaPattern) -> str:
    return f"{p.task_description} | {p.category}"


def build_document(p: LuaPattern) -> str:
    return f"-- {p.task_description}\n{p.code.rstrip()}\n"


def build_metadata(p: LuaPattern) -> dict[str, str]:
    md: dict[str, str] = {
        "id": p.id,
        "category": p.category,
        "task_description": p.task_description,
        "lua_version": p.lua_version,
        "dependencies": ",".join(p.dependencies),
    }
    for key in ("complexity", "source", "signature"):
        value = getattr(p, key)
        if value is not None:
            md[key] = value
    return md


def _open_collection():
    import chromadb

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def cmd_index(_args: argparse.Namespace) -> int:
    patterns = load_patterns(PATTERNS_DIR)
    if not patterns:
        print(f"No patterns found in {PATTERNS_DIR}. Nothing to index.", file=sys.stderr)
        return 0

    texts = [build_embedding_text(p) for p in patterns]
    embedder = _get_embedder()
    embeddings = embedder.encode(
        texts,
        normalize_embeddings=True,
        batch_size=32,
        show_progress_bar=True,
    )

    collection = _open_collection()
    collection.upsert(
        ids=[p.id for p in patterns],
        embeddings=embeddings.tolist(),
        documents=[build_document(p) for p in patterns],
        metadatas=[build_metadata(p) for p in patterns],
    )

    print(f"Indexed {len(patterns)} patterns into '{COLLECTION_NAME}' at {CHROMA_DIR}")
    return 0


def search_patterns(
    query: str,
    category_filter: str | None = None,
    k: int = 2,
) -> list[dict]:
    embedder = _get_embedder()
    query_embedding = embedder.encode(
        [query],
        normalize_embeddings=True,
    )[0].tolist()

    collection = _open_collection()
    where = {"category": category_filter} if category_filter else None
    res = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        where=where,
    )

    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]

    results: list[dict] = []
    for doc, meta, dist in zip(docs, metas, dists):
        results.append(
            {
                "code": doc,
                "task_description": meta.get("task_description", ""),
                "category": meta.get("category", ""),
                "score": 1.0 - float(dist),
            }
        )
    return results


def cmd_query(args: argparse.Namespace) -> int:
    results = search_patterns(args.text, category_filter=args.category, k=args.k)
    if not results:
        print("No results.")
        return 0

    for i, r in enumerate(results, 1):
        head = f"{i}. [score={r['score']:.3f}] {r['category']} — {r['task_description']}"
        print(head)
        preview = "\n".join(r["code"].splitlines()[:10])
        print(preview)
        print("---")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rag.indexer")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("index", help="rebuild ChromaDB index from rag/patterns/")

    q = sub.add_parser("query", help="test retrieval against the index")
    q.add_argument("text", help="natural-language task description")
    q.add_argument("--category", default=None, help="optional category filter")
    q.add_argument("-k", type=int, default=3, help="number of results (default: 3)")

    args = parser.parse_args(argv)
    if args.cmd == "index":
        return cmd_index(args)
    if args.cmd == "query":
        return cmd_query(args)
    parser.error(f"unknown command: {args.cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

# rag — ChromaDB-индекс курируемых Lua-паттернов

Dense-retrieval (BGE-M3, CPU) по YAML-библиотеке паттернов для RAG-подачи в Coder-агент.

## Установка

```bash
cd mts-backend-lua
source .venv/bin/activate
pip install -r rag/requirements.txt
```

## Добавление паттерна

Положи YAML в `rag/patterns/` (см. формат в `schema.py`: обязательны `id`, `category`, `task_description`, `code`).

## Индексация и поиск

```bash
python -m rag.indexer index                              # пересобрать индекс (идемпотентно)
python -m rag.indexer query "распарсить JSON и взять email"
python -m rag.indexer query "отдать 404" --category routing -k 2
```

Первый `index` качает веса BGE-M3 (~2 GB в HF-кэш). При удалении паттернов с диска — удали `rag/chroma_db/` и переиндексируй.

"""
config.py — все настройки через переменные окружения.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "lua-coder:mts"

    embed_base_url: str = "http://localhost:11434/v1"
    embed_api_key: str = "ollama"
    embed_model: str = "nomic-embed-text"
    rag_top_k: int = 2
    rag_rrf_k: int = 60

    planner_max_tokens: int = 256
    lua_node_max_tokens: int = 256
    fixer_max_tokens: int = 256
    clarifier_max_tokens: int = 128

    max_fix_cycles: int = 1
    clarification_session_ttl: int = 1800

    docs_path: str = "docs/lua_examples.txt"

    # Input-token budget for user-composed context in /generate-from-context.
    # num_ctx=4096 minus system+user+output-256 → ≈2800 is a safe ceiling.
    context_budget_tokens: int = 2800

    class Config:
        env_file = "../../.env"
        env_file_encoding = "utf-8"


settings = Settings()

"""
config.py — все настройки через переменные окружения.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "lua-coder:mts"

    planner_max_tokens: int = 256
    coder_max_tokens: int = 256
    fixer_max_tokens: int = 256

    max_fix_cycles: int = 3

    docs_path: str = "docs/lua_examples.txt"

    class Config:
        env_file = "../../.env"
        env_file_encoding = "utf-8"


settings = Settings()

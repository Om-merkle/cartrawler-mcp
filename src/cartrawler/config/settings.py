"""Application configuration via pydantic-settings."""
from functools import lru_cache
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[3]  # repo root


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────────
    app_name: str = "CarTrawler MCP"
    app_env: str = "development"
    debug: bool = True
    port: int = 8000

    # ── Database ───────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/cartrawler"
    )
    database_url_sync: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/cartrawler"
    )

    # ── Supabase ───────────────────────────────────────────────────────────────
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    # ── Auth / JWT ─────────────────────────────────────────────────────────────
    jwt_secret_key: str = "dev-secret-change-in-production-please"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # ── OpenAI ─────────────────────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    # ── MCP ────────────────────────────────────────────────────────────────────
    mcp_server_name: str = "cartrawler-mcp"
    mcp_server_host: str = "0.0.0.0"
    mcp_server_port: int = 8000
    mcp_server_base_url: str = "https://cartrawler-mcp-y81f.onrender.com"

    # ── External APIs ──────────────────────────────────────────────────────────
    cartrawler_api_key: str = ""
    cartrawler_base_url: str = "https://api.cartrawler.com/v1"
    hotel_api_key: str = ""
    hotel_base_url: str = ""

    # ── RAG / Vector ──────────────────────────────────────────────────────────
    vector_store_table: str = "knowledge_base_embeddings"
    embedding_dimension: int = 1536

    @computed_field
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @computed_field
    @property
    def data_dir(self) -> Path:
        return BASE_DIR / "data"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

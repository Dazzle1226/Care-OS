from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Care OS Pro Max API"
    api_prefix: str = "/api"
    jwt_secret: str = Field(default="care-os-demo-secret-change-me", alias="CARE_OS_JWT_SECRET")
    jwt_expire_minutes: int = 60 * 24 * 7

    base_dir: Path = Path(__file__).resolve().parents[2]
    database_url: str | None = Field(default=None, alias="CARE_OS_DATABASE_URL")

    embedding_provider: str = Field(default="hash", alias="CARE_OS_EMBEDDING_PROVIDER")
    embedding_dim: int = 256
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4o-mini"

    force_rule_fallback: bool = Field(default=False, alias="CARE_OS_FORCE_RULE_FALLBACK")

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
    ]

    high_risk_keywords: list[str] = [
        "自伤",
        "他伤",
        "伤害自己",
        "伤害他人",
        "想打人",
        "失控攻击",
        "撞头",
        "掐脖子",
        "持刀",
        "咬人",
        "knife",
        "suicide",
        "harm",
    ]

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        db_path = self.base_dir / "data" / "care_os.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path.as_posix()}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

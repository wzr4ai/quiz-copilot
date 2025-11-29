from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "SmartQuiz API"
    version: str = "0.1.0"
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    debug: bool = Field(default=False, validation_alias="DEBUG")
    database_url: str = Field(
        default="postgresql+psycopg://quiz_user:quiz_pass@localhost:5432/quiz_db",
        description="SQLAlchemy-compatible database URL",
        validation_alias=AliasChoices("DATABASE_URL", "DB_URL"),
    )
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    secret_key: str = Field(default="change-me", validation_alias="SECRET_KEY")
    access_token_expire_minutes: int = Field(
        default=60, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    cors_origins: list[str] = ["*"]
    gemini_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("GEMINI_API_KEY", "GEMINI_KEY")
    )
    gemini_api_base: str = Field(
        default="https://generativelanguage.googleapis.com",
        validation_alias=AliasChoices("GEMINI_API_BASE", "GEMINI_URL"),
    )
    gemini_model: str = "gemini-2.5-flash"
    gemini_request_timeout: int = 40
    zai_api_key: str | None = Field(default=None, validation_alias="ZAI_API_KEY")
    zai_api_base: str | None = Field(default=None, validation_alias="ZAI_API_BASE")
    zai_model: str | None = Field(default=None, validation_alias="ZAI_MODEL")

    class Config:
        env_file = str(Path(__file__).resolve().parents[3] / ".env")
        env_file_encoding = "utf-8"


settings = Settings()

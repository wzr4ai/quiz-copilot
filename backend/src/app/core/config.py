from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "SmartQuiz API"
    version: str = "0.1.0"
    database_url: str = Field(
        default="postgresql+psycopg://quiz_user:quiz_pass@localhost:5432/quiz_db",
        description="SQLAlchemy-compatible database URL",
    )
    cors_origins: list[str] = ["*"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

from __future__ import annotations

from typing import Generator

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

engine = create_engine(settings.database_url, echo=settings.debug)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _run_schema_patches()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def _run_schema_patches() -> None:
    """Lightweight, idempotent schema patches for new columns without Alembic."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE question "
                "ADD COLUMN IF NOT EXISTS practice_count INTEGER NOT NULL DEFAULT 0"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE smartpracticesession "
                "ADD COLUMN IF NOT EXISTS current_question_index INTEGER NOT NULL DEFAULT 0"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE smartpracticesession "
                "ADD COLUMN IF NOT EXISTS lowest_count_remaining INTEGER"
            )
        )

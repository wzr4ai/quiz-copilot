from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Column, UniqueConstraint, Enum
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    role: str = Field(default="user", sa_column=Column(Enum("user", "admin", name="user_role")))
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class Bank(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: Optional[str] = None
    is_public: bool = False
    created_by: int | None = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class Question(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    bank_id: int = Field(foreign_key="bank.id", index=True)
    type: str
    content: str
    options: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    standard_answer: str
    analysis: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class WrongRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    question_id: int = Field(foreign_key="question.id", index=True)
    user_answer: str
    correct_answer: str
    is_correct: bool
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class QuestionIssue(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    question_id: int = Field(foreign_key="question.id", index=True)
    bank_id: int = Field(foreign_key="bank.id", index=True)
    reason: str = Field(default="")
    status: str = Field(default="pending", description="pending | verified_ok | corrected")
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class FavoriteBank(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    bank_id: int = Field(foreign_key="bank.id")

    __table_args__ = (UniqueConstraint("user_id", "bank_id", name="uq_user_bank_fav"),)


class FavoriteQuestion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    question_id: int = Field(foreign_key="question.id")

    __table_args__ = (UniqueConstraint("user_id", "question_id", name="uq_user_question_fav"),)


class StudySession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    bank_id: int = Field(foreign_key="bank.id", index=True)
    mode: str
    score: int = 0
    answers: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

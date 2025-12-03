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
    practice_count: int = Field(default=0, description="累计正确刷题计数")
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


class SmartPracticeSettings(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    bank_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    target_count: int = Field(default=50, description="每组题目数量")
    guaranteed_low_count: int = Field(default=20, description="每批保底抽取的低计数题数量")
    type_ratio: dict = Field(default_factory=dict, sa_column=Column(JSON))
    realtime_analysis: bool = Field(default=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class SmartPracticeSession(SQLModel, table=True):
    id: str = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    settings_snapshot: dict = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = Field(default="in_progress", description="pending | in_progress | reinforce | completed")
    current_group_index: int = Field(default=0)
    current_question_index: int = Field(default=0, description="当前题组内的题目索引")
    round: int = Field(default=1, description="当前刷题轮次，从1开始")
    realtime_analysis: bool = Field(default=False)
    lowest_count_remaining: int | None = Field(default=None, description="当前轮次最低计数的题目数量")
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class SmartPracticeGroup(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="smartpracticesession.id", index=True)
    group_index: int = Field(default=0)
    mode: str = Field(default="normal", description="normal | reinforce")
    total_questions: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class SmartPracticeItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="smartpracticegroup.id", index=True)
    question_id: int = Field(foreign_key="question.id", index=True)
    question_type: str
    position: int = Field(default=0)
    is_reinforce: bool = Field(default=False)


class SmartPracticeAnswer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="smartpracticesession.id", index=True)
    question_id: int = Field(foreign_key="question.id", index=True)
    user_answer: str
    is_correct: bool
    counted: bool = Field(default=False, description="是否已计入 practice_count")
    answered_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class SmartPracticeFeedback(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="smartpracticesession.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    question_id: int = Field(foreign_key="question.id", index=True)
    reason: str = Field(default="", description="用户反馈的题目问题")
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

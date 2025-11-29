#!/usr/bin/env python3
"""Fix choice_single questions with standard_answer X/V/N to judgment type for bank 154."""

from __future__ import annotations

from sqlmodel import Session, select

from app.db import engine
from app.models.db_models import Question

TARGET_BANK_ID = 153


def fix_questions() -> int:
    fixed = 0
    with Session(engine) as session:
        stmt = select(Question).where(
            Question.bank_id == TARGET_BANK_ID,
            Question.type == "choice_single",
            Question.standard_answer.in_(["X", "V", "N"]),
        )
        rows = session.exec(stmt).all()
        for q in rows:
            if q.standard_answer in {"X"}:
                q.type = "choice_judgment"
                q.options = [{"key": "A", "text": "正确"}, {"key": "B", "text": "错误"}]
                q.standard_answer = "B"
                session.add(q)
                fixed += 1
            elif q.standard_answer in {"V", "N"}:
                q.type = "choice_judgment"
                q.options = [{"key": "A", "text": "正确"}, {"key": "B", "text": "错误"}]
                q.standard_answer = "A"
                session.add(q)
                fixed += 1
        session.commit()
    return fixed


def main() -> int:
    fixed = fix_questions()
    print(f"Fixed {fixed} questions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fix fill-in questions mis-tagged as choice in bank 153.

Rule:
- bank_id == 153
- options 为空/长度为 0
- standard_answer 不是仅包含英文字母/逗号/空格（即不是 A/B/C 等）
- 将题型改为 short_answer，保留题干与标准答案。
"""

from __future__ import annotations

import re
from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.db import engine
from app.models.db_models import Question

TARGET_BANK_ID = 155


def is_alpha_answers(val: str) -> bool:
    """Return True if answer is only letters/commas/spaces (e.g., A, B, AB)."""
    return bool(re.fullmatch(r"[A-Z,\\s]+", val.strip().upper()))


def fix_questions() -> int:
    fixed = 0
    with Session(engine) as session:
        stmt = select(Question).where(
            Question.bank_id == TARGET_BANK_ID,
            func.json_array_length(Question.options) == 0,
        )
        rows = session.exec(stmt).all()
        for q in rows:
            ans = (q.standard_answer or "").strip()
            if not ans:
                continue
            if is_alpha_answers(ans):
                continue
            if q.type.startswith("choice"):
                q.type = "short_answer"
                # 保持 options 为空，答案保留
                session.add(q)
                fixed += 1
        session.commit()
    return fixed


def main() -> int:
    fixed = fix_questions()
    print(f"Converted {fixed} questions to short_answer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Import question issues from logs/question_issue.log into DB."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlmodel import Session

from app.db import engine
from app.models.db_models import Question, QuestionIssue

logger = logging.getLogger("import_issue_log")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def parse_line(line: str) -> tuple[Optional[int], str]:
    parts = line.split("|")
    qid = None
    reason = ""
    for part in parts:
        if "qid=" in part:
            try:
                qid = int(part.split("qid=")[-1].strip())
            except ValueError:
                qid = None
        if "reason=" in part:
            reason = part.split("reason=")[-1].strip()
    return qid, reason


def import_issues(log_path: Path) -> int:
    added = 0
    with Session(engine) as session:
        for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            qid, reason = parse_line(line)
            if not qid:
                continue
            exists = session.exec(select(QuestionIssue).where(QuestionIssue.question_id == qid)).first()
            if exists:
                continue
            question = session.exec(select(Question).where(Question.id == qid)).first()
            if not question:
                continue
            issue = QuestionIssue(question_id=qid, bank_id=question.bank_id, reason=reason or "")
            session.add(issue)
            session.commit()
            session.refresh(issue)
            added += 1
            logger.info("Added issue for qid=%s", qid)
    return added


def main() -> int:
    log_path = Path(__file__).resolve().parents[1] / "logs" / "question_issue.log"
    if not log_path.exists():
        logger.error("question_issue.log not found at %s", log_path)
        return 1
    added = import_issues(log_path)
    logger.info("Done. Imported %s issue records.", added)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

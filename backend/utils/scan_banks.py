#!/usr/bin/env python3
"""Scan database question banks and print question counts."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

from app.db import engine
from app.models.db_models import Bank, Question

logger = logging.getLogger("scan_banks")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logs_dir = Path(__file__).resolve().parents[1] / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)
missing_log = logging.getLogger("scan_banks.missing")
missing_handler = logging.FileHandler(logs_dir / "missing_answers.log", encoding="utf-8")
missing_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
missing_log.addHandler(missing_handler)
missing_log.setLevel(logging.INFO)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="List banks and question counts.")
    parser.add_argument("--json", action="store_true", help="Output as JSON.")
    parser.add_argument("--log-missing", action="store_true", help="Log questions missing answers to logs/missing_answers.log")
    return parser.parse_args()


def scan() -> list[dict[str, Any]]:
    with Session(engine) as session:
        banks = session.exec(select(Bank)).all()
        # fallback: if banks table sparse, still report total questions
        total_questions = session.exec(select(func.count(Question.id))).one() or 0
        results: list[dict[str, Any]] = []
        for bank in banks:
            count = session.exec(select(func.count(Question.id)).where(Question.bank_id == bank.id)).one()
            results.append(
                {
                    "id": bank.id,
                    "title": bank.title,
                    "is_public": bank.is_public,
                    "description": bank.description or "",
                    "question_count": count or 0,
                }
            )
        # Add aggregate summary
        results.append({"id": -1, "title": "ALL", "is_public": True, "description": "所有题目汇总", "question_count": total_questions})
        return results


def log_missing_answers() -> int:
    missing_count = 0
    with Session(engine) as session:
        # Iterate by qid to avoid omissions
        stmt = select(Question).order_by(Question.id.asc())
        for q in session.exec(stmt).all():
            if not q.standard_answer or str(q.standard_answer).strip() == "":
                bank = session.get(Bank, q.bank_id)
                missing_log.info(
                    "Missing answer | bank=%s(%s) | qid=%s | content=%s",
                    bank.title if bank else "",
                    q.bank_id,
                    q.id,
                    q.content,
                )
                missing_count += 1
    return missing_count


def main() -> int:
    args = parse_args()
    try:
        data = scan()
        missing = log_missing_answers() if args.log_missing else 0
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to scan banks: %s", exc)
        return 1
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        for item in data:
            print(f"[{item['id']}] {item['title']} (public={item['is_public']}) - questions={item['question_count']}")
        if args.log_missing:
            print(f"Missing answers logged: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

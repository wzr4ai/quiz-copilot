#!/usr/bin/env python3
"""Fill missing/empty analyses in DB questions using ZAI (glm-4.5)."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from openai import AsyncOpenAI
from sqlmodel import Session, select

from app.core.config import settings
from app.db import engine
from app.models.db_models import Bank, Question

logger = logging.getLogger("fill_missing_analysis_db")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logs_dir = Path(__file__).resolve().parents[1] / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)
file_handler = logging.FileHandler(logs_dir / "fill_missing_analysis_db.log", encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(file_handler)

issue_log = logging.getLogger("fill_missing_analysis_db.issue")
issue_handler = logging.FileHandler(logs_dir / "question_issue.log", encoding="utf-8")
issue_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
issue_log.addHandler(issue_handler)
issue_log.setLevel(logging.INFO)

analysis_log = logging.getLogger("fill_missing_analysis_db.analysis")
analysis_handler = logging.FileHandler(logs_dir / "analysis_corrections.log", encoding="utf-8")
analysis_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
analysis_log.addHandler(analysis_handler)
analysis_log.setLevel(logging.INFO)


SYSTEM_PROMPT = (
    "你是命题质检与解析助手。根据题干、选项、标准答案与当前解析，输出评估结果：\n"
    "返回 JSON 对象，字段：\n"
    "- answer_issue: bool  (题目/答案可能有误或不自洽时为 true)\n"
    "- analysis_issue: bool (仅当当前解析为空/缺失，或明显错误/跑题/与答案矛盾时为 true；轻微措辞不调整)\n"
    "- analysis: string     (当 analysis_issue 为 true 或解析为空时，生成一句话解析；选择题需说明干扰项不选理由；末尾加 \"by glm-4.5\"；\n"
    "                       若答案显而易见，可填 \"显而易见 by glm-4.5\"；无需修改可留空)\n"
    "- reason: string       (简要说明问题或生成解析的依据)\n"
    "不要输出额外文本或代码块。"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fill missing analyses in DB using glm-4.5 (ZAI).")
    parser.add_argument("--model", default=None, help="Model name, default uses ZAI_MODEL or glm-4.5.")
    parser.add_argument("--limit", type=int, default=None, help="Max questions to process (overall).")
    parser.add_argument("--concurrency", type=int, default=3, help="Concurrent requests to ZAI.")
    parser.add_argument("--bank-id", type=int, default=None, help="Optional bank id filter.")
    parser.add_argument("--only-missing", action="store_true", help="Only process questions with empty analysis.")
    return parser.parse_args()


def build_user_prompt(q: Question) -> str:
    lines = [f"题干: {q.content}", f"答案: {q.standard_answer}"]
    if q.options:
        opt_lines = [f"{opt.get('key')}: {opt.get('text')}" for opt in q.options if isinstance(opt, dict)]
        lines.append("选项:\n" + "\n".join(opt_lines))
    current_analysis = (q.analysis or "").strip()
    if current_analysis:
        lines.append(f"当前解析: {current_analysis}")
    else:
        lines.append("当前解析: （空）")
    return "\n".join(lines)


async def call_zai(prompt: str, client: AsyncOpenAI, model: str) -> str:
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=256,
        temperature=0.2,
        extra_body={"thinking": {"type": "disabled"}},
    )
    content = resp.choices[0].message.content if resp.choices else ""
    if not content:
        raise RuntimeError("ZAI 返回为空")
    return content


async def process_question(
    sem: asyncio.Semaphore,
    client: AsyncOpenAI,
    model: str,
    q: Question,
) -> Dict[str, Any]:
    async with sem:
        prompt = build_user_prompt(q)
        raw = await call_zai(prompt, client, model)
        data = json.loads(raw)
        return data


async def main() -> int:
    args = parse_args()
    model = args.model or settings.zai_model or "glm-4.5"
    if not settings.zai_api_key:
        logger.error("ZAI_API_KEY 未配置 (.env)")
        return 1
    client = AsyncOpenAI(api_key=settings.zai_api_key, base_url=settings.zai_api_base)
    sem = asyncio.Semaphore(max(1, args.concurrency))
    total_processed = 0
    total_filled = 0
    total_failed = 0

    with Session(engine) as session:
        banks = {b.id: b for b in session.exec(select(Bank)).all()}
        stmt = select(Question)
        if args.bank_id:
            stmt = stmt.where(Question.bank_id == args.bank_id)
        if args.only_missing:
            stmt = stmt.where((Question.analysis.is_(None)) | (Question.analysis == ""))  # type: ignore
        if args.limit:
            stmt = stmt.limit(args.limit)
        questions = session.exec(stmt).all()
        if not questions:
            logger.info("No questions with missing analysis found.")
            return 0
        logger.info("Found %s questions to analyze", len(questions))

        for q in questions:
            total_processed += 1
            try:
                result = await process_question(sem, client, model, q)
                answer_issue = bool(result.get("answer_issue"))
                analysis_issue = bool(result.get("analysis_issue"))
                new_analysis = str(result.get("analysis") or "").strip()
                reason = str(result.get("reason") or "").strip()
                bank_title = (banks.get(q.bank_id).title if banks.get(q.bank_id) else f"Bank {q.bank_id}")

                if answer_issue:
                    issue_log.info(
                        "疑似题目/答案有误 | bank=%s(id=%s) qid=%s | reason=%s | content=%s",
                        bank_title,
                        q.bank_id,
                        q.id,
                        reason,
                        q.content,
                    )

                if analysis_issue and new_analysis:
                    old = (q.analysis or "").strip()
                    q.analysis = new_analysis
                    session.add(q)
                    session.commit()
                    session.refresh(q)
                    total_filled += 1
                    analysis_log.info(
                        "解析修正 | bank=%s(id=%s) qid=%s | old=%s | new=%s | reason=%s",
                        bank_title,
                        q.bank_id,
                        q.id,
                        old,
                        new_analysis,
                        reason,
                    )
                elif (not q.analysis or q.analysis.strip() == "") and new_analysis:
                    q.analysis = new_analysis
                    session.add(q)
                    session.commit()
                    session.refresh(q)
                    total_filled += 1
                    logger.info("Filled missing analysis for qid=%s bank_id=%s", q.id, q.bank_id)
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                total_failed += 1
                qid = getattr(q, "id", None)
                logger.error("Failed qid=%s: %s", qid, exc)
                continue

    logger.info("Done. processed=%s filled=%s failed=%s", total_processed, total_filled, total_failed)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

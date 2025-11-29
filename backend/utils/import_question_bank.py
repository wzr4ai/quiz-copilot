#!/usr/bin/env python3
"""Batch import processed question banks.

Supports two processed formats produced by ``question_bank_tool.py``:
- ``*.converted.json``: already structured question objects.
- ``*.chunks.jsonl``: text chunks that need AI parsing to extract questions.

Per file, a bank is created (or reused) using the meaningful part of the
filename as the bank title.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Iterable, List, Optional

import httpx
from sqlmodel import Session, select

from app.core.config import settings
from app.db import engine, init_db
from app.models.db_models import Bank, Question as QuestionDB
from app.models.schemas import Option, QuestionCreate
from app.services.ai_service import AIServiceError
from app.services.batch_importer import BatchImportService


def _configure_logger() -> logging.Logger:
    logger = logging.getLogger("import_question_bank")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)
    logs_dir = Path(__file__).resolve().parents[1] / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(logs_dir / "import_question_bank.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


logger = _configure_logger()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import processed question banks into the database.")
    parser.add_argument("--input", "-i", default="processed_question_bank", help="Directory containing processed files.")
    parser.add_argument("--limit", type=int, default=None, help="Max files to import (for quick tests).")
    parser.add_argument(
        "--ai-model",
        default=None,
        help="Override model for AI parsing text chunks; default uses settings.gemini_model.",
    )
    return parser.parse_args()


def iter_processed_files(folder: Path) -> Iterable[Path]:
    for path in sorted(folder.glob("*.converted.json")):
        yield path
    for path in sorted(folder.glob("*.chunks.jsonl")):
        yield path


def derive_bank_title(path: Path) -> str:
    stem = path.name
    for suffix in (".converted.json", ".chunks.jsonl", ".json", ".jsonl"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    stem = re.sub(r"[_\\s]+", " ", stem).strip()
    return stem or "题库"


def ensure_bank(session: Session, title: str) -> Bank:
    existing = session.exec(select(Bank).where(Bank.title == title)).first()
    if existing:
        return existing
    bank = Bank(title=title, description=f"{title} 自动导入")
    session.add(bank)
    session.commit()
    session.refresh(bank)
    logger.info("Created bank: %s (id=%s)", title, bank.id)
    return bank


def normalize_question_dict(item: dict, bank_id: int) -> Optional[QuestionCreate]:
    content = str(item.get("content") or item.get("问题") or "").strip()
    if not content:
        return None
    raw_options = item.get("options") or item.get("选项") or []
    options: List[Option] = []
    if isinstance(raw_options, dict):
        for key, text in raw_options.items():
            options.append(Option(key=str(key).strip(), text=str(text).strip()))
    elif isinstance(raw_options, list):
        for opt in raw_options:
            if isinstance(opt, dict) and "key" in opt and "text" in opt:
                options.append(Option(key=str(opt["key"]).strip(), text=str(opt["text"]).strip()))
    standard_answer = str(
        item.get("standard_answer") or item.get("答案") or item.get("answer") or ""
    ).strip()
    qtype = str(item.get("type") or "choice_single").strip() or "choice_single"
    analysis = item.get("analysis") or item.get("解析")
    return QuestionCreate(
        bank_id=bank_id,
        type=qtype,
        content=content,
        options=options,
        standard_answer=standard_answer,
        analysis=analysis if analysis is None else str(analysis),
    )


TEXT_PROMPT = (
    "你是一名教育测评数据标注助手。请从下面的原始试题文本中提取结构化题目。\n"
    "要求：\n"
    "1) 输出必须是 JSON 数组，禁止返回代码块或其他文字。\n"
    '2) 字段：type( choice_single | choice_multi | choice_judgment | short_answer ), '
    "content, options(数组，含 key 与 text)，standard_answer，analysis(可空字符串)。\n"
    "3) 判断题 type=choice_judgment，选项仅 A=正确、B=错误，standard_answer 填 A 或 B。\n"
    "4) 若原文选项中某个选项用 <ANS>…</ANS> 标记或含有“√”，视为正确答案。多个正确答案则使用逗号分隔。\n"
    "5) 如果未明确给出答案，standard_answer 留空字符串。\n"
    "6) 保持题干与选项文字原样（去掉多余空白即可），不要虚构内容。"
)


async def _call_gemini_text(prompt: str, text: str, model: str) -> str:
    api_key = settings.gemini_api_key
    if not api_key:
        raise AIServiceError("Gemini API key 未配置 (.env 中设置 GEMINI_API_KEY)")
    url = f"{settings.gemini_api_base.rstrip('/')}/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {"text": f"原始文本：\n{text}"},
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2048,
            "response_mime_type": "application/json",
        },
    }
    async with httpx.AsyncClient(timeout=settings.gemini_request_timeout) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
    data = resp.json()
    for candidate in data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            text_part = part.get("text")
            if text_part:
                return text_part
    raise AIServiceError("Gemini 未返回可用文本")


def _strip_code_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.lstrip("`")
        if "\n" in cleaned:
            cleaned = cleaned.split("\n", 1)[1]
    if cleaned.endswith("```"):
        cleaned = cleaned[: cleaned.rfind("```")].strip()
    return cleaned


async def parse_chunk_with_ai(chunk_text: str, bank_id: int, model: str) -> List[QuestionCreate]:
    raw_text = await _call_gemini_text(TEXT_PROMPT, chunk_text, model=model)
    cleaned = _strip_code_fence(raw_text)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise AIServiceError(f"AI 返回非 JSON: {exc}") from exc
    questions: List[QuestionCreate] = []
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                qc = normalize_question_dict(item, bank_id)
                if qc:
                    questions.append(qc)
    if not questions:
        raise AIServiceError("AI 未生成题目")
    return questions


def import_questions(session: Session, importer: BatchImportService, bank: Bank, questions: List[QuestionCreate]) -> dict:
    stats = {"imported": 0, "duplicates": 0}
    for q in questions:
        dup = importer._find_duplicate(q)  # type: ignore[attr-defined]
        if dup:
            stats["duplicates"] += 1
            continue
        record = QuestionDB(
            bank_id=q.bank_id,
            type=q.type,
            content=q.content,
            options=[opt.model_dump() for opt in q.options],
            standard_answer=q.standard_answer,
            analysis=q.analysis,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        stats["imported"] += 1
    return stats


async def process_file(session: Session, path: Path, ai_model: str) -> None:
    bank_title = derive_bank_title(path)
    bank = ensure_bank(session, bank_title)
    importer = BatchImportService(session=session, ai=None)  # ai unused here
    imported_total = 0
    duplicate_total = 0
    ai_failed_chunks = 0

    if path.suffix == ".json":
        logger.info("Processing structured file: %s", path.name)
        data = json.loads(path.read_text(encoding="utf-8"))
        questions: List[QuestionCreate] = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    qc = normalize_question_dict(item, bank.id)
                    if qc:
                        questions.append(qc)
        stats = import_questions(session, importer, bank, questions)
        imported_total += stats["imported"]
        duplicate_total += stats["duplicates"]
    elif path.suffix == ".jsonl":
        logger.info("Processing chunked file (AI): %s", path.name)
        with path.open("r", encoding="utf-8") as fh:
            lines = [json.loads(line) for line in fh if line.strip()]
        for idx, record in enumerate(lines, start=1):
            chunk_text = str(record.get("text") or "").strip()
            if not chunk_text:
                continue
            try:
                questions = await parse_chunk_with_ai(chunk_text, bank.id, model=ai_model)
                stats = import_questions(session, importer, bank, questions)
                imported_total += stats["imported"]
                duplicate_total += stats["duplicates"]
                logger.info("Chunk %s imported: +%s (duplicates %s)", idx, stats["imported"], stats["duplicates"])
            except AIServiceError as exc:
                ai_failed_chunks += 1
                logger.error("AI failed on chunk %s (%s): %s", idx, path.name, exc)
            except httpx.HTTPError as exc:
                ai_failed_chunks += 1
                logger.error("HTTP error on chunk %s (%s): %s", idx, path.name, exc)
    logger.info(
        "File done: %s (bank=%s) imported=%s duplicates=%s ai_failed_chunks=%s",
        path.name,
        bank_title,
        imported_total,
        duplicate_total,
        ai_failed_chunks,
    )


async def main() -> int:
    args = parse_args()
    input_dir = Path(args.input).expanduser().resolve()
    if not input_dir.exists():
        logger.error("Input directory not found: %s", input_dir)
        return 1
    init_db()
    files = list(iter_processed_files(input_dir))
    if args.limit:
        files = files[: args.limit]
    if not files:
        logger.error("No processed files found in %s", input_dir)
        return 1
    logger.info("Found %s processed files", len(files))

    ai_model = args.ai_model or settings.gemini_model

    with Session(engine) as session:
        for path in files:
            try:
                await process_file(session, path, ai_model=ai_model)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to import %s: %s", path.name, exc)
    logger.info("All done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

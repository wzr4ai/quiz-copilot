#!/usr/bin/env python3
"""Batch import processed question banks using ZAI (OpenAI-compatible) model."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Iterable, List, Optional

from openai import AsyncOpenAI
from sqlmodel import Session, select

from app.core.config import settings
from app.db import engine, init_db
from app.models.db_models import Bank, Question as QuestionDB
from app.models.schemas import Option, QuestionCreate
from app.services.batch_importer import BatchImportService


def _configure_logger() -> logging.Logger:
    logger = logging.getLogger("import_question_bank_zai")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)
    logs_dir = Path(__file__).resolve().parents[1] / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(logs_dir / "import_question_bank_zai.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


logger = _configure_logger()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import processed question banks with ZAI model.")
    parser.add_argument("--input", "-i", default="processed_question_bank", help="Directory containing processed files.")
    parser.add_argument("--limit", type=int, default=None, help="Max files to import (for quick tests).")
    parser.add_argument("--retries", type=int, default=3, help="Max retries per chunk when AI parsing fails.")
    parser.add_argument("--concurrency", type=int, default=3, help="Concurrent AI parse requests for chunks.")
    parser.add_argument(
        "--model",
        default=None,
        help="Override ZAI model; defaults to ZAI_MODEL or falls back to settings.zai_model.",
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
    return (stem or "题库") + " (zai)"


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
    standard_answer = str(item.get("standard_answer") or item.get("答案") or item.get("answer") or "").strip()
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
    "你是一名教育测评数据标注助手。请从下面的原始试题文本中提取结构化题目，并进行轻量纠错。\n"
    "由于习惯格式不同，有的题目答案可能是在题目选项中，正确选项后有特殊标记（打勾标记或者文字标记），有的是在题目中写出正确选项，你需要正确识别并理解。\n"
    "输出要求（务必遵守）：\n"
    "1) 仅输出合法的 JSON 数组，不要输出额外文本、解释或代码块标记。\n"
    '2) 数组元素字段：type( choice_single | choice_multi | choice_judgment | short_answer ), '
    "content, options(数组，含 key 与 text)，standard_answer，analysis(可空字符串)。\n"
    "3) 判断题 type=choice_judgment，选项仅 A=正确、B=错误，standard_answer 填 A 或 B。\n"
    "4) 保持题干与选项文字原样（去掉多余空白即可），不要虚构内容。\n"
    "示例输出（严格遵循键名与双引号，并确保 JSON 可被解析）：\n"
    '[{"type":"choice_single","content":"示例题干","options":[{"key":"A","text":"选项1"},{"key":"B","text":"选项2"}],"standard_answer":"A","analysis":"示例解析【解析由glm4.6生成】"}]'
)


def _strip_code_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.lstrip("`")
        if "\n" in cleaned:
            cleaned = cleaned.split("\n", 1)[1]
    if cleaned.endswith("```"):
        cleaned = cleaned[: cleaned.rfind("```")].strip()
    return cleaned


def _extract_json_array(text: str) -> list | None:
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


_QUOTE_BETWEEN_CHARS = re.compile(r'(?<![:{\[,])"(?!\s*[:\]\},])')


def _sanitize_jsonish(text: str) -> str:
    """Best-effort fix for unescaped quotes inside values (e.g., 关键词"三同时")."""
    collapsed = " ".join(text.split())  # remove newlines that may break parsing
    return _QUOTE_BETWEEN_CHARS.sub("”", collapsed)


async def parse_chunk_with_zai(chunk_text: str, bank_id: int, model: str, retries: int) -> List[QuestionCreate]:
    if not settings.zai_api_key:
        raise RuntimeError("ZAI_API_KEY 未配置 (.env)")

    client = AsyncOpenAI(api_key=settings.zai_api_key, base_url=settings.zai_api_base)
    last_exc: Exception | None = None
    last_raw: str | None = None
    last_input: str | None = None
    def _content_filtered(exc: Exception) -> bool:
        msg = str(exc)
        return "contentFilter" in msg or "'code': '1301'" in msg or "1301" in msg
    for attempt in range(1, retries + 1):
        try:
            last_input = chunk_text
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": TEXT_PROMPT},
                    {"role": "user", "content": f"原始文本：\n{chunk_text}"},
                ],
                temperature=0.2,
                max_tokens=4096,
                extra_body={"thinking": {"type": "disabled"}},
            )
            content = response.choices[0].message.content if response.choices else ""
            last_raw = content or ""
            if not content:
                raise RuntimeError("ZAI 返回为空")
            cleaned = _strip_code_fence(content)
            try:
                payload = json.loads(cleaned)
            except json.JSONDecodeError:
                sanitized = _sanitize_jsonish(cleaned)
                try:
                    payload = json.loads(sanitized)
                except json.JSONDecodeError:
                    payload = _extract_json_array(sanitized)
                if payload is None:
                    raise
            questions: List[QuestionCreate] = []
            if isinstance(payload, list):
                for item in payload:
                    if isinstance(item, dict):
                        qc = normalize_question_dict(item, bank_id)
                        if qc:
                            questions.append(qc)
            if not questions:
                raise RuntimeError(f"ZAI 未生成题目，raw={cleaned}")
            return questions
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if _content_filtered(exc):
                logger.error("ZAI 内容审核拦截，跳过该分块: %s | input=%s", exc, last_input)
                break
            logger.warning(
                "ZAI parse failed (attempt %s/%s): %s | input=%s | raw=%s",
                attempt,
                retries,
                exc,
                last_input,
                last_raw,
            )
            if attempt < retries:
                await asyncio.sleep(1.5 * attempt)
    raise RuntimeError(f"ZAI 调用连续失败: {last_exc} | input={last_input} | raw={last_raw}") from last_exc


def import_questions(session: Session, importer: BatchImportService, questions: List[QuestionCreate]) -> dict:
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


async def _parse_chunk_task(
    sem: asyncio.Semaphore,
    idx: int,
    record: dict,
    bank_id: int,
    ai_model: str,
    retries: int,
) -> tuple[int, List[QuestionCreate] | None, Exception | None]:
    async with sem:
        chunk_text = str(record.get("text") or "").strip()
        if not chunk_text:
            return idx, [], None
        try:
            questions = await parse_chunk_with_zai(chunk_text, bank_id, model=ai_model, retries=retries)
            return idx, questions, None
        except Exception as exc:  # noqa: BLE001
            return idx, None, exc


async def process_file(session: Session, path: Path, ai_model: str, retries: int, concurrency: int) -> None:
    bank_title = derive_bank_title(path)
    bank = ensure_bank(session, bank_title)
    importer = BatchImportService(session=session, ai=None)
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
        stats = import_questions(session, importer, questions)
        imported_total += stats["imported"]
        duplicate_total += stats["duplicates"]
    elif path.suffix == ".jsonl":
        logger.info("Processing chunked file (ZAI AI, concurrency=%s): %s", concurrency, path.name)
        with path.open("r", encoding="utf-8") as fh:
            lines = [json.loads(line) for line in fh if line.strip()]
        sem = asyncio.Semaphore(max(1, concurrency))
        tasks = [
            _parse_chunk_task(sem, idx, record, bank.id, ai_model=ai_model, retries=retries)
            for idx, record in enumerate(lines, start=1)
        ]
        results = await asyncio.gather(*tasks)
        fail_streak = 0
        for idx, questions, error in sorted(results, key=lambda x: x[0]):
            if error:
                ai_failed_chunks += 1
                logger.error("Chunk %s failed after retries: %s", idx, error)
                fail_streak += 1
                if fail_streak >= 5:
                    logger.error("连续5个分块失败，终止导入。未完成文件: %s", path)
                    raise RuntimeError(f"连续5个分块失败，终止导入。未完成文件: {path}")
                continue
            fail_streak = 0
            if not questions:
                continue
            stats = import_questions(session, importer, questions)
            imported_total += stats["imported"]
            duplicate_total += stats["duplicates"]
            logger.info("Chunk %s imported: +%s (duplicates %s)", idx, stats["imported"], stats["duplicates"])
    logger.info(
        "File done: %s (bank=%s) imported=%s duplicates=%s ai_failed_chunks=%s",
        path.name,
        bank_title,
        imported_total,
        duplicate_total,
        ai_failed_chunks,
    )
    # move processed file to ../done
    done_dir = path.parent.parent / "done"
    done_dir.mkdir(parents=True, exist_ok=True)
    try:
        target = done_dir / path.name
        path.rename(target)
        logger.info("Moved processed file to %s", target)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to move %s to done folder: %s", path, exc)


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

    ai_model = args.model or settings.zai_model or "gpt-4o-mini"

    with Session(engine) as session:
        for path in files:
            try:
                await process_file(
                    session,
                    path,
                    ai_model=ai_model,
                    retries=args.retries,
                    concurrency=args.concurrency,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to import %s: %s", path.name, exc)
    logger.info("All done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

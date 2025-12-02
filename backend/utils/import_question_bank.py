#!/usr/bin/env python3
"""按批量导入处理好的题库，自动在 Gemini / OpenAI 兼容模型间切换。

用法示例：
  python backend/utils/import_question_bank.py \
    --input backend/processed_question_bank \
    --ai-model gemini-2.5-flash \
    --concurrency 3 --retries 3 --limit 1

    uv run python utils/import_question_bank.py --input processed_question_bank --ai-model gemini-2.5-flash --concurrency 4 --retries 5 --limit 1

参数说明：
  --input/-i        待导入文件目录（默认 processed_question_bank）
  --limit           最多处理的文件数（便于快速测试）
  --ai-model        AI 模型名；包含 "gemini" 时走 Gemini generateContent（GEMINI_API_KEY/GEMINI_KEY），
                    其他模型使用 OpenAI 兼容 chat completions（ZAI_API_KEY，ZAI_API_BASE）
  --concurrency     解析 *.chunks.jsonl 时的并发请求数（默认 3）
  --retries         单个分块解析失败的重试次数（默认 3）
  --api-key         覆盖环境变量提供的 API Key（Gemini 或 OpenAI 兼容均可）
  --base-url        覆盖默认的 API Base（Gemini/OpenAI 兼容均可）

支持的输入（由 question_bank_tool.py 生成）：
  *.converted.json  已结构化，直接入库
  *.chunks.jsonl    原始文本分块，需 AI 解析，支持并发

每个文件会创建/复用以文件名为标题的题库，并附加所用模型标记（如“消防安全题库 (gemini-2.5-flash)”）。
处理完成的文件会移动到 backend/done，避免重复导入。
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
from openai import AsyncOpenAI
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
        help="Model for AI parsing text chunks. Gemini models use Gemini API; others use OpenAI-compatible API.",
    )
    parser.add_argument("--retries", type=int, default=3, help="Max retries per chunk when AI parsing fails.")
    parser.add_argument("--concurrency", type=int, default=3, help="Concurrent AI parse requests for chunks.")
    parser.add_argument("--api-key", default=None, help="Override API key (Gemini or OpenAI-compatible).")
    parser.add_argument("--base-url", default=None, help="Override API base url.")
    return parser.parse_args()


def iter_processed_files(folder: Path) -> Iterable[Path]:
    for path in sorted(folder.glob("*.converted.json")):
        yield path
    for path in sorted(folder.glob("*.chunks.jsonl")):
        yield path


def derive_bank_title(path: Path, ai_model: str | None = None) -> str:
    stem = path.name
    for suffix in (".converted.json", ".chunks.jsonl", ".json", ".jsonl"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    stem = re.sub(r"[_\\s]+", " ", stem).strip()
    title = stem or "题库"
    if ai_model:
        model_tag = re.sub(r"\s+", " ", ai_model).strip()
        if model_tag:
            title = f"{title} ({model_tag})"
    return title


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
    "你是一名教育测评数据标注助手。请从下面的原始试题文本中提取结构化题目，并进行轻量纠错。\n"
    "要求：\n"
    "1) 输出必须是 JSON 数组，禁止返回代码块或其他文字。\n"
    '2) 字段：type( choice_single | choice_multi | choice_judgment | short_answer ), '
    "content, options(数组，含 key 与 text)，standard_answer，analysis(可空字符串)。\n"
    "3) 判断题 type=choice_judgment，选项仅 A=正确、B=错误，standard_answer 填 A 或 B。\n"
    "4) 若原文选项中某个选项用 <ANS>…</ANS> 标记、含“√”、或在题干中指明答案，需正确识别。多个正确答案使用逗号分隔。\n"
    "5) 如果未明确给出答案，standard_answer 留空字符串。\n"
    "6) 保持题干与选项文字原样（去掉多余空白即可），不要虚构内容。\n"
    "示例输出：[{'type':'choice_single','content':'示例题干','options':[{'key':'A','text':'选项1'}],'standard_answer':'A','analysis':'示例解析'}]"
)


def _is_gemini_model(model: str) -> bool:
    return "gemini" in model.lower()


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
    """Best-effort fix for unescaped quotes inside values."""
    collapsed = " ".join(text.split())
    return _QUOTE_BETWEEN_CHARS.sub("”", collapsed)


def _repair_jsonish_array(text: str) -> list | None:
    """Attempt to auto-close brackets/braces and drop trailing commas."""
    if "[" not in text:
        return None
    candidate = text[text.find("[") :]
    candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
    stack: list[str] = []
    repaired_chars: list[str] = []
    for ch in candidate:
        if ch in "[{":
            stack.append(ch)
            repaired_chars.append(ch)
        elif ch in "]}":
            if stack and ((stack[-1] == "[" and ch == "]") or (stack[-1] == "{" and ch == "}")):
                stack.pop()
                repaired_chars.append(ch)
            else:
                continue
        else:
            repaired_chars.append(ch)
    for open_ch in reversed(stack):
        repaired_chars.append("]" if open_ch == "[" else "}")
    fixed = "".join(repaired_chars)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        return None


async def _call_gemini_text(prompt: str, text: str, model: str, api_key: str | None = None, base_url: str | None = None) -> str:
    key = api_key or settings.gemini_api_key
    if not key:
        raise AIServiceError("Gemini API key 未配置 (.env 中设置 GEMINI_API_KEY)")
    url_base = (base_url or settings.gemini_api_base).rstrip("/")
    url = f"{url_base}/v1beta/models/{model}:generateContent?key={key}"
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


async def _call_openai_chat(
    prompt: str,
    text: str,
    model: str,
    api_key: str | None = None,
    base_url: str | None = None,
) -> str:
    key = api_key or settings.zai_api_key
    if not key:
        raise AIServiceError("OpenAI/ZAI API key 未配置 (.env 中设置 ZAI_API_KEY)")
    base = base_url or settings.zai_api_base or "https://api.openai.com/v1"
    client = AsyncOpenAI(api_key=key, base_url=base)
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": TEXT_PROMPT},
            {"role": "user", "content": f"原始文本：\n{text}"},
        ],
        temperature=0.2,
        max_tokens=8192,
        extra_body={"thinking": {"type": "disabled"}},
    )
    if not response.choices:
        raise AIServiceError("AI 返回为空")
    return response.choices[0].message.content or ""


async def parse_chunk_with_ai(
    chunk_text: str,
    bank_id: int,
    model: str,
    retries: int,
    api_key: str | None = None,
    base_url: str | None = None,
) -> List[QuestionCreate]:
    last_exc: Exception | None = None
    last_raw: str | None = None
    provider = "gemini" if _is_gemini_model(model) else "openai"

    def _content_filtered(exc: Exception) -> bool:
        msg = str(exc)
        return "contentFilter" in msg or "1301" in msg

    for attempt in range(1, retries + 1):
        try:
            raw_text = (
                await _call_gemini_text(TEXT_PROMPT, chunk_text, model=model, api_key=api_key, base_url=base_url)
                if provider == "gemini"
                else await _call_openai_chat(TEXT_PROMPT, chunk_text, model=model, api_key=api_key, base_url=base_url)
            )
            last_raw = raw_text or ""
            cleaned = _strip_code_fence(raw_text or "")
            try:
                payload = json.loads(cleaned)
            except json.JSONDecodeError:
                sanitized = _sanitize_jsonish(cleaned)
                try:
                    payload = json.loads(sanitized)
                except json.JSONDecodeError:
                    payload = _extract_json_array(sanitized) or _repair_jsonish_array(sanitized)
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
                raise AIServiceError("AI 未生成题目")
            return questions
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if _content_filtered(exc):
                logger.error("AI 内容审核拦截，跳过该分块: %s | input=%s", exc, chunk_text)
                break
            logger.warning(
                "AI parse failed (attempt %s/%s): %s | raw=%s",
                attempt,
                retries,
                exc,
                last_raw,
            )
            if attempt < retries:
                await asyncio.sleep(1.5 * attempt)
    raise AIServiceError(f"AI 调用连续失败: {last_exc} | raw={last_raw}") from last_exc


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


async def _parse_chunk_task(
    sem: asyncio.Semaphore,
    idx: int,
    record: dict,
    bank_id: int,
    ai_model: str,
    retries: int,
    api_key: str | None,
    base_url: str | None,
) -> tuple[int, List[QuestionCreate] | None, Exception | None]:
    async with sem:
        chunk_text = str(record.get("text") or "").strip()
        if not chunk_text:
            return idx, [], None
        try:
            questions = await parse_chunk_with_ai(
                chunk_text,
                bank_id,
                model=ai_model,
                retries=retries,
                api_key=api_key,
                base_url=base_url,
            )
            return idx, questions, None
        except Exception as exc:  # noqa: BLE001
            return idx, None, exc


async def process_file(
    session: Session,
    path: Path,
    ai_model: str,
    retries: int,
    concurrency: int,
    api_key: str | None,
    base_url: str | None,
) -> None:
    bank_title = derive_bank_title(path, ai_model=ai_model)
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
        logger.info("Processing chunked file (AI, concurrency=%s): %s", concurrency, path.name)
        with path.open("r", encoding="utf-8") as fh:
            lines = [json.loads(line) for line in fh if line.strip()]
        sem = asyncio.Semaphore(max(1, concurrency))
        tasks = [
            _parse_chunk_task(
                sem,
                idx,
                record,
                bank.id,
                ai_model=ai_model,
                retries=retries,
                api_key=api_key,
                base_url=base_url,
            )
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
            stats = import_questions(session, importer, bank, questions)
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

    ai_model = args.ai_model or settings.gemini_model or settings.zai_model or "gemini-2.5-flash"

    with Session(engine) as session:
        for path in files:
            try:
                await process_file(
                    session,
                    path,
                    ai_model=ai_model,
                    retries=args.retries,
                    concurrency=args.concurrency,
                    api_key=args.api_key,
                    base_url=args.base_url,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to import %s: %s", path.name, exc)
    logger.info("All done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

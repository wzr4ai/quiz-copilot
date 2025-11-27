from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Iterable, List

from sqlmodel import Session, select

from app.models.schemas import (
    BatchImportFileResult,
    BatchImportResponse,
    BatchImportRequest,
    QuestionCreate,
)
from app.services.ai_service import AIService, AIServiceError
from app.services.ai_stub import generate_questions_from_text
from app.models.db_models import Question as QuestionDB


SUPPORTED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp"}
SUPPORTED_TEXT_EXT = {".txt", ".md"}


class BatchImportService:
    def __init__(self, session: Session, ai: AIService) -> None:
        self.session = session
        self.ai = ai

    async def import_directory(self, request: BatchImportRequest) -> BatchImportResponse:
        directory = Path(request.directory).expanduser().resolve()
        if not directory.exists() or not directory.is_dir():
            raise ValueError("目录不存在或不可访问")

        files = list(self._iter_files(directory, recursive=request.recursive))
        file_results: List[BatchImportFileResult] = []
        imported_total = 0
        duplicate_total = 0
        failed_files = 0

        for file_path in files:
            result = BatchImportFileResult(filename=str(file_path))
            try:
                questions = await self._process_file(file_path, request.bank_id)
            except Exception as exc:  # noqa: BLE001
                result.errors.append(str(exc))
                failed_files += 1
                file_results.append(result)
                continue

            if not questions:
                result.errors.append("未能解析出题目，可能内容已截断或无法识别")
                failed_files += 1
                file_results.append(result)
                continue

            for q in questions:
                warnings = self._validate_question(q)
                if warnings:
                    result.warnings.extend(warnings)
                existing = self._find_duplicate(q)
                if existing:
                    result.duplicates += 1
                    duplicate_total += 1
                else:
                    created = QuestionDB(
                        bank_id=q.bank_id,
                        type=q.type,
                        content=q.content,
                        options=[opt.model_dump() for opt in q.options],
                        standard_answer=q.standard_answer,
                        analysis=q.analysis,
                    )
                    self.session.add(created)
                    self.session.commit()
                    self.session.refresh(created)
                    result.imported += 1
                    imported_total += 1

            file_results.append(result)

        return BatchImportResponse(
            total_files=len(files),
            processed_files=len(file_results),
            imported_questions=imported_total,
            duplicate_questions=duplicate_total,
            failed_files=failed_files,
            file_results=file_results,
        )

    async def _process_file(self, path: Path, bank_id: int) -> List[QuestionCreate]:
        suffix = path.suffix.lower()
        if suffix in SUPPORTED_IMAGE_EXT:
            image_base64 = self._read_image_base64(path)
            try:
                return await self.ai.generate_questions_from_image(image_base64, bank_id)
            except AIServiceError as exc:
                raise RuntimeError(f"图片识别失败: {exc}")
        if suffix in SUPPORTED_TEXT_EXT:
            text = path.read_text(encoding="utf-8", errors="ignore")
            return generate_questions_from_text(text, bank_id)
        raise RuntimeError("不支持的文件类型")

    def _iter_files(self, directory: Path, recursive: bool) -> Iterable[Path]:
        if recursive:
            for root, _, filenames in os.walk(directory):
                for name in filenames:
                    yield Path(root) / name
        else:
            for entry in directory.iterdir():
                if entry.is_file():
                    yield entry

    def _read_image_base64(self, path: Path) -> str:
        data = path.read_bytes()
        return base64.b64encode(data).decode("utf-8")

    def _validate_question(self, question: QuestionCreate) -> List[str]:
        warnings: List[str] = []
        content = question.content.strip()
        if len(content) < 6 or content.endswith("..."):
            warnings.append("题干可能被截断，请人工核对")

        if question.type in {"choice_single", "choice_multi"}:
            option_keys = [opt.key for opt in question.options]
            if len(question.options) < 2:
                warnings.append("选项少于2个，可能识别不完整")
            answers = [a.strip() for a in question.standard_answer.split(",") if a.strip()]
            if not answers:
                warnings.append("未识别到标准答案")
            else:
                missing = [ans for ans in answers if ans not in option_keys]
                if missing:
                    warnings.append("标准答案不在选项中，可能识别不清")
        else:
            if len(question.standard_answer.strip()) < 1:
                warnings.append("简答题答案缺失或过短")

        return warnings


    def _find_duplicate(self, payload: QuestionCreate) -> QuestionDB | None:
        candidate = (
            self.session.exec(
                select(QuestionDB).where(
                    QuestionDB.bank_id == payload.bank_id,
                    QuestionDB.type == payload.type,
                    QuestionDB.content == payload.content,
                )
            ).first()
        )
        if not candidate:
            return None
        if payload.type in {"choice_single", "choice_multi"}:
            if candidate.standard_answer.strip().lower() != payload.standard_answer.strip().lower():
                return None
            if len(candidate.options or []) != len(payload.options or []):
                return None
            opts_match = all(
                co.get("key") == po.key and (co.get("text") or "").strip() == po.text.strip()
                for co, po in zip(candidate.options or [], payload.options or [])
            )
            return candidate if opts_match else None
        if payload.type == "short_answer":
            if candidate.standard_answer.strip().lower() == payload.standard_answer.strip().lower():
                return candidate
        return None

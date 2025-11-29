#!/usr/bin/env python3
"""Question bank helper.

This script normalizes the mixed source files under ``Question_Bank_File`` into
two outputs:
1) Structured questions (JSON) when the source already contains clear
   question/option/answer字段（如题库 JSON）并可直接用于后端的
   ``QuestionCreate`` 结构。
2) 文本分块（JSONL，一块一行）用于调用大模型做 OCR/解析时保持题目不被截断。
   分块时尝试识别题号/题干开头，避免在题目中间切断；若文档用加粗/着色标出
   正确答案，会在文本中用 ``<ANS>...<\\/ANS>`` 标记保留下来。

Usage
-----
python utils/question_bank_tool.py \
  --input Question_Bank_File \
  --output processed_question_bank \
  --bank-id 1

Outputs
-------
- <stem>.converted.json : 标准化后的题目列表，可直接作为批量导入/人工校对输入。
- <stem>.chunks.jsonl    : 每行一个 JSON 对象，字段 ``text`` 是切好的片段，
                          ``source`` 是原文件，便于送入 AI 模型。

Dependencies
------------
python-docx (docx 解析), pdfplumber (pdf 解析). 处理 .doc 时如安装了 textract 也会自动使用；
否则会提示先转换为 docx/pdf。
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

logger = logging.getLogger("question_bank_tool")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

try:
    from docx import Document
except Exception:  # pragma: no cover - optional dependency
    Document = None

try:
    import pdfplumber
except Exception:  # pragma: no cover - optional dependency
    pdfplumber = None


QUESTION_START_PATTERNS = [
    re.compile(r"^\s*\d{1,3}[\.、．)]"),
    re.compile(r"^\s*[（(]\d{1,3}[）)]"),
    re.compile(r"^\s*第?\d{1,3}题"),
    re.compile(r"^\s*[一二三四五六七八九十]+、"),
    re.compile(r"^\s*单选题|^\s*多选题|^\s*判断题"),
]

OPTION_PATTERNS = [
    re.compile(r"^\s*[A-HＡ-Ｈ][\.、．)]"),
    re.compile(r"^\s*答案[:：]"),
]

HEADING_PATTERNS = [
    re.compile(r"^\s*单选题"),
    re.compile(r"^\s*单项选择题"),
    re.compile(r"^\s*多选题"),
    re.compile(r"^\s*多项选择题"),
    re.compile(r"^\s*判断题"),
    re.compile(r"^\s*填空题"),
]

ANSWER_MARKERS = re.compile(r"(正确答案[:：]?|答案[:：])")
MD_MARKERS = [
    ("**", ""),
    ("__", ""),
    ("```", ""),
    ("`", ""),
    ("#", ""),
]


def strip_ans_markers(text: str) -> str:
    return text.replace("<ANS>", "").replace("</ANS>", "")


def strip_md(text: str) -> str:
    cleaned = text
    for marker, repl in MD_MARKERS:
        cleaned = cleaned.replace(marker, repl)
    return cleaned


@dataclass
class ProcessedFile:
    source: Path
    structured_questions: list[dict]
    chunks: list[str]
    note: Optional[str] = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize question bank sources.")
    parser.add_argument("--input", "-i", required=True, help="File or directory to process.")
    parser.add_argument("--output", "-o", default="processed_question_bank", help="Output directory.")
    parser.add_argument("--bank-id", type=int, default=None, help="Optional bank id to include in normalized JSON.")
    parser.add_argument("--chunk-size", type=int, default=1400, help="Max chars per chunk for AI OCR/text calls.")
    parser.add_argument("--min-chunk", type=int, default=300, help="Minimum chars before we allow a split.")
    return parser.parse_args()


def looks_like_question_start(line: str) -> bool:
    if any(pat.match(line) for pat in OPTION_PATTERNS):
        return False
    return any(pat.match(line) for pat in QUESTION_START_PATTERNS)


def extract_question_number(line: str) -> Optional[int]:
    """Extract leading Arabic question number if present."""
    match = re.match(r"^\s*[（(]?(\d{1,3})[）).、．]?", line)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def _strip_soft_spaces(text: str) -> str:
    return " ".join(text.replace("\u3000", " ").split())


def merge_paragraph_runs(paragraph) -> str:
    """Return paragraph text; ignore inline highlighting markers."""
    parts: List[str] = []
    for run in getattr(paragraph, "runs", []):
        if not run.text:
            continue
        escaped = strip_md(strip_ans_markers(run.text))
        parts.append(escaped)
    text = "".join(parts) if parts else paragraph.text
    return _strip_soft_spaces(strip_md(strip_ans_markers(text)))


def extract_docx(path: Path) -> list[str]:
    if Document:
        doc = Document(path)
        lines = []
        for para in doc.paragraphs:
            text = merge_paragraph_runs(para)
            if text.strip():
                lines.append(strip_md(strip_ans_markers(text.strip())))
        return lines
    # Fallback: simple XML extraction without formatting
    import zipfile
    import xml.etree.ElementTree as ET

    lines: list[str] = []
    with zipfile.ZipFile(path) as zf:
        with zf.open("word/document.xml") as doc_xml:
            tree = ET.parse(doc_xml)
            root = tree.getroot()
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            for para in root.findall(".//w:p", ns):
                texts = []
                for run in para.findall(".//w:t", ns):
                    if run.text:
                        texts.append(run.text)
                paragraph_text = _strip_soft_spaces(strip_md(strip_ans_markers("".join(texts))))
                if paragraph_text:
                    lines.append(paragraph_text)
    if not lines:
        raise RuntimeError("无法解析 docx 文件内容")
    return lines


def extract_pdf(path: Path) -> list[str]:
    if not pdfplumber:
        raise RuntimeError("pdfplumber 未安装，无法解析 pdf 文件")
    lines: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            content = page.extract_text() or ""
            for raw in content.splitlines():
                txt = _strip_soft_spaces(strip_md(raw))
                if txt:
                    lines.append(strip_ans_markers(txt))
    return lines


def extract_doc(path: Path) -> list[str]:
    try:
        import textract  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("处理 .doc 需要安装 textract，或先将文件转换为 docx/pdf") from exc
    text = textract.process(str(path)).decode("utf-8", errors="ignore")
    lines = []
    for raw in text.splitlines():
        txt = _strip_soft_spaces(strip_md(strip_ans_markers(raw)))
        if txt:
            lines.append(txt)
    return lines


def split_into_chunks(lines: list[str], max_chars: int, min_chunk: int) -> list[str]:
    """Simple splitter: new chunk on question-like starts; enforce max size; strip markdown."""
    chunks: list[str] = []
    current: list[str] = []

    for line in lines:
        line = strip_md(strip_ans_markers(line))
        if looks_like_question_start(line) and current:
            candidate = "\n".join(current)
            if len(candidate) >= min_chunk:
                chunks.append(candidate.strip())
                current = [line]
                continue
        if current and len("\n".join(current + [line])) > max_chars:
            chunks.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)

    if current:
        chunks.append("\n".join(current).strip())
    return chunks


def normalize_questions_from_json(raw: object, bank_id: Optional[int]) -> list[dict]:
    """Convert JSON question bank structures to the backend QuestionCreate payload shape."""
    def _convert_one(item: dict, fallback_type: str) -> dict:
        options_raw = item.get("选项") or item.get("options") or {}
        options = [{"key": k.strip(), "text": str(v).strip()} for k, v in options_raw.items()]
        answer = item.get("答案") or item.get("answer") or item.get("standard_answer") or ""
        if isinstance(answer, list):
            answer = ",".join(str(a).strip() for a in answer)
        qtype = item.get("type") or fallback_type
        return {
            "bank_id": bank_id,
            "type": qtype,
            "content": item.get("问题") or item.get("question") or item.get("content") or "",
            "options": options,
            "standard_answer": str(answer).strip(),
            "analysis": item.get("解析") or item.get("analysis"),
        }

    questions: list[dict] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                questions.append(_convert_one(item, "choice_single"))
        return [q for q in questions if q["content"]]

    if isinstance(raw, dict):
        for section, items in raw.items():
            if not isinstance(items, list):
                continue
            qtype = "choice_multi" if "多选" in str(section) else "choice_single"
            for item in items:
                if isinstance(item, dict):
                    questions.append(_convert_one(item, qtype))
    return [q for q in questions if q["content"]]


def read_and_process_file(path: Path, bank_id: Optional[int], max_chars: int, min_chunk: int) -> ProcessedFile:
    suffix = path.suffix.lower()
    structured: list[dict] = []
    chunks: list[str] = []
    note: Optional[str] = None

    if suffix == ".json":
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise RuntimeError(f"无法解析 JSON: {exc}") from exc
        structured = normalize_questions_from_json(raw, bank_id)
        if not structured:
            note = "JSON 里没有识别到题目结构"
    elif suffix == ".docx":
        lines = extract_docx(path)
        chunks = split_into_chunks(lines, max_chars=max_chars, min_chunk=min_chunk)
    elif suffix == ".pdf":
        lines = extract_pdf(path)
        chunks = split_into_chunks(lines, max_chars=max_chars, min_chunk=min_chunk)
    elif suffix == ".doc":
        lines = extract_doc(path)
        chunks = split_into_chunks(lines, max_chars=max_chars, min_chunk=min_chunk)
    else:
        text = path.read_text(encoding="utf-8", errors="ignore")
        lines = []
        for x in text.splitlines():
            cleaned = _strip_soft_spaces(strip_ans_markers(x))
            if cleaned:
                lines.append(cleaned)
        chunks = split_into_chunks(lines, max_chars=max_chars, min_chunk=min_chunk)

    return ProcessedFile(source=path, structured_questions=structured, chunks=chunks, note=note)


def iter_files(input_path: Path) -> Iterable[Path]:
    if input_path.is_file():
        yield input_path
        return
    for file in input_path.glob("**/*"):
        if file.is_file():
            yield file


def write_outputs(result: ProcessedFile, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = result.source.stem
    if result.structured_questions:
        converted_path = output_dir / f"{stem}.converted.json"
        converted_path.write_text(json.dumps(result.structured_questions, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Structured questions written: %s (%s items)", converted_path, len(result.structured_questions))
    if result.chunks:
        chunk_path = output_dir / f"{stem}.chunks.jsonl"
        with chunk_path.open("w", encoding="utf-8") as fh:
            for idx, chunk in enumerate(result.chunks, start=1):
                record = {"chunk_id": idx, "source": str(result.source), "text": chunk}
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        logger.info("Chunks written: %s (%s blocks)", chunk_path, len(result.chunks))
    if not result.structured_questions and not result.chunks:
        logger.warning("No output generated for %s", result.source)
    if result.note:
        logger.warning("Note for %s: %s", result.source, result.note)


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()
    if not input_path.exists():
        logger.error("Input path does not exist: %s", input_path)
        return 1

    files = list(iter_files(input_path))
    if not files:
        logger.error("No files found under %s", input_path)
        return 1

    logger.info("Processing %s files from %s", len(files), input_path)
    for file in files:
        try:
            result = read_and_process_file(
                path=file,
                bank_id=args.bank_id,
                max_chars=args.chunk_size,
                min_chunk=args.min_chunk,
            )
            write_outputs(result, output_dir=output_dir)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to process %s: %s", file, exc)
    logger.info("Done. Outputs stored in %s", output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())

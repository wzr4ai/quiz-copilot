#!/usr/bin/env python3
"""Analyze raw question bank documents to inform splitting heuristics."""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from question_bank_tool import (
    HEADING_PATTERNS,
    OPTION_PATTERNS,
    extract_doc,
    extract_docx,
    extract_pdf,
    extract_question_number,
    _strip_soft_spaces,
)

logger = logging.getLogger("analyze_question_banks")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


@dataclass
class FileStats:
    name: str
    kind: str
    lines: int
    heading_hits: Counter
    number_seq_quality: str
    number_resets: int
    avg_line_len: float
    max_line_len: int
    option_lines: int
    sample_lines: list[str]


def iter_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    for path in sorted(root.glob("**/*")):
        if path.is_file():
            yield path


def read_lines(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        try:
            return extract_docx(path)
        except Exception as exc:  # pragma: no cover - dependency missing
            logger.warning("Skip docx: %s (%s)", path.name, exc)
            return []
    if suffix == ".pdf":
        try:
            return extract_pdf(path)
        except Exception as exc:  # pragma: no cover - dependency missing
            logger.warning("Skip pdf: %s (%s)", path.name, exc)
            return []
    if suffix == ".doc":
        try:
            return extract_doc(path)
        except Exception as exc:  # pragma: no cover - dependency missing
            logger.warning("Skip doc: %s (%s)", path.name, exc)
            return []
    if suffix == ".json":
        text = path.read_text(encoding="utf-8", errors="ignore")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return [_strip_soft_spaces(line) for line in text.splitlines() if _strip_soft_spaces(line)]
        # flatten json questions for a quick look
        lines: list[str] = []
        if isinstance(data, dict):
            for section, items in data.items():
                lines.append(f"## {section}")
                if isinstance(items, list):
                    for item in items[:5]:
                        if isinstance(item, dict):
                            q = item.get("问题") or item.get("question") or item.get("content")
                            if q:
                                lines.append(str(q))
        elif isinstance(data, list):
            for item in data[:10]:
                if isinstance(item, dict):
                    q = item.get("问题") or item.get("question") or item.get("content")
                    if q:
                        lines.append(str(q))
        return lines
    text = path.read_text(encoding="utf-8", errors="ignore")
    return [_strip_soft_spaces(line) for line in text.splitlines() if _strip_soft_spaces(line)]


def analyze_numbers(lines: list[str]) -> tuple[str, int]:
    nums = [n for n in (extract_question_number(l) for l in lines) if n is not None]
    if not nums:
        return "none", 0
    resets = 0
    prev: Optional[int] = None
    for n in nums:
        if prev is not None and n == 1 and prev > 5:
            resets += 1
        prev = n
    if resets > 3:
        quality = "frequent resets"
    elif resets > 0:
        quality = "resets present"
    else:
        quality = "mostly sequential"
    return quality, resets


def analyze_file(path: Path) -> FileStats:
    lines = read_lines(path)
    heading_hits = Counter()
    for line in lines:
        for pat in HEADING_PATTERNS:
            if pat.match(line):
                heading_hits[pat.pattern] += 1
    option_lines = sum(1 for l in lines if any(p.match(l) for p in OPTION_PATTERNS))
    quality, resets = analyze_numbers(lines)
    lengths = [len(l) for l in lines] or [0]
    return FileStats(
        name=path.name,
        kind=path.suffix.lower() or "txt",
        lines=len(lines),
        heading_hits=heading_hits,
        number_seq_quality=quality,
        number_resets=resets,
        avg_line_len=sum(lengths) / len(lengths),
        max_line_len=max(lengths),
        option_lines=option_lines,
        sample_lines=lines[:8],
    )


def write_report(stats: list[FileStats], output: Path) -> None:
    total_files = len(stats)
    with output.open("w", encoding="utf-8") as fh:
        fh.write("# Question Bank File Analysis\n\n")
        fh.write(f"Analyzed {total_files} files.\n\n")
        fh.write("## Summary Heuristics\n")
        fh.write("- Most files contain numeric prefixes; several reset to 1 at section boundaries.\n")
        fh.write("- Headings like 单选题/多选题/判断题 appear and can be used as hard splits.\n")
        fh.write("- Option lines (A/B/C) are common; avoid treating them as question starts.\n")
        fh.write("- Some lines are long (max length recorded below); respect max_chars to prevent overruns.\n\n")
        fh.write("## Per-file Details\n")
        for item in stats:
            fh.write(f"### {item.name}\n")
            fh.write(f"- Type: `{item.kind}`\n")
            fh.write(f"- Lines: {item.lines}, avg len: {item.avg_line_len:.1f}, max len: {item.max_line_len}\n")
            fh.write(f"- Numbering: {item.number_seq_quality} (resets={item.number_resets})\n")
            fh.write(f"- Headings: {dict(item.heading_hits)}\n")
            fh.write(f"- Option-like lines: {item.option_lines}\n")
            fh.write("- Sample lines:\n")
            for line in item.sample_lines:
                fh.write(f"  - {line}\n")
            fh.write("\n")
    logger.info("Report written to %s", output)


def main() -> int:
    root = Path(__file__).resolve().parents[1] / "Question_Bank_File"
    if not root.exists():
        logger.error("Question_Bank_File not found at %s", root)
        return 1
    stats = [analyze_file(path) for path in iter_files(root)]
    output = Path(__file__).resolve().parents[2] / "docs" / "question_bank_analysis.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    write_report(stats, output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

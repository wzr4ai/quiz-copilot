#!/usr/bin/env python3
"""Fill missing/empty analyses in converted question banks using ZAI (glm-4.5).

For each `*.converted.json` under the given directory, questions with blank
analysis will be sent to glm-4.5 to generate a short rationale. If the answer
is obvious, the model should return `"显而易见 by glm-4.5"`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger("fill_missing_analysis")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


SYSTEM_PROMPT = (
    "你是一名命题解析助手。对于给定的题目、选项和标准答案，判断解析是否需要补充：\n"
    "1) 如果答案从题干或选项中显而易见（无需再解释），返回：{\"analysis\": \"显而易见 by glm-4.5\"}。\n"
    "2) 否则给出一句话解析，简洁说明答案依据，末尾标注 \"by glm-4.5\"。\n"
    "只输出 JSON 对象，不要输出多余内容或代码块。"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fill missing analyses using glm-4.5 (ZAI).")
    parser.add_argument("--input", "-i", default="processed_question_bank", help="Directory containing *.converted.json.")
    parser.add_argument("--model", default=None, help="Model name, default uses ZAI_MODEL or glm-4.5.")
    parser.add_argument("--limit", type=int, default=None, help="Max questions to process (for quick tests).")
    parser.add_argument("--concurrency", type=int, default=3, help="Concurrent requests to ZAI.")
    return parser.parse_args()


def iter_converted_files(folder: Path) -> list[Path]:
    return sorted(folder.glob("*.converted.json"))


def needs_analysis(q: Dict[str, Any]) -> bool:
    analysis = (q.get("analysis") or "").strip()
    return len(analysis) == 0


def build_user_prompt(q: Dict[str, Any]) -> str:
    content = q.get("content") or ""
    opts = q.get("options") or []
    answer = q.get("standard_answer") or q.get("答案") or ""
    lines = [f"题干: {content}", f"答案: {answer}"]
    if isinstance(opts, list) and opts:
        opt_lines = [f"{opt.get('key')}: {opt.get('text')}" for opt in opts if isinstance(opt, dict)]
        lines.append("选项:\n" + "\n".join(opt_lines))
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
    q: Dict[str, Any],
    idx: int,
) -> tuple[int, str | None, Exception | None]:
    async with sem:
        try:
            prompt = build_user_prompt(q)
            raw = await call_zai(prompt, client, model)
            data = json.loads(raw)
            analysis = str(data.get("analysis") or "").strip()
            if not analysis:
                raise RuntimeError(f"ZAI 未返回解析: {raw}")
            return idx, analysis, None
        except Exception as exc:  # noqa: BLE001
            return idx, None, exc


async def process_file(path: Path, model: str, limit: int | None, concurrency: int) -> None:
    client = AsyncOpenAI(api_key=settings.zai_api_key, base_url=settings.zai_api_base)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        logger.warning("Skip (not a list): %s", path)
        return
    missing_indices = [i for i, q in enumerate(data) if isinstance(q, dict) and needs_analysis(q)]
    if limit:
        missing_indices = missing_indices[:limit]
    if not missing_indices:
        logger.info("No missing analysis in %s", path.name)
        return
    sem = asyncio.Semaphore(max(1, concurrency))
    tasks = [
        process_question(sem, client, model, data[i], i)
        for i in missing_indices
    ]
    results = await asyncio.gather(*tasks)
    filled = 0
    failures = 0
    for idx, analysis, error in results:
        if error:
            failures += 1
            logger.error("Failed to fill q#%s in %s: %s", idx, path.name, error)
            continue
        data[idx]["analysis"] = analysis
        filled += 1
    if filled:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Updated %s (filled %s, failed %s)", path.name, filled, failures)
    else:
        logger.info("No analyses filled for %s (failures %s)", path.name, failures)


async def main() -> int:
    args = parse_args()
    input_dir = Path(args.input).expanduser().resolve()
    if not input_dir.exists():
        logger.error("Input directory not found: %s", input_dir)
        return 1
    model = args.model or settings.zai_model or "glm-4.5"
    if not settings.zai_api_key:
        logger.error("ZAI_API_KEY 未配置 (.env)")
        return 1

    files = iter_converted_files(input_dir)
    if not files:
        logger.error("No *.converted.json found in %s", input_dir)
        return 1
    logger.info("Scanning %s files for missing analyses", len(files))
    for path in files:
        try:
            await process_file(path, model=model, limit=args.limit, concurrency=args.concurrency)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed processing %s: %s", path, exc)
    logger.info("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

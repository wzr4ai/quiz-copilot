#!/usr/bin/env python3
"""Quick ZAI connectivity/debug helper."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from openai import AsyncOpenAI

from app.core.config import settings


def _configure_logger() -> logging.Logger:
    logger = logging.getLogger("test_zai")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)
    logs_dir = Path(__file__).resolve().parents[1] / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(logs_dir / "test_zai.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


logger = _configure_logger()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test ZAI (OpenAI-compatible) connectivity.")
    parser.add_argument("--prompt", default="请用一句话回答：系统连接是否正常？", help="Prompt to send.")
    parser.add_argument("--model", default=None, help="Model name; defaults to ZAI_MODEL or gpt-4o-mini.")
    parser.add_argument("--max-tokens", type=int, default=200, help="Max tokens in response.")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    api_key = settings.zai_api_key
    api_base = settings.zai_api_base
    model = args.model or settings.zai_model or "gpt-4o-mini"

    if not api_key:
        logger.error("ZAI_API_KEY 未配置 (.env)")
        return 1
    if not api_base:
        logger.error("ZAI_API_BASE 未配置 (.env)")
        return 1

    client = AsyncOpenAI(api_key=api_key, base_url=api_base)
    logger.info("Sending test request to %s model=%s", api_base, model)
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个简洁的健康检查助手。"},
                {"role": "user", "content": args.prompt},
            ],
            max_tokens=args.max_tokens,
            temperature=0.2,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("ZAI request failed: %s", exc)
        return 1

    content = resp.choices[0].message.content if resp.choices else ""
    logger.info("Status: success, usage=%s, finish_reason=%s", resp.usage, resp.choices[0].finish_reason if resp.choices else None)
    logger.info("Response:\n%s", content)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

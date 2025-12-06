#!/usr/bin/env python3
"""
AI 智能选题工具 (Gemini 版)
扫描数据库中的题目，根据自然语言需求筛选出符合条件的题目ID，并导出结果。

Usage:
    # 使用默认 .env 配置
    python utils/filter_questions_by_ai.py --query "查找所有关于罚款金额的题目"

    # 手动指定 Gemini 参数
    python utils/filter_questions_by_ai.py \
        --query "找出所有涉及高处作业的安全题" \
        --api-key "AIzaSy..." \
        --model "gemini-1.5-pro" \
        --output high_work.csv

    python utils/filter_questions_by_ai.py --query "找出所有涉及高处作业的安全题" --api-base "https://gemini.wzrtnt.workers.dev" --api-key "BKu5rDYJe5nkp53m" --model "gemini-2.5-flash-lite" --concurrency 4 --output high_work.csv
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import random
import sys
import time
from pathlib import Path
from typing import List, Dict, Any

import httpx
from sqlmodel import Session, select

# 添加 backend 路径到 sys.path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.db import engine
from app.models.db_models import Question, Bank

# --- 日志配置 ---
LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "filter_dry_run.log"

logger = logging.getLogger("filter_questions")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


# 核心 Prompt
SYSTEM_PROMPT = """
你是一个严格的数据筛选程序。你的唯一任务是输出一个 JSON 格式的整数数组。

任务说明：
1. 接收用户的【筛选需求】和一批【题目数据】。
2. 逐一判断每道题目是否符合筛选需求。
3. 仅返回符合条件的题目 ID 列表（例如 `[101, 105]`）。
4. 如果没有匹配项，返回 `[]`。

严格约束：
- 禁止输出任何解释、分析或 Markdown 标记（如 ```json）。
- 禁止输出除了 JSON 数组以外的任何字符。
"""

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="利用 Gemini AI 语义筛选题目并导出。")
    parser.add_argument("--query", "-q", required=True, help="筛选需求")
    parser.add_argument("--output", "-o", default="filtered_questions.csv", help="输出路径")
    parser.add_argument("--bank-id", type=int, default=None, help="仅扫描指定题库")
    
    parser.add_argument("--api-key", default=None, help="Gemini API Key")
    parser.add_argument("--api-base", default=None, help="Gemini API Base URL")
    parser.add_argument("--model", default=None, help="Model Name")
    
    # 性能参数
    parser.add_argument("--batch-size", type=int, default=10, help="每批题目数量")
    parser.add_argument("--concurrency", type=int, default=3, help="并发数")
    parser.add_argument("--timeout", type=float, default=60.0, help="超时时间(秒)")
    parser.add_argument("--max-tokens", type=int, default=8192, help="AI 输出最大Token")
    parser.add_argument("--input-limit", type=int, default=300, help="输入截断长度")
    
    parser.add_argument("--dry-run", action="store_true", help="测试模式(不调AI)")
    
    return parser.parse_args()

def get_questions(session: Session, bank_id: int | None) -> List[Question]:
    stmt = select(Question)
    if bank_id:
        stmt = stmt.where(Question.bank_id == bank_id)
    questions = session.exec(stmt).all()
    logger.info(f"数据库中共有 {len(questions)} 道题目待扫描。")
    return list(questions)

def format_options(options: List[Dict[str, Any]] | None) -> str:
    if not options:
        return ""
    try:
        parts = [f"{o.get('key', '?')}:{o.get('text', '')}" for o in options if isinstance(o, dict)]
        return " ".join(parts)
    except Exception:
        return ""

def clean_json_string(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1:
            return text[start : end + 1]
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1:
        return text[start : end + 1]
    return text

async def call_gemini(
    client: httpx.AsyncClient,
    api_key: str,
    api_base: str,
    model: str,
    max_tokens: int,
    prompt: str,
    user_text: str
) -> str:
    """调用 Gemini API，包含重试机制与详细日志"""
    url = f"{api_base.rstrip('/')}/v1beta/models/{model}:generateContent?key={api_key}"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}, {"text": user_text}]}],
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": max_tokens,
            "response_mime_type": "application/json",
        },
    }
    
    # 记录请求概况 (不含 Prompt 正文，防止刷屏)
    req_preview = (
        f"REQ >> URL: {url} | Model: {model} | "
        f"InputLen: {len(user_text)} chars | Config: temp=0.0, max_tokens={max_tokens}"
    )
    logger.info(req_preview)

    max_retries = 5
    base_delay = 3.0

    for attempt in range(max_retries + 1):
        start_time = time.time()
        try:
            response = await client.post(url, json=payload)
            duration = time.time() - start_time
            
            # 429 限流处理
            if response.status_code == 429:
                if attempt < max_retries:
                    sleep_time = (base_delay * (2 ** attempt)) + (random.randint(0, 1000) / 1000.0)
                    logger.warning(
                        f"⚠️ [429 Limit] 耗时 {duration:.2f}s | 尝试 {attempt + 1}/{max_retries} | "
                        f"暂停 {sleep_time:.2f}s 后重试..."
                    )
                    await asyncio.sleep(sleep_time)
                    continue
                else:
                    logger.error("❌ [429 Limit] 达到最大重试次数，放弃。")
                    response.raise_for_status()

            if response.status_code != 200:
                logger.error(f"❌ API Error {response.status_code}: {response.text}")
                response.raise_for_status()
            
            data = response.json()
            
            # 提取并记录 Token 使用情况
            usage = data.get("usageMetadata", {})
            prompt_tok = usage.get("promptTokenCount", "N/A")
            resp_tok = usage.get("candidatesTokenCount", "N/A")
            total_tok = usage.get("totalTokenCount", "N/A")
            
            logger.info(
                f"RESP << 200 OK | Time: {duration:.2f}s | "
                f"Tokens: In={prompt_tok}, Out={resp_tok}, Total={total_tok}"
            )

            try:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError, TypeError) as e:
                logger.error(f"❌ 响应结构异常: {data}")
                raise RuntimeError("Gemini 返回结构异常") from e

        except (httpx.RequestError, httpx.HTTPStatusError, RuntimeError) as e:
            if attempt == max_retries:
                raise e
            logger.warning(f"⚠️ 网络/解析错误: {e}. 重试中...")
            await asyncio.sleep(2)
            
    raise RuntimeError("Unknown retry loop exit")

async def check_batch(
    sem: asyncio.Semaphore,
    client: httpx.AsyncClient,
    config: dict,
    query: str,
    batch_questions: List[Question],
    dry_run: bool,
    input_limit: int
) -> List[int]:
    if not batch_questions:
        return []

    input_text_lines = []
    for q in batch_questions:
        content_snippet = q.content[:input_limit].replace("\n", " ")
        opts_str = format_options(q.options)
        if len(opts_str) > input_limit: opts_str = opts_str[:input_limit] + "..."
        ans_str = q.standard_answer.replace("\n", " ")
        if len(ans_str) > 100: ans_str = ans_str[:100] + "..."
        
        line = f"ID:{q.id} | 题干:{content_snippet}"
        if opts_str: line += f" | 选项:{opts_str}"
        if ans_str:  line += f" | 答案:{ans_str}"
        input_text_lines.append(line)
    
    user_content = f"【筛选需求】：{query}\n\n【题目列表】：\n" + "\n".join(input_text_lines)

    if dry_run:
        logger.info(f"DRY RUN (Batch {len(batch_questions)} items)")
        return []

    async with sem:
        try:
            json_str = await call_gemini(
                client,
                config["api_key"],
                config["api_base"],
                config["model"],
                config["max_tokens"],
                SYSTEM_PROMPT,
                user_content
            )
            
            cleaned = clean_json_string(json_str)
            matched_ids = json.loads(cleaned)
            
            if isinstance(matched_ids, list):
                batch_ids = {q.id for q in batch_questions}
                return [mid for mid in matched_ids if mid in batch_ids]
            else:
                return []
        except Exception as e:
            logger.error(f"❌ 批次最终处理失败: {e}")
            return []

async def main():
    args = parse_args()
    
    gemini_config = {
        "api_key": args.api_key or settings.gemini_api_key,
        "api_base": args.api_base or settings.gemini_api_base or "https://generativelanguage.googleapis.com",
        "model": args.model or settings.gemini_model or "gemini-1.5-flash",
        "max_tokens": args.max_tokens
    }

    if not args.dry_run and not gemini_config["api_key"]:
        logger.error("未找到 API Key。")
        return

    output_path = Path(args.output)
    
    with Session(engine) as session:
        all_questions = get_questions(session, args.bank_id)
        banks = {b.id: b.title for b in session.exec(select(Bank)).all()}

        if not all_questions:
            logger.info("无题目。")
            return

        batches = [
            all_questions[i : i + args.batch_size] 
            for i in range(0, len(all_questions), args.batch_size)
        ]
        
        logger.info(f"任务启动: {len(all_questions)} 题 | {len(batches)} 批次")
        if not args.dry_run:
            logger.info(f"Model: {gemini_config['model']} | 并发: {args.concurrency}")

        sem = asyncio.Semaphore(args.concurrency)
        
        async with httpx.AsyncClient(timeout=args.timeout) as client:
            tasks = [
                check_batch(sem, client, gemini_config, args.query, batch, args.dry_run, args.input_limit)
                for batch in batches
            ]
            results = await asyncio.gather(*tasks)
        
        matched_ids = set()
        for res in results:
            matched_ids.update(res)
        
        logger.info(f"筛选完成，命中: {len(matched_ids)}")

        if matched_ids:
            matched_questions = [q for q in all_questions if q.id in matched_ids]
            
            with open(output_path, "w", newline="", encoding="utf-8-sig") as csvfile:
                fieldnames = ["ID", "Bank", "Type", "Content", "Options", "Answer", "Analysis"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for q in matched_questions:
                    opts_str = format_options(q.options)
                    writer.writerow({
                        "ID": q.id,
                        "Bank": banks.get(q.bank_id, str(q.bank_id)),
                        "Type": q.type,
                        "Content": q.content,
                        "Options": opts_str,
                        "Answer": q.standard_answer,
                        "Analysis": q.analysis or ""
                    })
            logger.info(f"文件已保存: {output_path.resolve()}")
        else:
            logger.info("未筛选到匹配题目。")

if __name__ == "__main__":
    asyncio.run(main())
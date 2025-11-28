from __future__ import annotations

import base64
import json
from typing import Any

import httpx
from pydantic import TypeAdapter, ValidationError

from app.core.config import settings
from app.models.schemas import QuestionCreate

_QUESTION_LIST_ADAPTER = TypeAdapter(list[QuestionCreate])


class AIServiceError(Exception):
    """Raised when AI service calls fail or responses are invalid."""


class AIService:
    def __init__(self, api_key: str | None, api_base: str, model: str, timeout: int = 40) -> None:
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def generate_questions_from_image(self, image_base64: str, bank_id: int) -> list[QuestionCreate]:
        if not image_base64:
            raise AIServiceError("缺少待识别的图片内容")

        sanitized = self._sanitize_base64(image_base64)
        payload = self._build_image_prompt(sanitized)
        text = await self._invoke_gemini(payload)
        return self._parse_questions(text, bank_id)

    def _sanitize_base64(self, data: str) -> str:
        cleaned = data.strip()
        if "," in cleaned and cleaned.lower().startswith("data:"):
            cleaned = cleaned.split(",", 1)[1]
        return cleaned.replace("\n", "").replace("\r", "")

    def _build_image_prompt(self, image_base64: str) -> dict[str, Any]:
        mime_type = self._infer_mime_type(image_base64)
        prompt = (
            "你是教育领域的出题助手。优先精准抽取图片中已有的试题并原样录入；"
            "只有在图片内容不是题目时，才根据材料创作 2-4 道题。"
            "输出必须是纯 JSON 数组，每个元素为题目对象，禁止返回任何额外文字或 Markdown 代码块。"
            "字段要求："
            '1) type: "choice_single"、"choice_multi"、"choice_judgment" 或 "short_answer"；'
            "   判断题使用 type=choice_judgment，选项仅 A=正确、B=错误；"
            "2) content: 题干文本；"
            "3) options: choice_single/choice_multi/judgment 需提供 2-5 个选项数组，每项含 key(如 A/B/C/D) 与 text；"
            "   short_answer 的 options 必须为空数组；"
            "4) standard_answer: 单选/判断填正确选项字母；多选填多个正确选项字母，逗号或空格分隔；"
            "   简答题填写参考答案文本；"
            "5) analysis: 简要解析文本，可为空字符串。"
            "示例输出："
            '['
            '{"type":"choice_judgment","content":"判断题干","options":[{"key":"A","text":"正确"},{"key":"B","text":"错误"}],"standard_answer":"A","analysis":"解析"},'
            '{"type":"choice_multi","content":"多选题干","options":[{"key":"A","text":"选项1"},{"key":"B","text":"选项2"}],"standard_answer":"A,B","analysis":""},'
            '{"type":"short_answer","content":"题干3","options":[],"standard_answer":"参考答案","analysis":""}'
            ']'
            "务必符合字段与类型，仅返回 JSON 数组。"
        )
        return {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": mime_type, "data": image_base64}},
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1536,
                "response_mime_type": "application/json",
            },
        }

    async def _invoke_gemini(self, payload: dict[str, Any]) -> str:
        if not self.api_key:
            raise AIServiceError("Gemini API key 未配置")

        url = f"{self.api_base}/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            raise AIServiceError(f"Gemini 调用失败: {exc.response.status_code} {detail}") from exc
        except httpx.HTTPError as exc:
            raise AIServiceError(f"Gemini 请求异常: {exc}") from exc

        data: dict[str, Any] = response.json()
        return self._extract_text(data)

    def _extract_text(self, data: dict[str, Any]) -> str:
        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                text = part.get("text")
                if text:
                    return text
        if data.get("error"):
            message = data["error"].get("message") or "未知错误"
            raise AIServiceError(f"Gemini 返回错误: {message}")
        raise AIServiceError("Gemini 返回为空，未能识别图片内容")

    def _parse_questions(self, text: str, bank_id: int) -> list[QuestionCreate]:
        cleaned_text = self._strip_code_fence(text)
        try:
            payload = json.loads(cleaned_text)
        except json.JSONDecodeError as exc:
            fallback = self._extract_json_array(cleaned_text)
            if fallback is None:
                raise AIServiceError("Gemini 返回的内容不是有效的 JSON") from exc
            payload = fallback

        if not isinstance(payload, list):
            raise AIServiceError("Gemini 返回格式应为题目数组")

        normalized: list[dict[str, Any]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            options = item.get("options") or []
            item["options"] = options if isinstance(options, list) else []
            item["bank_id"] = bank_id
            normalized.append(item)

        if not normalized:
            raise AIServiceError("Gemini 未生成可用题目")

        try:
            return _QUESTION_LIST_ADAPTER.validate_python(normalized)
        except ValidationError as exc:
            raise AIServiceError("Gemini 生成的题目字段缺失或格式不符") from exc

    def _strip_code_fence(self, text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = stripped.lstrip("`")
            if "\n" in stripped:
                stripped = stripped.split("\n", 1)[1]
        if stripped.endswith("```"):
            stripped = stripped[: stripped.rfind("```")].strip()
        return stripped

    def _extract_json_array(self, text: str) -> list[Any] | None:
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None

    def _infer_mime_type(self, image_base64: str) -> str:
        sample = image_base64[:128]
        remainder = len(sample) % 4
        if remainder:
            sample += "=" * (4 - remainder)
        try:
            header = base64.b64decode(sample, validate=False)
        except Exception:
            return "image/png"
        if header.startswith(b"\xff\xd8"):
            return "image/jpeg"
        if header.startswith(b"\x89PNG"):
            return "image/png"
        if header.startswith(b"GIF8"):
            return "image/gif"
        return "image/png"


ai_service = AIService(
    api_key=settings.gemini_api_key,
    api_base=settings.gemini_api_base,
    model=settings.gemini_model,
    timeout=settings.gemini_request_timeout,
)

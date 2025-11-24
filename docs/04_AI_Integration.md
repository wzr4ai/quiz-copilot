# 04. AI 服务层集成 (Gemini & OpenAI)

## 1. 模型策略
为了平衡成本与效果，在后端实现一个 `AIService` 类，根据任务分发模型（首选 / 备选）：

* **图像识别（OCR + 理解）** -> 首选 **Gemini 2.5 Flash** 或 **Gemini 2.5 Pro**；备选 **GLM-4.5V**（多模态备用）。
* **逻辑 / 指令遵循（例如按要求生成 JSON）** -> 首选 **Gemini 2.5 Flash / Pro**；备选 **GLM-4.6**（复杂推理备用）。
* **用户对话 / 人文关怀** -> 首选 **Gemini 2.5 Flash**；备选 **DeepSeek V3.2**（更贴合开放式对话）。

### 其他模型调用建议
- 多模态请求：优先用 Flash 版本，Pro 仅在 OCR 失败或需要更强视觉推理时回退；备选 GLM-4.5V 时保持相同的输出 JSON 结构。
- 结构化输出：指令/逻辑类请求统一加 `response_mime_type: application/json`（或等价参数），温度 ≤ 0.3；若 JSON 解析失败，降温重试并附加“仅输出 JSON”提醒。
- 对话类：开启流式输出降低延迟；如检测到敏感或情绪化内容，可在系统提示内加入“共情+安全边界”指示后再调用。
- 失败重试：首次调用超时或 5xx 时自动切换到对应备选模型，并在日志中记录模型名+请求 ID 便于排查。

## 2. Prompt Engineering (核心资产)

### 场景一：文本转结构化题库 (System Prompt)
```text
Role: 你是一个专业的教育专家和数据结构化助手。
Task: 用户将提供一段文本资料。你需要从中提取关键知识点，生成 3-5 道单选题和 1 道简答题。
Output Format: 必须严格仅返回以下 JSON 格式，不要包含 Markdown 代码块标记：
[
  {
    "type": "choice_single",
    "content": "题目描述...",
    "options": [{"key": "A", "text": "选项A"}, {"key": "B", "text": "选项B"}],
    "standard_answer": "A",
    "analysis": "解析..."
  }
]
```

### 场景二：主观题智能判分 (System Prompt)
```text
Role: 你是一位公正的阅卷老师。
Input:
1. 题目: {question_content}
2. 标准参考答案: {standard_answer}
3. 学生回答: {user_answer}

Task: 请根据标准答案对学生回答进行评分（满分 10 分）并给出点评。
Output JSON:
{
  "score": 7,
  "feedback": "回答涵盖了核心点 A，但忽略了 B 点。建议补充..."
}
```

## 3. 代码实现接口规范
```python
class AIService:
    async def generate_quiz_from_text(self, text: str) -> List[QuestionDict]:
        # 调用 LLM，并尝试 json.loads 解析返回结果；解析失败时重试
        pass

    async def grade_subjective_question(self, question, user_answer) -> GradeResult:
        # 调用 LLM 进行评分
        pass
```

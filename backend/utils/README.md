# Question Bank Tool

Python 脚本，用于将 `Question_Bank_File` 中的混合文档（json/doc/docx/pdf）转换成：
- `*.converted.json`：结构化题目数据（对原本已是题库格式的 JSON 做规范化，可直接对接后端导入）。
- `*.chunks.jsonl`：按题号智能分块后的文本，便于调用 AI/OCR API 识别，不会在题干中途截断；文档中加粗/着色的文本会被标记为 `<ANS>…</ANS>` 以保留正确答案提示。

## 安装依赖
在仓库根目录执行：
```bash
cd backend
pip install -e .  # pyproject 中已加入 python-docx 与 pdfplumber
```
如需解析 `.doc`，额外安装 `textract`（或先将文件转换为 docx/pdf）。

## 运行
```bash
uv run python utils/question_bank_tool.py \
  --input ./Question_Bank_File \
  --output ./processed_question_bank \
  --bank-id 1
```

可选参数：
- `--chunk-size`：单个分块最大字符数（默认 1400，防止超过模型上下文或 API 长度限制）。
- `--min-chunk`：分块最小字符数（默认 300，避免碎片化）。

输出路径 `processed_question_bank/` 将生成 `.converted.json` 与 `.chunks.jsonl`，文件名与源文件同名。

## 批量导入到题库（含 AI 解析）
`import_question_bank.py` 会读取 `processed_question_bank` 下的文件：
- `*.converted.json`：直接导入。
- `*.chunks.jsonl`：对每个分块调用 Gemini（按 `.env` 中的 `GEMINI_API_KEY`、`GEMINI_API_BASE`、`GEMINI_MODEL`）解析出题目再导入。

导入时会以文件名（去除后缀）创建/复用题库名称。

运行示例（在 backend 目录下）：
```bash
uv run python utils/import_question_bank.py \
  --input processed_question_bank \
  --limit 2           # 可选，限制处理文件数
  --ai-model gemini-2.5-flash  # 可选，覆盖默认模型
```

注意：
- 确保数据库连接已配置好（`DATABASE_URL` 环境变量）并可写入。
- 对 `.chunks.jsonl`，需要外网调用 Gemini；若无 API Key 或网络不可达，这类文件将无法解析。
- 导入过程中会跳过重复题（同 bank_id、type、content、选项 与标准答案一致）。
- 执行日志输出到终端，同时写入 `logs/import_question_bank.log` 方便排查。

## 使用 ZAI（OpenAI 兼容）导入
ZAI 配置（.env）：
- `ZAI_API_KEY`：必填
- `ZAI_API_BASE`：可选，自定义 Base URL
- `ZAI_MODEL`：可选，未填则脚本默认 `gpt-4o-mini`

运行示例（在 backend 目录下）：
```bash
uv run python utils/import_question_bank_zai.py \
  --input processed_question_bank \
  --limit 1 \
  --retries 3 \
  --model gpt-4o-mini  # 可选，覆盖 ZAI_MODEL
```

特点：
- AI 解析失败会自动重试，每个 chunk 最多 3 次。
- 生成的题库名称会在原文件名基础上附加 “(zai)” 标记。
- 日志写入 `logs/import_question_bank_zai.log`。

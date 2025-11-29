# Backend 开发说明（FastAPI + SQLModel）

## 1. 环境与运行
- 依赖安装：`cd backend && pip install -e .`（或 `uv pip install -e .`）。需要 Python >= 3.13。
- 配置：`backend/.env`（数据库、JWT、AI 等）。关键项：`DATABASE_URL`、`SECRET_KEY`、`ACCESS_TOKEN_EXPIRE_MINUTES`、`ZAI_API_KEY`、`GEMINI_API_KEY`。
- 初始化 DB：`python -c "from app.db import init_db; init_db()"`.
- 启动：`uvicorn app.main:app --reload`（工作目录 `backend/src` 或设置 PYTHONPATH）。

## 2. 目录结构
- `src/app/main.py`：FastAPI 入口。
- `src/app/api/`：路由（题库、题目、学习、认证等）。
- `src/app/models/`：`db_models.py`（SQLModel 表）、`schemas.py`（Pydantic）。
- `src/app/core/`：配置、安全、依赖。
- `src/app/services/`：AI、批量导入、辅助服务。
- `logs/`：后端日志（导入、质检、问题记录等）。
- `utils/`：批处理脚本（分割、导入、修复、质检、日志导入）。

## 3. 核心路由（节选）
- `POST /auth/login`，注册：`/auth/register`。
- 题库：`/banks` CRUD，合并 `/banks/merge`。
- 题目：列表/创建/更新/删除 `/questions`；AI 导题 `/questions/ai/...`；收藏 `/questions/{id}/favorite`。
- Admin 特有：
  - `GET /questions/admin/{id}`：按 QID 取题。
  - `GET /questions/admin/search`：关键字搜索题干/答案。
  - `GET/PATCH /questions/admin/issues`：疑似错题记录列表、状态更新。

## 4. 模型与表
- `User`、`Bank`、`Question`、`FavoriteBank/Question`、`StudySession`、`WrongRecord`。
- `QuestionIssue`：疑似错题记录（字段：question_id、bank_id、reason、status=pending/verified_ok/corrected）。

## 5. 日志与问题处理
- `logs/question_issue.log`：疑似错题来源；`utils/import_issue_log.py` 可导入 DB。
- `logs/analysis_corrections.log`：AI 修正解析记录。
- `logs/missing_answers.log`：`utils/scan_banks.py --log-missing` 记录缺失答案题目。

## 6. AI 与批处理
- `question_bank_tool.py`：分割题库文件，生成 `.converted.json`/`.chunks.jsonl`。
- `import_question_bank.py/_zai.py`：批量导入（文本/图片/AI 并发，内容过滤处理）。
- `fill_missing_analysis_db.py`：glm-4.5 质检/补全解析，写入 DB/日志。
- 临时脚本示例：`fix_x_v_judgment.py`（将特定 bank 的 X/V/N 选择题改为判断题）。

## 7. 常用命令
- 运行：`uvicorn app.main:app --reload`
- 批量导入（ZAI）：`python utils/import_question_bank_zai.py --input processed_question_bank`
- 质检导入问题表：`python utils/import_issue_log.py`
- 缺失答案扫描：`python utils/scan_banks.py --log-missing`
- 填充解析：`python utils/fill_missing_analysis_db.py --concurrency 5`

## 8. 注意事项
- JWT 有效期默认 60 分钟，可在 `.env` 调整，个人使用可延长（注意令牌泄露风险）。
- ZAI 接口需通过 `ZAI_API_KEY`/`ZAI_API_BASE`，已处理 content filter 1301 的跳过逻辑。
- 批量导入并发+重试，包含内容过滤/JSON 清洗；失败分块会记录日志。  

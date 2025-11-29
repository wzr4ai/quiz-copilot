# Quiz Copilot 项目总览

## 1. 目录结构
- `backend/`：FastAPI + SQLModel 后端，提供认证、题库管理、AI 导入、疑似错题管理等接口。
- `uni-app/`：UniApp 前端，含练习、题库管理、错题处理、快速编辑等页面。
- `Question_Bank_File/`：原始题库文件（doc/docx/pdf/json 等）。
- `backend/utils/`：批处理与维护脚本（分割题库、导入、修正、质检、日志导入等）。
- `docs/`：架构与流程文档。

## 2. 核心功能
- 认证与角色：JWT（默认 60 分钟，`ACCESS_TOKEN_EXPIRE_MINUTES` 可调）；admin 拥有管理和质检入口。
- 题库管理：创建/更新/删除题库，批量导入处理后的题目，支持 AI 辅助导入与去重。
- AI 能力：文本/图片导题、缺失解析自动填充、疑似错题质检（glm-4.5）、ZAI 导入与并发解析。
- 质检与修正：从日志导入疑似错题至 DB，前端列出并可编辑标记；支持按 QID 快速编辑。
- 搜索与快速定位：admin 关键字搜索题干/答案；按 QID 打开编辑页；疑似错题列表快速跳转。

## 3. 重要日志与辅助文件
- `backend/logs/`: `question_issue.log`（疑似错题）、`analysis_corrections.log`（解析修正）、`missing_answers.log`（缺失答案）、`import_question_bank_zai.log` 等。
- `backend/utils/import_issue_log.py`：将 `question_issue.log` 导入 DB 的 `question_issue` 表。
- `backend/utils/scan_banks.py --log-missing`：扫描 DB，记录无标准答案的题目。

## 4. 快速使用
1) 后端准备  
   - `cd backend && pip install -e .`（或 `uv pip install -e .`）。  
   - 配置 `.env`（数据库、JWT、ZAI/Gemini 等）。
   - 初始化 DB：`python -c "from app.db import init_db; init_db()"`.
2) 分割与导入  
   - `python utils/question_bank_tool.py --input Question_Bank_File --output processed_question_bank`.  
   - `python utils/import_question_bank_zai.py --input processed_question_bank`（ZAI 多轮并发解析）。  
3) 质检与修复  
   - `python utils/import_issue_log.py` 将日志导入 DB。  
   - 前端 admin 访问“疑似错题”“题目搜索”“按 ID 编辑”进行复核。  
4) 运行  
   - 后端：`uvicorn app.main:app --reload`（路径 `backend/src`）。  
   - 前端：在 UniApp/HBuilderX 中导入 `uni-app/` 目录运行。

## 5. 角色与安全
- 普通用户：练习、收藏、错题本。  
- 管理员：题库管理、批量导入、QID 编辑、疑似错题处理、搜索。  
- 长期登录可调整 `.env` 中 `ACCESS_TOKEN_EXPIRE_MINUTES`；个人/小团队可拉长（注意令牌泄露风险）。

## 6. 主要辅助脚本（backend/utils）
- `question_bank_tool.py`：分割/规范化题库文件，生成 `.converted.json`、`.chunks.jsonl`。  
- `import_question_bank.py` / `_zai.py`：批量导入（文本/图片/AI）。  
- `analyze_question_banks.py`：分析文件结构输出 `docs/question_bank_analysis.md`。  
- `fill_missing_analysis_db.py`：AI 质检/补全解析，写入 DB 与日志。  
- `import_issue_log.py`：日志导入疑似错题表。  
- `fix_x_v_judgment.py`：临时修复脚本（示例：将 X/V/N 选择题改为判断题）。  

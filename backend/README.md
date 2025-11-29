# Backend

## 部署指南（中文）

1) 环境准备  
   - Python >= 3.13，推荐虚拟环境：`python -m venv .venv && source .venv/bin/activate`。  
   - 安装依赖：`pip install -e .`（在 backend 目录下）。  
   - 可选：使用 Docker Compose 启动本地 Postgres/Redis（文件在 `backend/docker/docker-compose.dev.yml`）。

2) 配置 `.env`（复制 `.env.example` 后修改）  
   - `DATABASE_URL`：数据库连接。  
   - `SECRET_KEY`：JWT 签名。  
   - `ACCESS_TOKEN_EXPIRE_MINUTES`：令牌有效期（默认 60 分钟，可按需调整）。  
   - AI：`ZAI_API_KEY`/`ZAI_API_BASE`/`ZAI_MODEL`，可选 `GEMINI_API_KEY` 等。

3) 初始化数据库  
   ```bash
   python -c "from app.db import init_db; init_db()"
   ```

4) 启动服务  
   ```bash
   uvicorn app.main:app --reload --app-dir src
   ```
   生产可用 gunicorn+uvicorn worker，关闭 `--reload`。

5) 常用维护脚本（在 backend/ 下）  
   - 分割题库：`python utils/question_bank_tool.py --input ../Question_Bank_File --output processed_question_bank`  
   - 导入题库（ZAI）：`python utils/import_question_bank_zai.py --input processed_question_bank`  
   - 缺失答案扫描：`python utils/scan_banks.py --log-missing`  
   - 质检/补全解析：`python utils/fill_missing_analysis_db.py --concurrency 5`  
   - 导入疑似错题日志：`python utils/import_issue_log.py`  
   - 临时修复示例：`python utils/fix_x_v_judgment.py`

6) 其它说明  
   - 前端 `uni-app/` 的 `API_BASE` 需指向后端地址。  
   - 日志默认写入 `backend/logs/`。  
   - 管理员可使用：题库管理、按 QID 编辑、关键词搜索、疑似错题处理等功能。

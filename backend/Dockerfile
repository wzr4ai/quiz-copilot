# 使用官方提供的 uv 镜像，基于 Python 3.13 (Debian bookworm slim)
# 这是一个多阶段构建的优化镜像，包含了 uv 工具
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
# 1. 编译字节码，加快启动速度
# 2. 确保 uv 使用系统 Python 环境或虚拟环境路径正确
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
# 确保容器内的 PATH 包含虚拟环境的 bin 目录
ENV PATH="/app/.venv/bin:$PATH"

# --- 依赖安装层 (利用 Docker 缓存) ---

# 仅复制依赖描述文件
COPY pyproject.toml uv.lock ./

# 使用 uv 同步安装依赖
# --frozen: 严格按照 lock 文件安装
# --no-dev: 不安装开发环境依赖 (如 pytest 等，生产环境不需要)
RUN uv sync --frozen --no-dev

# --- 代码复制层 ---

# 复制源代码目录
COPY src ./src
# 复制其他必要的运行脚本或配置
COPY main.py ./
COPY start_backend.sh ./
COPY README.md ./

# 如果你的代码需要读取 utils 目录，也需要复制
COPY utils ./utils

# --- 运行时配置 ---

# 给启动脚本添加执行权限
RUN chmod +x start_backend.sh

# 创建日志和数据目录（确保目录存在，防止报错）
RUN mkdir -p logs done processed_question_bank Question_Bank_File

# 暴露端口 (FastAPI 默认通常是 8000)
EXPOSE 8000

# 启动命令
# 建议直接使用 uvicorn 启动，或者运行你的 shell 脚本
# 这里假设你的启动逻辑在 start_backend.sh 里
CMD ["./start_backend.sh"]

# 如果 start_backend.sh 比较复杂，也可以直接用下面的命令启动 FastAPI：
# CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
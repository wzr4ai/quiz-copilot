# 02. 后端架构 (FastAPI)

## 1. API 路由规划
建议使用 `APIRouter` 进行模块化拆分。

### `/api/v1/auth`
* `POST /login`: 接收微信 `code` -> 换取 `openid` -> 返回 JWT Token。

### `/api/v1/banks` (题库管理)
* `GET /`: 获取当前用户的题库列表。
* `POST /`: 创建新题库。
* `DELETE /{id}`: 删除题库。

### `/api/v1/questions` (题目管理)
* `GET /`: 获取某题库下的题目（分页）。
* `POST /manual`: 手动录入单题。
* `POST /ai/text-to-quiz`: **(AI 核心)** 接收长文本，返回结构化题目列表。
* `POST /ai/image-to-quiz`: **(AI 核心)** 接收图片，返回结构化题目列表。
* `POST /ai/batch-import`: 扫描服务器指定文件夹下的图片/文本，批量导入题目并返回导入/失败/疑似异常的报告。
* `PUT /{id}`: 题目修正/编辑。

### `/api/v1/study` (刷题与判分)
* `GET /session/start`: 生成一次练习（随机/顺序/错题模式）。
* `POST /submit`: 提交答案。如果是主观题，触发后台 AI 判分任务。
* `GET /wrong`: 拉取错题本（根据最近一次答题记录，正确后自动覆盖旧错题）。

## 2. 项目结构示例
```python
# app/main.py
from fastapi import FastAPI
from app.api import auth, banks, questions, study

app = FastAPI(title="SmartQuiz API")

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(banks.router, prefix="/api/v1/banks", tags=["Banks"])
app.include_router(questions.router, prefix="/api/v1/questions", tags=["Questions"])
app.include_router(study.router, prefix="/api/v1/study", tags=["Study"])
```

## 3. 异步与并发
* AI 接口（特别是图片识别）可能耗时 5-10 秒，路由必须使用 `async def`。
* 建议在 `app/services/ai_service.py` 中封装 AI 调用，并设置超时与重试策略。
* 使用 `asyncio.create_task` 将长任务异步化，避免阻塞请求。

## 4. 当前实现备注 (MVP)
- 持久化切换为 PostgreSQL（连接串读取 `.env` 的 `DATABASE_URL`），使用 SQLModel 定义用户/题库/题目/错题记录/收藏等表，应用启动时自动建表。
- 认证使用 `OAuth2PasswordBearer`（账号密码登录），密码 Bcrypt 哈希存储，角色包含 `user`/`admin`，仅管理员可管理数据库中的题库与题目。
- `app/services/ai_stub.py` 生成示例题目，用于文本/图片导入的接口契约占位。
- 开启了 CORS（默认 `*`），便于 H5 调试；上线时请收敛域名。

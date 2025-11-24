# 01. 数据库设计 (PostgreSQL + SQLModel)

## 1. 设计原则
* **利用 JSONB**: 题目选项（Options）结构多变，不适合用关联表，直接存 JSONB。
* **UUID/ULID**: 主键建议使用 ULID（可排序的 UUID），便于分布式和数据迁移。
* **规范化**: 题库与题目分离，刷题记录与错题本分离。

## 2. 核心模型 (Python SQLModel 草稿)

### User (用户表)
```python
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    openid: str = Field(index=True, unique=True)  # 微信 OpenID
    nickname: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### QuestionBank (题库表)
```python
class QuestionBank(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    title: str
    description: Optional[str] = None
    is_public: bool = False
```

### Question (题目表 - 核心)
```python
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB


class Question(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    bank_id: int = Field(foreign_key="questionbank.id")

    # 题型: choice_single, choice_multi, true_false, short_answer
    type: str = Field(index=True)

    content: str  # 题干

    # 关键设计：存储选项列表
    # 格式示例: [{"key": "A", "text": "苹果"}, {"key": "B", "text": "香蕉"}]
    options: List[dict] = Field(default=[], sa_column=Column(JSONB))

    standard_answer: str  # 答案 (如 "A", "AB", "True", 或主观题范文)
    analysis: Optional[str] = None  # 解析

    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### UserRecord (刷题记录)
```python
class UserRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    question_id: int = Field(foreign_key="question.id")

    user_answer: str  # 用户填写的答案
    is_correct: bool  # 客观题直接判断，主观题由 AI 判断

    ai_score: Optional[int] = None  # 主观题得分 (0-100)
    ai_comment: Optional[str] = None  # AI 评语

    reviewed_at: datetime = Field(default_factory=datetime.utcnow)
```

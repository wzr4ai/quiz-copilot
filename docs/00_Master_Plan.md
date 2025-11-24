# 00. 智刷 AI (SmartQuiz) - 项目总规划

## 1. 项目简介
本项目旨在开发一款基于 AI 赋能的智能刷题小程序。通过 LLM (大语言模型) 解决传统刷题软件“录题繁琐”和“主观题无法判分”的两大痛点。

## 2. 技术栈选型

| 模块 | 技术方案 | 说明 |
| :--- | :--- | :--- |
| **前端** | **UniApp (Vue3 + Vite)** | 目标发布为微信小程序，兼顾多端扩展。 |
| **后端** | **Python FastAPI** | 异步高性能，适合 AI 流式处理和并发请求。 |
| **数据库** | **PostgreSQL 16+** | 利用 `JSONB` 存储非结构化题目数据；向量插件 `pgvector` (可选，预留未来RAG功能)。 |
| **ORM** | **SQLModel** | 结合 Pydantic 和 SQLAlchemy，提供最佳的类型提示体验。 |
| **AI** | **Gemini (主力) + OpenAI兼容接口** | Gemini 1.5 Flash 用于图像识别和大量文本处理；DeepSeek/OpenAI 用于逻辑判题。 |

## 3. 核心功能里程碑 (Milestones)

* **Phase 1: 基础骨架 (MVP)**
    * [ ] 数据库设计与 CRUD 接口跑通。
    * [ ] 前端实现题库列表、答题界面（仅支持单选）。
    * [ ] 简单的手动录题功能。
* **Phase 2: AI 魔法 (Core)**
    * [ ] 接入 Gemini API，实现“文本转题库”。
    * [ ] 实现“拍照转题库” (OCR + 结构化)。
    * [ ] 实现主观题 AI 判分（评分 + 评语）。
* **Phase 3: 数据与闭环**
    * [ ] 错题本逻辑（自动加入错题）。
    * [ ] 艾宾浩斯遗忘曲线复习提醒。

## 4. 目录结构建议

```text
SmartQuiz/
├── backend/             # FastAPI 项目
│   ├── app/
│   │   ├── models/      # SQLModel 数据模型
│   │   ├── api/         # 接口路由
│   │   ├── services/    # 业务逻辑 (AI调用等)
│   │   ├── core/        # 配置 (Config, DB连接)
│   │   └── main.py      # 入口
│   ├── tests/
│   └── requirements.txt
├── frontend/            # UniApp 项目
│   ├── pages/
│   ├── components/
│   └── static/
└── docs/                # 开发文档
```

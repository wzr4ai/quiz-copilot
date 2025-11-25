# 03. 前端架构 (UniApp)

## 1. 页面路由 (pages.json)

| 路径 | 页面名称 | 功能描述 |
| :--- | :--- | :--- |
| `pages/index/index` | 首页 | 展示题库列表、快捷入口（拍照录题）。 |
| `pages/quiz/index` | 答题页 | **核心页**。支持随机/错题模式、答案提交、在线修正题目。 |
| `pages/quiz/result` | 结果页 | 展示本次练习得分、错题解析。 |
| `pages/editor/add` | 录题中心 | 选择“文本导入”或“拍照导入”，识别后可预览并编辑题目。 |
| `pages/profile/index`| 个人中心 | 历史记录、设置。 |

## 2. 关键组件 (Components)

### `QuestionCard.vue`
* **功能**: 渲染单道题目。
* **Props**: `question` (Object), `mode` (Answer/Review)。
* **逻辑**: 
    * 根据 `type` 渲染不同 UI（单选是 Radio，多选是 Checkbox，主观题是 Textarea）。
    * 点击选项后，触发 `emit('select', value)`。

### `AIImportPopup.vue`
* **功能**: 录题时的等待弹窗。
* **逻辑**: 展示“AI 正在读取试卷...”，后端返回后，展示预览列表供用户勾选确认。

## 3. 状态管理 (Pinia)
* `useQuizStore`: 管理当前正在做的题目队列、用户当前的答案、倒计时。
* `useUserStore`: 管理 JWT Token、用户信息。

## 4. 当前 H5 MVP 交互
- 首页请求 `/api/v1/banks` 填充题库卡片，并提供“错题重练”快捷入口（传参 `mode=wrong`）。
- 录题页：文本/图片提交到 `/api/v1/questions/ai/*`，展示返回题目列表，允许编辑后批量调用 `/api/v1/questions/manual` 保存。
- 答题页：通过 `/api/v1/study/session/start` 拉取题目，提交答案到 `/api/v1/study/submit`，编辑按钮调用 `/api/v1/questions/{id}` 进行题干修正。
- 结果页：展示得分与错题列表，支持“一键重练”和“错题重练”。

## 5. UI 框架建议
* 推荐使用 **uView-plus** 或 **Wot-design-uni**。
* 重点关注组件：`Upload` (图片上传), `Steps` (录题步骤), `Progress` (答题进度)。

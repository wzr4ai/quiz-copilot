# 03. 前端架构 (UniApp)

## 1. 页面路由 (pages.json)

| 路径 | 页面名称 | 功能描述 |
| :--- | :--- | :--- |
| `pages/index/index` | 首页 | 展示题库列表、快捷入口（拍照录题）。 |
| `pages/quiz/index` | 答题页 | **核心页**。类似抖音上下滑或左右滑切换题目。 |
| `pages/quiz/result` | 结果页 | 展示本次练习得分、错题解析。 |
| `pages/editor/add` | 录题中心 | 选择“文本导入”或“拍照导入”。 |
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

## 4. UI 框架建议
* 推荐使用 **uView-plus** 或 **Wot-design-uni**。
* 重点关注组件：`Upload` (图片上传), `Steps` (录题步骤), `Progress` (答题进度)。

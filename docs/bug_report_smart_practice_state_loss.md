# 智能刷题进度丢失问题排查报告

## 问题描述
- 正常刷题（未进入强化）时，简答题输入完成后直接离开/刷新页面再次进入，当前题答案为空，提交整组提示“还有未作答题目”。

## 复现路径（手动）
1. 开始智能刷题，遇到简答题。
2. 输入答案，不点击页面其他区域（保持输入框聚焦），直接切 Tab/关闭页面或刷新后再进入智能刷题页。
3. 重新加载当前题组后，该简答题答案为空，提交组时提示未作答。

## 排查结论
- 题目编辑不会清空作答：前端保存编辑仅 merge 更新后的题干/选项/解析（`uni-app/pages/quiz/smart.vue:543`），后端 `PUT /questions/{id}` 也不触碰作答记录（`backend/src/app/api/questions.py:143`），排除“编辑题目导致进度丢失”。
- 实际根因：简答题答案只在输入框失焦时触发 `submitText` → `sendAnswer`（`uni-app/pages/quiz/smart.vue:103`, `uni-app/pages/quiz/smart.vue:419`），离开页面/刷新不会触发失焦，导致答案仅存在于前端内存未写入后端。`handleNext`/`completeGroup` 也没有兜底提交文本答案（`uni-app/pages/quiz/smart.vue:454`, `uni-app/pages/quiz/smart.vue:471`），返回时服务端的 `user_answer` 为空，表现为进度丢失并阻塞组提交。

## 影响范围
- 智能刷题中的所有简答题（正常/强化模式均受影响），在未失焦就离开或刷新时会丢失当前题作答。
- 单选/多选/判断即时提交，不受此问题影响。

## 修复建议
1. 在导航与提交前强制提交简答题：`handleNext`、`completeGroup` 中检测当前题为 `short_answer` 且未锁定时调用 `submitText`（或直接 `sendAnswer`），确保离开前写入后端。
2. 页面生命周期兜底：在 `onHide/onUnload` 检查当前题为简答题且本地有值未锁定时尝试提交，避免刷新或切页丢失。
3. 增加回归用例：覆盖“简答题输入后未失焦直接离开页面再回来”与“未失焦直接完成本组”，验证后端仍能返回 `user_answer`。

## 相关文件
- 前端：`uni-app/pages/quiz/smart.vue:103`, `uni-app/pages/quiz/smart.vue:419`, `uni-app/pages/quiz/smart.vue:454`, `uni-app/pages/quiz/smart.vue:471`, `uni-app/pages/quiz/smart.vue:543`
- 后端：`backend/src/app/api/questions.py:143`

## 新发现：反馈跳过后重复题状态丢失 & 误判
- 现象：使用“题目有问题，反馈并跳过”后，后续遇到重复出现的题目时会出现：
  - 已答状态不落盘/刷新后为空。
  - 明明正确选项是 B，我选择 C 却被判为正确。

### 复现路径
1. 题库较小或连续跳过多题（反馈后该题 `practice_count` 被置为 -1，题池变小），容易在后续组里抽到之前出现过的题。
2. 再次遇到同一道题，选择与上次不同的答案（例如正确为 B，此次选 C）。
3. 页面显示判对，刷新/重载后该题仍为空白，组提交时也把它当作已答正确处理。

### 根因分析
- 题目抽取未避开当前会话已出现的题：`_load_questions`/`_select_questions_by_ratio`（`backend/src/app/services/smart_practice_service.py:120` 起）在生成后续组时没有排除本 Session 已答/已出现的题，题池越小（比如多次反馈跳过），重复几率越高。
- 后端答题去重仅按 `session_id + question_id`，且“已计数”的旧答案直接短路返回，不再写入新答案：
  - `answer_question` 里只要找到已有 `SmartPracticeAnswer` 且 `existing.counted` 为真，就直接返回旧的 `is_correct`（`backend/src/app/services/smart_practice_service.py:525-583`），忽略这一次提交。
  - 问题重复出现时，当前组的作答不会被保存，仍沿用旧判定，因此出现“选 C 也判对”的错判。
- 状态看起来“丢失”：`_serialize_group` 返回答案时按 `answered_at >= group.created_at` 过滤（`backend/src/app/services/smart_practice_service.py:245-279`），重复题的旧答案时间早于当前组，前端拿不到 `user_answer`，展示为空，用户即使再次作答也因上述短路不会落盘。

### 影响范围
- 当前会话中被重复抽中的题都会受影响：无法重答、无法纠错，判分沿用旧结果，可能误导为正确；同时进度无法保存，提交/重载后仍为空。

### 修复建议
1. 抽题侧：生成新组时排除当前 Session 已出现的题（或至少已计数的题），必要时扩大题池不足提示。
2. 答题侧：`answer_question` 不应仅凭 `existing.counted` 短路；应按组/时间（`answered_at >= group.created_at` 或携带 `group_id`）判定当前组是否需要记录新答案并重新计算正误。
3. 组校验侧：`_wrong_questions_for_group` 同样应按当前组的作答记录（基于时间或 `group_id`）判断缺失/正误，避免旧答案掩盖当前组的未答/错答。 

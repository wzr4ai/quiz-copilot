# UniApp 前端说明

## 1. 运行与环境
- 打开 `uni-app/` 目录导入 HBuilderX 或 UniApp CLI。
- 默认接口基址在 `services/api.js` 的 `API_BASE`；按需修改为后端地址。
- 依赖 Token/Role 存储于本地（`uni.setStorageSync`）；未登录或非 admin 将被拦截在管理页。

## 2. 主要页面
- `/pages/index/index`：首页/练习入口。
- `/pages/quiz/*`：答题与结果。
- `/pages/editor/add`：录题中心。
- `/pages/profile/index`：登录/注册、账号信息。
- `/pages/manager/index`：题库管理（admin）：
  - 题库 CRUD、合并、批量导入。
  - 快速按题目 ID 跳转编辑。
  - 按钮入口：合并题库、疑似错题、题目搜索。
- `/pages/manager/merge`：题库合并。
- `/pages/manager/qid`：按 QID 编辑题目（admin）。
- `/pages/manager/issues`：疑似错题列表与编辑（admin），可更新状态“已核查无误/已核查修正”。
- `/pages/manager/search`：关键词搜索题干/答案（admin），可跳转到 QID 编辑。

## 3. 服务接口（services/api.js）
- 认证：`login`/`register`，本地存储 token/role/username。
- 题库/题目：`fetchBanks`、`fetchQuestions`、`create/update/delete`、批量导入等。
- 收藏、学习：收藏题、练习会话等。
- Admin：
  - `adminGetQuestionById`：按 QID 取题。
  - `adminFetchIssueQuestions` / `adminUpdateIssue`：疑似错题列表与状态更新。
  - `adminSearchQuestions`：关键词搜索题干/答案。

## 4. 管理端权限
- `pages/manager/*` 在 `onLoad` 时检查 `getToken` 和 `getRole`；非 admin 会提示并跳转首页。

## 5. UI 提示
- Manager 页右上角入口：新建题库、合并题库、疑似错题、搜索题目。
- 疑似错题页：上方 picker 选日志条目，显示 reason，支持编辑题目并更新状态。
- 搜索页：输入关键字，列出匹配题目（显示 QID/题库/选项/答案/解析），可一键跳转 QID 编辑页。

## 6. 常见操作
- 批量导入：管理页“批量导入”填写服务器目录并执行。
- 按题目 ID 快速编辑：管理页输入 QID 点击“打开”跳转到 QID 页面。
- 处理疑似错题：管理页进入“疑似错题”，选择条目，编辑并保存，更新状态。  

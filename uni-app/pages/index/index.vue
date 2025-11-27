<template>
	<view class="page">
		<view class="hero">
			<view>
				<text class="eyebrow">SmartQuiz</text>
				<text class="title">智刷 AI 题库</text>
				<text class="subtitle">快速导入，随时刷题。</text>
			</view>
		</view>

		<view class="card quick-actions">
			<text class="card-title">快捷入口</text>
			<view class="action-grid">
				<view class="action" @click="toQuiz()">
					<text class="action-label">开始练习</text>
					<text class="action-desc">随机题库</text>
				</view>
				<view class="action" @click="toQuiz('', 'favorite')">
					<text class="action-label">收藏刷题</text>
					<text class="action-desc">练收藏</text>
				</view>
				<view v-if="isAdmin" class="action" @click="toEditor('text')">
					<text class="action-label">文本导入</text>
					<text class="action-desc">贴文本生成题</text>
				</view>
				<view v-if="isAdmin" class="action" @click="toEditor('image')">
					<text class="action-label">拍照导入</text>
					<text class="action-desc">识别试卷</text>
				</view>
				<view class="action" @click="toQuiz('', 'wrong')">
					<text class="action-label">错题重练</text>
					<text class="action-desc">针对弱项</text>
				</view>
				<view v-if="isAdmin" class="action alt" @click="toManager">
					<text class="action-label">题库管理</text>
					<text class="action-desc">增删改查</text>
				</view>
				<view class="action neutral" @click="toProfile">
					<text class="action-label">我的</text>
					<text class="action-desc">登录 / 账户</text>
				</view>
			</view>
		</view>

		<view class="card">
			<text class="card-title">最近题库</text>
			<view v-if="loading" class="empty">加载中...</view>
			<view v-else-if="banks.length === 0" class="empty">暂无数据，先导入一套题吧。</view>
			<view v-else class="bank-list">
				<view v-for="bank in banks" :key="bank.id" class="bank-item">
					<view>
						<text class="bank-title">{{ bank.title }}</text>
						<text class="bank-desc">{{ bank.description || '暂无描述' }}</text>
					</view>
					<button class="mini-btn" size="mini" @click="toQuiz(bank.id)">刷题</button>
				</view>
			</view>
		</view>

		<view class="card git-card" @click="openGit">
			<view class="git-icon">🐱‍💻</view>
			<view>
				<text class="card-title">GitHub</text>
				<text class="git-link">查看代码仓库</text>
			</view>
		</view>
	</view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { fetchBanks, getRole, getToken } from '../../services/api'

const banks = ref([])
const loading = ref(false)
const role = ref(getRole() || '')
const isAdmin = computed(() => role.value === 'admin')

const loadBanks = async () => {
  role.value = getRole() || ''
  if (!getToken()) {
    banks.value = []
    return
  }
  loading.value = true
  try {
    const res = await fetchBanks()
    banks.value = res || []
  } catch (err) {
    uni.showToast({ title: err.message || '题库加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

onShow(loadBanks)

const toQuiz = (bankId, mode = 'random') => {
  uni.navigateTo({ url: `/pages/quiz/index?bankId=${bankId || ''}&mode=${mode}` })
}

const toEditor = (mode) => {
  uni.navigateTo({ url: `/pages/editor/add?mode=${mode}` })
}

const toManager = () => {
  uni.navigateTo({ url: '/pages/manager/index' })
}

const toProfile = () => {
  uni.navigateTo({ url: '/pages/profile/index' })
}

const openGit = () => {
  const url = 'https://github.com/wzr4ai/quiz-copilot'
  /* #ifdef H5 */
  window.open(url, '_blank')
  /* #endif */
  /* #ifndef H5 */
  uni.setClipboardData({
    data: url,
    success: () => uni.showToast({ title: '链接已复制，可在浏览器打开', icon: 'none' }),
  })
  /* #endif */
}
</script>

<style>
.page {
	padding: 32rpx;
	display: flex;
	flex-direction: column;
	gap: 24rpx;
	min-height: 100vh;
	background: linear-gradient(180deg, #f7faff 0%, #ffffff 80%);
}

.hero {
	padding: 40rpx 32rpx;
	border-radius: 24rpx;
	background: #0f172a;
	color: #f8fafc;
	display: flex;
	align-items: center;
	justify-content: space-between;
}

.eyebrow {
	font-size: 24rpx;
	letter-spacing: 2rpx;
	color: #94a3b8;
}

.title {
	display: block;
	font-size: 48rpx;
	font-weight: 700;
	margin-top: 12rpx;
}

.subtitle {
	display: block;
	font-size: 28rpx;
	margin-top: 8rpx;
	color: #cbd5e1;
}

.card {
	background: #ffffff;
	border-radius: 18rpx;
	padding: 24rpx;
	box-shadow: 0 6rpx 24rpx rgba(15, 23, 42, 0.06);
}

.card-title {
	font-size: 32rpx;
	font-weight: 600;
	color: #0f172a;
}

.quick-actions .action-grid {
	margin-top: 18rpx;
	display: grid;
	grid-template-columns: repeat(2, 1fr);
	gap: 16rpx;
}

.action {
	background: #0ea5e9;
	color: #f8fafc;
	border-radius: 16rpx;
	padding: 20rpx 16rpx;
	display: flex;
	flex-direction: column;
	gap: 8rpx;
	box-shadow: 0 8rpx 24rpx rgba(14, 165, 233, 0.2);
}

.action-label {
	font-size: 28rpx;
	font-weight: 600;
}

.action-desc {
	font-size: 24rpx;
	color: #e0f2fe;
}

.action.alt {
	background: #10b981;
	box-shadow: 0 8rpx 24rpx rgba(16, 185, 129, 0.2);
}

.action.neutral {
	background: #6366f1;
	box-shadow: 0 8rpx 24rpx rgba(99, 102, 241, 0.2);
}

.git-card {
	display: flex;
	align-items: center;
	gap: 12rpx;
	cursor: pointer;
}

.git-icon {
	font-size: 36rpx;
}

.bank-list {
	margin-top: 16rpx;
	display: flex;
	flex-direction: column;
	gap: 12rpx;
}

.bank-item {
	display: flex;
	justify-content: space-between;
	align-items: center;
	padding: 16rpx;
	border: 1rpx solid #e2e8f0;
	border-radius: 14rpx;
}

.bank-title {
	display: block;
	font-size: 28rpx;
	font-weight: 600;
	color: #0f172a;
}

.bank-desc {
	display: block;
	font-size: 24rpx;
	color: #64748b;
	margin-top: 6rpx;
}

.mini-btn {
	background: #0ea5e9;
	color: #ffffff;
}

.empty {
	margin-top: 16rpx;
	color: #94a3b8;
	font-size: 24rpx;
}
</style>

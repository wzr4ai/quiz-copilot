<template>
	<view class="page">
		<view class="card center">
			<text class="title">本次得分</text>
			<text class="score">{{ result.score }}</text>
			<text class="desc">正确 {{ result.correct_count }}/{{ result.total }}</text>
		</view>

		<view class="card" v-if="result.wrong_questions && result.wrong_questions.length">
			<text class="card-title">错题记录</text>
			<view class="wrong" v-for="item in result.wrong_questions" :key="item.question.id">
				<text class="q">{{ item.question.content }}</text>
				<text class="meta">我的答案：{{ item.user_answer || '未作答' }}</text>
				<text class="meta">参考答案：{{ item.correct_answer }}</text>
			</view>
		</view>

		<view class="actions">
			<button class="primary" @click="toHome">返回首页</button>
			<button class="ghost" @click="retry">再刷一遍</button>
			<button
				class="ghost"
				:disabled="!result.bankId || !(result.wrong_questions && result.wrong_questions.length)"
				@click="retryWrong"
			>
				错题重练
			</button>
		</view>
	</view>
</template>

<script setup>
import { onShow } from '@dcloudio/uni-app'
import { ref } from 'vue'

const result = ref({ score: 0, total: 0, correct_count: 0, wrong_questions: [], bankId: '' })

onShow(() => {
  const data = uni.getStorageSync('quizResult')
  if (data) {
    result.value = data
  }
})

const toHome = () => {
  uni.reLaunch({ url: '/pages/index/index' })
}

const retry = () => {
  uni.navigateTo({ url: `/pages/quiz/index?bankId=${result.value.bankId || ''}` })
}

const retryWrong = () => {
  if (!result.value.bankId) {
    return uni.showToast({ title: '缺少题库信息', icon: 'none' })
  }
  uni.navigateTo({ url: `/pages/quiz/index?bankId=${result.value.bankId}&mode=wrong` })
}
</script>

<style>
.page {
	min-height: 100vh;
	padding: 32rpx;
	background: #f8fafc;
	display: flex;
	flex-direction: column;
	gap: 20rpx;
}

.card {
	background: #ffffff;
	border-radius: 18rpx;
	padding: 28rpx;
	box-shadow: 0 6rpx 24rpx rgba(15, 23, 42, 0.06);
}

.center {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 12rpx;
}

.title {
	font-size: 32rpx;
	font-weight: 700;
	color: #0f172a;
}

.score {
	font-size: 72rpx;
	font-weight: 800;
	color: #0ea5e9;
}

.desc {
	color: #64748b;
	font-size: 26rpx;
}

.actions {
	display: grid;
	grid-template-columns: repeat(3, 1fr);
	gap: 10rpx;
	margin-top: auto;
}

.primary {
	background: #0ea5e9;
	color: #ffffff;
	border: none;
}

.ghost {
	background: #e2e8f0;
	color: #0f172a;
	border: none;
}

.card-title {
	font-size: 30rpx;
	font-weight: 700;
	color: #0f172a;
}

.wrong {
	margin-top: 12rpx;
	padding-top: 12rpx;
	border-top: 1rpx solid #e2e8f0;
	display: flex;
	flex-direction: column;
	gap: 6rpx;
}

.wrong .q {
	color: #0f172a;
	font-weight: 600;
}

.wrong .meta {
	color: #64748b;
	font-size: 24rpx;
}
</style>

<template>
	<view class="page">
		<view class="avatar-block">
			<view class="avatar">AI</view>
			<view>
				<text class="name">SmartQuiz 用户</text>
				<text class="subtitle">欢迎回来</text>
			</view>
		</view>

		<view class="card">
			<text class="card-title">学习数据</text>
			<view class="stats">
				<view class="stat">
					<text class="stat-value">23</text>
					<text class="stat-label">完成练习</text>
				</view>
				<view class="stat">
					<text class="stat-value">4</text>
					<text class="stat-label">错题待复习</text>
				</view>
				<view class="stat">
					<text class="stat-value">98</text>
					<text class="stat-label">最高分</text>
				</view>
			</view>
		</view>

		<view class="card">
			<text class="card-title">设置</text>
			<view class="list">
				<view class="item" @click="openPlaceholder('account')">
					<text>账号与安全</text>
					<text class="arrow">></text>
				</view>
				<view class="item" @click="openPlaceholder('notifications')">
					<text>提醒设置</text>
					<text class="arrow">></text>
				</view>
			</view>
		</view>
	</view>
</template>

<script setup>
const openPlaceholder = (section) => {
  uni.showToast({ title: `${section} 敬请期待`, icon: 'none' })
}
</script>

<style>
.page {
	min-height: 100vh;
	padding: 24rpx;
	display: flex;
	flex-direction: column;
	gap: 16rpx;
	background: #f8fafc;
}

.avatar-block {
	display: flex;
	align-items: center;
	gap: 16rpx;
}

.avatar {
	width: 96rpx;
	height: 96rpx;
	border-radius: 50%;
	background: #0ea5e9;
	color: #ffffff;
	display: flex;
	align-items: center;
	justify-content: center;
	font-weight: 700;
	font-size: 32rpx;
}

.name {
	font-size: 34rpx;
	color: #0f172a;
	font-weight: 700;
}

.subtitle {
	display: block;
	color: #64748b;
	font-size: 24rpx;
}

.card {
	background: #ffffff;
	border-radius: 18rpx;
	padding: 20rpx;
	box-shadow: 0 6rpx 24rpx rgba(15, 23, 42, 0.04);
}

.card-title {
	font-size: 30rpx;
	font-weight: 700;
	color: #0f172a;
}

.stats {
	display: grid;
	grid-template-columns: repeat(3, 1fr);
	margin-top: 16rpx;
	gap: 12rpx;
}

.stat {
	background: #f8fafc;
	border-radius: 14rpx;
	padding: 16rpx;
	text-align: center;
}

.stat-value {
	font-size: 34rpx;
	font-weight: 800;
	color: #0ea5e9;
}

.stat-label {
	display: block;
	margin-top: 6rpx;
	color: #64748b;
	font-size: 24rpx;
}

.list {
	margin-top: 12rpx;
}

.item {
	display: flex;
	justify-content: space-between;
	align-items: center;
	padding: 14rpx 0;
	border-bottom: 1rpx solid #e2e8f0;
	color: #0f172a;
}

.arrow {
	color: #94a3b8;
}
</style>

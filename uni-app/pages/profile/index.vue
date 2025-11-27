<template>
	<view class="page">
		<view class="avatar-block">
			<view class="avatar">AI</view>
			<view>
				<text class="name">{{ token ? username || '已登录用户' : 'SmartQuiz' }}</text>
				<text class="subtitle">
					{{ token ? (role === 'admin' ? '管理员' : '普通用户') : '请先登录' }}
				</text>
			</view>
		</view>

		<view class="card" v-if="!token">
			<text class="card-title">登录 / 注册</text>
			<input v-model="username" class="input" placeholder="用户名" />
			<input v-model="password" class="input" placeholder="密码" password />
			<view class="actions">
				<button class="primary" :loading="loading" @click="handleUnified">登录 / 注册</button>
			</view>
		</view>

		<view class="card" v-else>
			<text class="card-title">账号</text>
			<text class="hint">用户名：{{ username }}</text>
			<text class="hint">角色：{{ role === 'admin' ? '管理员' : '用户' }}</text>
			<view class="actions">
				<button class="ghost danger" @click="handleLogout">退出登录</button>
			</view>
		</view>

		<view class="card">
			<text class="card-title">学习数据</text>
			<view class="stats">
				<view class="stat">
					<text class="stat-value">—</text>
					<text class="stat-label">完成练习</text>
				</view>
				<view class="stat">
					<text class="stat-value">—</text>
					<text class="stat-label">错题待复习</text>
				</view>
				<view class="stat">
					<text class="stat-value">—</text>
					<text class="stat-label">最高分</text>
				</view>
			</view>
		</view>
	</view>
</template>

<script setup>
import { ref } from 'vue'
import { clearToken, getRole, getToken, getUsername, login, register, setAuth } from '../../services/api'

const username = ref(getUsername() || '')
const password = ref('')
const token = ref(getToken())
const role = ref(getRole() || '')
const loading = ref(false)

const handleUnified = async () => {
  if (!username.value || !password.value) {
    return uni.showToast({ title: '请输入账号密码', icon: 'none' })
  }
  loading.value = true
  try {
    // 尝试直接登录
    const res = await login({ username: username.value, password: password.value })
    token.value = getToken()
    role.value = res.role
    uni.showToast({ title: '登录成功', icon: 'success' })
  } catch (err) {
    // 登录失败，询问是否注册
    const modal = await uni.showModal({
      title: '未找到账号',
      content: '该账号不存在，是否立即注册并登录？',
      confirmText: '注册',
    })
    if (modal.confirm) {
      try {
        const res = await register({ username: username.value, password: password.value })
        token.value = getToken()
        role.value = res.role
        uni.showToast({ title: '注册成功并已登录', icon: 'success' })
      } catch (regErr) {
        uni.showToast({ title: regErr.message || '注册失败', icon: 'none' })
      }
    }
  }
  loading.value = false
}

const handleLogout = () => {
  clearToken()
  token.value = ''
  role.value = ''
  setAuth({ token: '', role: '', username: '' })
  uni.showToast({ title: '已退出', icon: 'none' })
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
	display: flex;
	flex-direction: column;
	gap: 12rpx;
}

.card-title {
	font-size: 30rpx;
	font-weight: 700;
	color: #0f172a;
}

.input {
	border: 1rpx solid #e2e8f0;
	border-radius: 12rpx;
	padding: 12rpx;
	background: #f8fafc;
}

.actions {
	display: flex;
	gap: 10rpx;
	flex-wrap: wrap;
	align-items: center;
}

.primary {
	background: #0ea5e9;
	color: #ffffff;
	border: none;
}

.ghost {
	background: #f8fafc;
	color: #0f172a;
	border: 1rpx dashed #cbd5e1;
}

.ghost.danger {
	color: #dc2626;
	border-color: #fecdd3;
}

.hint {
	color: #64748b;
	font-size: 24rpx;
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

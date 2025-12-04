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
			<text class="card-title">外观</text>
			<view class="theme-grid">
				<view
					v-for="option in themeOptions"
					:key="option.value"
					class="theme-tile"
					:class="{ active: themePreference === option.value }"
					@click="changeTheme(option.value)"
				>
					<view>
						<text class="theme-name">{{ option.label }}</text>
						<text class="theme-desc">{{ option.desc }}</text>
					</view>
					<text class="theme-pill">
						{{ option.value === 'system' ? `系统${activeTheme === 'dark' ? '深色' : '浅色'}` : '已选' }}
					</text>
				</view>
			</view>
			<text class="hint">当前外观：{{ activeThemeLabel }}</text>
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

		<view class="card">
			<text class="card-title">智能刷题</text>
			<view v-if="smartStatus">
				<text class="hint">状态：{{ smartStatusDisplay }}</text>
				<text class="hint" v-if="smartStatus.has_active">Session: {{ smartStatus.session_id }}</text>
				<text class="hint" v-if="smartStatus.has_active">
					组：{{ (smartStatus.current_group_index || 0) + 1 }} ｜ 轮次：{{ smartStatus.round || 1 }}
				</text>
				<text class="hint" v-if="typeof smartStatus.pending_wrong === 'number'">
					待巩固（当前组错/未答）：{{ smartStatus.pending_wrong }}
				</text>
				<text class="hint" v-if="typeof smartStatus.total_answered === 'number'">
					本组已答：{{ smartStatus.total_answered }} ｜ 正确：{{ smartStatus.total_correct || 0 }} ｜ 错误：{{ smartStatus.total_wrong || 0 }}
				</text>
				<text class="hint" v-if="typeof smartStatus.reinforce_remaining === 'number'">
					强化剩余：{{ smartStatus.reinforce_remaining }}
				</text>
				<text class="hint" v-if="typeof smartStatus.lowest_count_remaining === 'number'">
					当前轮最低计数剩余：{{ smartStatus.lowest_count_remaining }}
				</text>
				<view v-if="practiceStatsList.length" class="stats-list">
					<text class="hint">全局计数分布：</text>
					<view v-for="item in practiceStatsList" :key="item.count" class="stat-row">
						<text class="hint">计数 {{ item.count }}：{{ item.total }} 题</text>
					</view>
				</view>
				<view v-if="perBankStatsList.length" class="bank-list">
					<text class="hint">按题库分布：</text>
					<view class="bank-card" v-for="bank in perBankStatsList" :key="bank.bank_id">
						<view class="bank-head">
							<text class="bank-title">{{ bank.title }}</text>
							<text class="bank-sub">待刷(计数0)：{{ bank.lowest_count_remaining ?? 0 }}</text>
						</view>
						<view class="bank-buckets" v-if="bank.practice_count_stats && bank.keys.length">
							<view class="bucket-chip" v-for="level in bank.keys" :key="`${bank.bank_id}-${level}`">
								计数 {{ level }}：{{ bank.practice_count_stats[level] }}
							</view>
						</view>
					</view>
				</view>
			</view>
			<view v-else>
				<text class="hint">暂无智能刷题记录</text>
			</view>
			<view class="actions">
				<button class="ghost" @click="() => uni.navigateTo({ url: '/pages/quiz/smart' })">进入智能刷题</button>
				<button class="ghost" :loading="statsLoading" @click="loadSmartStatus">刷新数据</button>
				<button class="ghost danger" :disabled="!smartStatus?.has_active" @click="resetSmart">重置状态</button>
			</view>
		</view>
	</view>
</template>

<script setup>
import { onShow } from '@dcloudio/uni-app'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import {
  clearToken,
  fetchSmartPracticeStatus,
  getRole,
  getToken,
  getUsername,
  login,
  register,
  resetSmartPracticeState,
  setAuth,
} from '../../services/api'
import { getThemePreference, resolveTheme, setThemePreference, subscribeTheme } from '../../services/theme'

const username = ref(getUsername() || '')
const password = ref('')
const token = ref(getToken())
const role = ref(getRole() || '')
const loading = ref(false)
const smartStatus = ref(null)
const practiceStatsList = ref([])
const perBankStatsList = ref([])
const statsLoading = ref(false)
const smartStatusLabel = computed(() => {
  if (!smartStatus.value || !smartStatus.value.has_active) return '未开始'
  if (smartStatus.value.status === 'reinforce') return '错题强化'
  if (smartStatus.value.status === 'completed') return '已完成'
  return '进行中'
})
const realtimeLabel = computed(() => {
  if (!smartStatus.value) return ''
  if (smartStatus.value.realtime_analysis === false) return '考试模式'
  if (smartStatus.value.realtime_analysis === true) return '实时解析开启'
  return ''
})
const smartStatusDisplay = computed(() => {
  const base = smartStatusLabel.value
  const rt = realtimeLabel.value
  return rt ? `${base} ｜ ${rt}` : base
})
const themeOptions = [
  { value: 'system', label: '跟随系统', desc: '自动响应浏览器/设备主题' },
  { value: 'light', label: '浅色', desc: '保持明亮视图' },
  { value: 'dark', label: '深色', desc: '夜间护眼' },
]
const themePreference = ref(getThemePreference())
const activeTheme = ref(resolveTheme(themePreference.value))
const activeThemeLabel = computed(() =>
  activeTheme.value === 'dark' ? '深色模式' : '浅色模式',
)

let stopThemeWatch
onMounted(() => {
  stopThemeWatch = subscribeTheme((theme, preference) => {
    themePreference.value = preference
    activeTheme.value = theme
  })
})

onUnmounted(() => {
  stopThemeWatch?.()
})

const changeTheme = (value) => {
  const applied = setThemePreference(value)
  themePreference.value = value
  activeTheme.value = applied
  const msg =
    value === 'system'
      ? `已跟随系统（当前${applied === 'dark' ? '深色' : '浅色'}）`
      : `已切换到${applied === 'dark' ? '深色' : '浅色'}`
  uni.showToast({ title: msg, icon: 'none' })
}

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
    const msg = err?.message || ''
    if (msg.includes('密码错误')) {
      uni.showToast({ title: '密码错误，请重试', icon: 'none' })
      loading.value = false
      return
    }
    if (msg.includes('不存在')) {
      const modal = await uni.showModal({
        title: '账号不存在',
        content: '未找到该账号，是否注册并登录？',
        confirmText: '注册',
      })
      if (!modal.confirm) {
        loading.value = false
        return
      }
      try {
        const res = await register({ username: username.value, password: password.value })
        token.value = getToken()
        role.value = res.role
        uni.showToast({ title: '注册成功并已登录', icon: 'success' })
      } catch (regErr) {
        const rmsg = regErr.message || ''
        if (rmsg.includes('已存在')) {
          uni.showToast({ title: '账号已存在，请检查密码', icon: 'none' })
        } else {
          uni.showToast({ title: rmsg || '注册失败', icon: 'none' })
        }
      }
    } else {
      uni.showToast({ title: msg || '登录失败，请重试', icon: 'none' })
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

const loadSmartStatus = async () => {
  statsLoading.value = true
  if (!getToken()) {
    smartStatus.value = null
    practiceStatsList.value = []
    perBankStatsList.value = []
    statsLoading.value = false
    return
  }
  try {
    smartStatus.value = await fetchSmartPracticeStatus()
    const stats = smartStatus.value?.practice_count_stats || {}
    practiceStatsList.value = Object.keys(stats)
      .map((k) => ({ count: Number(k), total: stats[k] }))
      .sort((a, b) => a.count - b.count)
    const perBank = smartStatus.value?.per_bank_stats || []
    perBankStatsList.value = perBank.map((bank) => {
      const keys = Object.keys(bank.practice_count_stats || {})
        .map((k) => Number(k))
        .sort((a, b) => a - b)
      return { ...bank, keys }
    })
  } catch (err) {
    smartStatus.value = null
    practiceStatsList.value = []
    perBankStatsList.value = []
  } finally {
    statsLoading.value = false
  }
}

const resetSmart = async () => {
  const modal = await uni.showModal({
    title: '重置智能刷题',
    content: '将删除当前进行中的智能刷题状态（题组、进度），是否继续？',
    confirmText: '重置',
  })
  if (!modal.confirm) return
  try {
    await resetSmartPracticeState()
    smartStatus.value = null
    uni.showToast({ title: '已重置', icon: 'none' })
  } catch (err) {
    uni.showToast({ title: err.message || '重置失败', icon: 'none' })
  }
}

onShow(() => {
  token.value = getToken()
  role.value = getRole() || ''
  username.value = getUsername() || ''
  themePreference.value = getThemePreference()
  activeTheme.value = resolveTheme(themePreference.value)
  loadSmartStatus()
})
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

.stats-list {
	margin-top: 8rpx;
	display: flex;
	flex-direction: column;
	gap: 4rpx;
}
.bank-list {
	margin-top: 12rpx;
	display: flex;
	flex-direction: column;
	gap: 10rpx;
}
.bank-card {
	border: 1rpx solid #e2e8f0;
	border-radius: 12rpx;
	padding: 12rpx;
	background: #f8fafc;
}
.bank-head {
	display: flex;
	justify-content: space-between;
	align-items: center;
	gap: 8rpx;
	margin-bottom: 6rpx;
}
.bank-title {
	font-size: 28rpx;
	font-weight: 700;
	color: #0f172a;
}
.bank-sub {
	font-size: 24rpx;
	color: #475569;
}
.bank-buckets {
	display: flex;
	flex-wrap: wrap;
	gap: 8rpx;
}
.bucket-chip {
	background: #e2e8f0;
	color: #0f172a;
	padding: 6rpx 10rpx;
	border-radius: 999rpx;
	font-size: 22rpx;
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

.theme-grid {
	display: flex;
	flex-direction: column;
	gap: 10rpx;
}

.theme-tile {
	border: 1rpx solid #e2e8f0;
	border-radius: 14rpx;
	padding: 14rpx;
	display: flex;
	justify-content: space-between;
	align-items: center;
	gap: 8rpx;
	background: #f8fafc;
}

.theme-tile.active {
	border-color: #0ea5e9;
	box-shadow: 0 6rpx 16rpx rgba(14, 165, 233, 0.18);
}

.theme-name {
	font-size: 28rpx;
	font-weight: 700;
	color: #0f172a;
}

.theme-desc {
	display: block;
	margin-top: 4rpx;
	font-size: 24rpx;
	color: #64748b;
}

.theme-pill {
	background: #0ea5e9;
	color: #ffffff;
	padding: 6rpx 12rpx;
	border-radius: 999rpx;
	font-size: 22rpx;
}
</style>

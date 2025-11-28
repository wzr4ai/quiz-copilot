<template>
	<view class="page">
		<view class="header">
			<view>
				<text class="eyebrow">管理</text>
				<text class="title">合并题库</text>
				<text class="subtitle">勾选多个题库，生成一个新题库。</text>
			</view>
			<button class="ghost" size="mini" @click="goBack">返回管理</button>
		</view>

		<view class="card">
			<text class="card-title">新题库信息</text>
			<input v-model="form.title" placeholder="新题库名称" class="input" />
			<input v-model="form.description" placeholder="描述（可选）" class="input" />
			<label class="switch-row">
				<text>公开题库</text>
				<switch :checked="form.is_public" @change="(e) => (form.is_public = e.detail.value)" />
			</label>
		</view>

		<view class="card">
			<view class="card-title-row">
				<text class="card-title">选择要合并的题库</text>
				<text class="hint">建议至少选择两个题库</text>
			</view>
			<view v-if="loading" class="empty">加载中...</view>
			<view v-else-if="!banks.length" class="empty">暂无题库可合并。</view>
			<checkbox-group v-else :value="selectedIds.map(String)" @change="onSelect">
				<label v-for="bank in banks" :key="bank.id" class="bank-item">
					<checkbox :value="String(bank.id)" />
					<view class="bank-info">
						<text class="bank-title">{{ bank.title }}</text>
						<text class="bank-desc">{{ bank.description || '暂无描述' }}</text>
					</view>
					<text class="arrow">▸</text>
				</label>
			</checkbox-group>
		</view>

		<button class="primary" :loading="merging" @click="submitMerge">合并选中题库</button>
	</view>
</template>

<script setup>
import { onLoad } from '@dcloudio/uni-app'
import { ref } from 'vue'
import { fetchBanks, getRole, getToken, mergeBanks } from '../../services/api'

const banks = ref([])
const loading = ref(false)
const merging = ref(false)
const selectedIds = ref([])
const form = ref({
  title: '',
  description: '',
  is_public: false,
})

const ensureAdmin = () => {
  const role = getRole()
  if (!getToken() || role !== 'admin') {
    uni.showModal({
      title: '无权限',
      content: '请使用管理员账号登录后再访问此功能。',
      showCancel: false,
      success: () => {
        uni.switchTab({ url: '/pages/index/index' })
      },
    })
    return false
  }
  return true
}

const loadBanks = async () => {
  if (!ensureAdmin()) return
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

onLoad(loadBanks)

const onSelect = (e) => {
  selectedIds.value = (e.detail.value || []).map((val) => Number(val))
}

const submitMerge = async () => {
  if (!form.value.title.trim()) {
    return uni.showToast({ title: '请填写新题库名称', icon: 'none' })
  }
  if (selectedIds.value.length < 2) {
    return uni.showToast({ title: '请至少选择两个题库', icon: 'none' })
  }
  merging.value = true
  try {
    const payload = {
      title: form.value.title.trim(),
      description: form.value.description,
      is_public: form.value.is_public,
      source_bank_ids: selectedIds.value,
    }
    const res = await mergeBanks(payload)
    await uni.showModal({
      title: '合并完成',
      content: `新题库「${res.bank.title}」已生成，共合并 ${res.merged_questions} 题。`,
      showCancel: false,
    })
    uni.navigateBack({ delta: 1 })
  } catch (err) {
    uni.showToast({ title: err.message || '合并失败', icon: 'none' })
  } finally {
    merging.value = false
  }
}

const goBack = () => {
  uni.navigateBack({ delta: 1 })
}
</script>

<style>
.page {
	padding: 24rpx;
	display: flex;
	flex-direction: column;
	gap: 20rpx;
	background: #f8fafc;
	min-height: 100vh;
}

.header {
	display: flex;
	align-items: center;
	justify-content: space-between;
}

.eyebrow {
	font-size: 24rpx;
	color: #64748b;
}

.title {
	display: block;
	font-size: 40rpx;
	font-weight: 700;
	color: #0f172a;
	margin-top: 8rpx;
}

.subtitle {
	display: block;
	font-size: 26rpx;
	color: #475569;
	margin-top: 6rpx;
}

.card {
	background: #ffffff;
	border-radius: 16rpx;
	padding: 20rpx;
	box-shadow: 0 4rpx 18rpx rgba(15, 23, 42, 0.06);
}

.card-title {
	font-size: 30rpx;
	font-weight: 600;
	color: #0f172a;
	margin-bottom: 12rpx;
	display: block;
}

.card-title-row {
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 8rpx;
}

.hint {
	font-size: 24rpx;
	color: #94a3b8;
}

.input {
	width: 100%;
	padding: 18rpx;
	border: 1rpx solid #e2e8f0;
	border-radius: 12rpx;
	margin-bottom: 12rpx;
	background: #f8fafc;
}

.switch-row {
	display: flex;
	justify-content: space-between;
	align-items: center;
	padding: 12rpx 0;
}

.bank-item {
	display: flex;
	align-items: center;
	padding: 16rpx 0;
	border-bottom: 1rpx solid #e2e8f0;
}

.bank-item:last-child {
	border-bottom: none;
}

.bank-info {
	flex: 1;
	margin-left: 12rpx;
}

.bank-title {
	display: block;
	font-size: 30rpx;
	color: #0f172a;
}

.bank-desc {
	display: block;
	font-size: 24rpx;
	color: #64748b;
	margin-top: 4rpx;
}

.arrow {
	color: #cbd5e1;
	font-size: 24rpx;
}

.primary {
	margin-top: 8rpx;
	background: linear-gradient(90deg, #0ea5e9, #2563eb);
	color: #ffffff;
	border: none;
	border-radius: 12rpx;
	padding: 16rpx;
}

.ghost {
	background: #e2e8f0;
	color: #0f172a;
	border: none;
	border-radius: 12rpx;
	padding: 10rpx 16rpx;
}

.empty {
	color: #94a3b8;
	font-size: 26rpx;
	padding: 12rpx 0;
}
</style>

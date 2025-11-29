<template>
  <view class="page">
    <view class="card">
      <text class="title">按关键字搜索题目（仅管理员）</text>
      <view class="row">
        <input v-model="keyword" class="input" placeholder="输入题干/答案关键字" />
        <button class="primary" :loading="loading" @click="doSearch">搜索</button>
      </view>
      <view v-if="error" class="warn">{{ error }}</view>
      <view v-else-if="!results.length && !loading" class="empty">暂无结果</view>
    </view>

    <view v-for="item in results" :key="item.id" class="card result-card">
      <view class="row space-between">
        <text class="meta">#{{ item.id }} ｜ 题库：{{ bankName(item.bank_id) }}</text>
        <button class="ghost mini" @click="goEdit(item.id)">编辑</button>
      </view>
      <text class="content">{{ item.content }}</text>
      <view v-if="item.options?.length" class="options">
        <view v-for="opt in item.options" :key="opt.key" class="option-line">
          <text class="opt-key">{{ opt.key }}</text>
          <text class="opt-text">{{ opt.text }}</text>
        </view>
      </view>
      <text class="meta">答案：{{ item.standard_answer || '—' }}</text>
      <text class="meta">解析：{{ item.analysis || '—' }}</text>
    </view>
  </view>
</template>

<script setup>
import { onLoad } from '@dcloudio/uni-app'
import { ref } from 'vue'
import { adminSearchQuestions, fetchBanks, getToken, getRole } from '../../services/api'

const keyword = ref('')
const loading = ref(false)
const results = ref([])
const error = ref('')
const banks = ref([])

const bankName = (id) => {
  const b = banks.value.find((x) => x.id === id)
  return b ? b.title : `题库 ${id}`
}

const loadBanks = async () => {
  try {
    banks.value = await fetchBanks()
  } catch {
    banks.value = []
  }
}

const doSearch = async () => {
  error.value = ''
  results.value = []
  if (!keyword.value.trim()) {
    error.value = '请输入关键字'
    return
  }
  loading.value = true
  try {
    results.value = await adminSearchQuestions(keyword.value.trim(), 200)
  } catch (err) {
    error.value = err.message || '搜索失败'
  } finally {
    loading.value = false
  }
}

const goEdit = (qid) => {
  uni.navigateTo({ url: `/pages/manager/qid?qid=${qid}` })
}

onLoad(async () => {
  if (!getToken()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    setTimeout(() => uni.switchTab({ url: '/pages/index/index' }), 800)
    return
  }
  if (getRole() !== 'admin') {
    uni.showToast({ title: '需要管理员权限', icon: 'none' })
    setTimeout(() => uni.switchTab({ url: '/pages/index/index' }), 800)
    return
  }
  await loadBanks()
})
</script>

<style>
.page {
  min-height: 100vh;
  background: #f8fafc;
  padding: 16rpx;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}
.card {
  background: #fff;
  border-radius: 14rpx;
  padding: 16rpx;
  border: 1rpx solid #e2e8f0;
  display: flex;
  flex-direction: column;
  gap: 10rpx;
}
.title {
  font-size: 32rpx;
  font-weight: 700;
}
.row {
  display: flex;
  align-items: center;
  gap: 10rpx;
}
.space-between {
  justify-content: space-between;
}
.input {
  flex: 1;
  border: 1rpx solid #e2e8f0;
  border-radius: 10rpx;
  padding: 12rpx;
}
.primary {
  background: #0ea5e9;
  color: #fff;
  border: none;
  padding: 12rpx 16rpx;
  border-radius: 12rpx;
}
.ghost {
  border: 1rpx solid #cbd5e1;
  background: #fff;
  color: #0f172a;
}
.mini {
  padding: 8rpx 12rpx;
}
.warn {
  color: #ef4444;
}
.empty {
  color: #94a3b8;
}
.result-card .content {
  font-size: 30rpx;
  color: #0f172a;
}
.meta {
  color: #64748b;
  font-size: 26rpx;
}
.options {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}
.option-line {
  display: flex;
  gap: 8rpx;
}
.opt-key {
  font-weight: 700;
}
</style>

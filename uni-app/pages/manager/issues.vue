<template>
  <view class="page">
    <view class="card">
      <text class="title">疑似错题列表</text>
      <view v-if="loading" class="empty">加载中...</view>
      <view v-else-if="error" class="warn">{{ error }}</view>
      <view v-else-if="!entries.length" class="empty">暂无记录</view>
      <picker mode="selector" :range="entries" range-key="label" @change="onSelect" v-if="entries.length">
        <view class="picker">
          <text>{{ currentLabel }}</text>
          <text class="arrow">▼</text>
        </view>
      </picker>
    </view>

    <view v-if="question.id" class="card">
      <text class="meta">题库：{{ bankLabel }}</text>
      <text class="meta warn">Reason: {{ currentReason }}</text>
      <text class="meta">状态：{{ current?.status || 'pending' }}</text>
      <textarea v-model="question.content" class="textarea" placeholder="题干" />
      <view v-if="question.type !== 'short_answer'" class="options">
        <view v-for="(opt, idx) in question.options" :key="idx" class="option">
          <text class="opt-key">{{ opt.key }}</text>
          <input v-model="opt.text" class="opt-input" />
          <button size="mini" class="ghost mini" @click="removeOption(idx)">-</button>
        </view>
        <button class="ghost mini" @click="addOption">添加选项</button>
      </view>
      <view v-if="question.type === 'choice_single'" class="options">
        <view v-for="(opt, idx) in question.options" :key="`ans-${idx}`" class="option">
          <radio :value="opt.key" :checked="question.standard_answer === opt.key" @change="() => setSingleAnswer(opt.key)" />
          <text class="opt-text">{{ opt.key }}. {{ opt.text || '未填写' }}</text>
        </view>
      </view>
      <view v-else-if="question.type === 'choice_multi'" class="options">
        <view v-for="(opt, idx) in question.options" :key="`ans-${idx}`" class="option">
          <checkbox
            :value="opt.key"
            :checked="isMultiChecked(opt.key)"
            @change="() => toggleMultiAnswer(opt.key)"
          />
          <text class="opt-text">{{ opt.key }}. {{ opt.text || '未填写' }}</text>
        </view>
        <text class="hint">多选可勾选多个作为正确答案</text>
      </view>
      <view v-else class="row">
        <text class="label">答案</text>
        <input v-model="question.standard_answer" class="input" placeholder="答案" />
      </view>
      <textarea v-model="question.analysis" class="textarea" placeholder="解析（可选）" />
      <button class="primary" :loading="saving" @click="save">保存修改</button>
      <view class="actions">
        <button class="ghost mini" @click="updateIssueStatus('verified_ok')">已核查无误</button>
        <button class="ghost mini" @click="updateIssueStatus('corrected')">已核查修正</button>
      </view>
    </view>
  </view>
</template>

<script setup>
import { onLoad } from '@dcloudio/uni-app'
import { ref, computed } from 'vue'
import { adminFetchIssueQuestions, adminGetQuestionById, fetchBanks, updateQuestionApi, getToken, getRole, adminUpdateIssue } from '../../services/api'

const entries = ref([])
const loading = ref(false)
const error = ref('')
const current = ref(null)
const question = ref({ id: null, bank_id: null, type: 'choice_single', content: '', options: [], standard_answer: '', analysis: '' })
const saving = ref(false)
const banks = ref([])

const currentLabel = computed(() => {
  if (!current.value) return '选择一条记录'
  return current.value.label
})
const currentReason = computed(() => current.value?.reason || '')
const bankLabel = computed(() => {
  const found = banks.value.find((b) => b.id === question.value.bank_id)
  return found ? found.title : `题库 ${question.value.bank_id}`
})

const loadBanks = async () => {
  try {
    banks.value = await fetchBanks()
  } catch {
    banks.value = []
  }
}

const onSelect = async (e) => {
  const idx = e.detail.value
  current.value = entries.value[idx]
  await loadQuestion(current.value.qid)
}

const loadQuestion = async (qid) => {
  loading.value = true
  try {
    const data = await adminGetQuestionById(qid)
    question.value = { ...data, options: data.options || [] }
  } catch (err) {
    error.value = err.message || '加载失败'
  } finally {
    loading.value = false
  }
}

const setSingleAnswer = (key) => {
  question.value.standard_answer = key
}
const isMultiChecked = (key) => {
  return question.value.standard_answer.split(',').map((s) => s.trim()).includes(key)
}
const toggleMultiAnswer = (key) => {
  const parts = question.value.standard_answer.split(',').map((s) => s.trim()).filter(Boolean)
  if (parts.includes(key)) {
    question.value.standard_answer = parts.filter((p) => p !== key).join(',')
  } else {
    question.value.standard_answer = [...parts, key].join(',')
  }
}
const addOption = () => {
  const nextKey = String.fromCharCode(65 + question.value.options.length)
  question.value.options.push({ key: nextKey, text: '' })
}
const removeOption = (idx) => {
  question.value.options.splice(idx, 1)
}

const save = async () => {
  if (!question.value.id) return
  saving.value = true
  try {
    await updateQuestionApi(question.value.id, {
      bank_id: question.value.bank_id,
      type: question.value.type,
      content: question.value.content,
      options: question.value.options,
      standard_answer: question.value.standard_answer,
      analysis: question.value.analysis,
    })
    uni.showToast({ title: '已保存', icon: 'success' })
  } catch (err) {
    uni.showToast({ title: err.message || '保存失败', icon: 'none' })
  } finally {
    saving.value = false
  }
}

const loadIssues = async () => {
  loading.value = true
  try {
    const data = await adminFetchIssueQuestions()
    entries.value = (data || []).map((item) => ({
      issue_id: item.id,
      qid: item.question?.id,
      status: item.status,
      reason: item.reason,
      question: item.question,
      label: `#${item.id} ${item.question?.content?.slice(0, 20) || ''}`,
    }))
  } catch (err) {
    error.value = err.message || '读取日志失败'
  } finally {
    loading.value = false
  }
}

const updateIssueStatus = async (status) => {
  if (!current.value?.issue_id) return
  saving.value = true
  try {
    await adminUpdateIssue(current.value.issue_id, { status })
    current.value.status = status
    uni.showToast({ title: '状态已更新', icon: 'success' })
  } catch (err) {
    uni.showToast({ title: err.message || '更新失败', icon: 'none' })
  } finally {
    saving.value = false
  }
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
  await loadIssues()
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
.meta {
  color: #64748b;
  font-size: 26rpx;
}
.picker {
  border: 1rpx solid #e2e8f0;
  padding: 12rpx;
  border-radius: 12rpx;
  display: flex;
  justify-content: space-between;
}
.arrow {
  color: #94a3b8;
}
.warn {
  color: #ef4444;
}
.empty {
  color: #94a3b8;
}
.textarea,
.input {
  width: 100%;
  border: 1rpx solid #e2e8f0;
  border-radius: 10rpx;
  padding: 12rpx;
}
.options {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}
.option {
  display: flex;
  align-items: center;
  gap: 8rpx;
}
.opt-key {
  width: 50rpx;
  font-weight: 700;
}
.opt-input {
  flex: 1;
  border: 1rpx solid #e2e8f0;
  border-radius: 10rpx;
  padding: 10rpx;
}
.opt-text {
  color: #0f172a;
}
.hint {
  color: #94a3b8;
  font-size: 24rpx;
}
.primary {
  background: #0ea5e9;
  color: #fff;
  border: none;
  padding: 12rpx;
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
</style>

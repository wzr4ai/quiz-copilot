<template>
  <view class="page">
    <view class="card">
      <view class="header">
        <text class="title">题目 ID：{{ qidDisplay }}</text>
        <text class="meta">题库：{{ bankLabel }}</text>
      </view>
      <view v-if="loading" class="empty">加载中...</view>
      <view v-else-if="error" class="warn">{{ error }}</view>
      <view v-else>
        <view class="row">
          <text class="label">题型</text>
          <view class="chips">
            <view
              v-for="type in questionTypes"
              :key="type.value"
              :class="['chip', question.type === type.value ? 'chip-active' : '']"
              @click="setType(type.value)"
            >
              <text class="chip-text">{{ type.label }}</text>
            </view>
          </view>
        </view>
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
      </view>
    </view>
  </view>
</template>

<script setup>
import { onLoad } from '@dcloudio/uni-app'
import { ref, computed } from 'vue'
import { adminGetQuestionById, updateQuestionApi, fetchBanks, getToken, getRole } from '../../services/api'

const qidDisplay = ref('')
const bankLabel = ref('')
const question = ref({
  id: null,
  bank_id: null,
  type: 'choice_single',
  content: '',
  options: [
    { key: 'A', text: '' },
    { key: 'B', text: '' },
  ],
  standard_answer: '',
  analysis: '',
})
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const banks = ref([])

const questionTypes = [
  { label: '单选', value: 'choice_single' },
  { label: '判断', value: 'choice_judgment' },
  { label: '多选', value: 'choice_multi' },
  { label: '简答', value: 'short_answer' },
]

const loadBanks = async () => {
  try {
    banks.value = await fetchBanks()
  } catch {
    banks.value = []
  }
}

const findBankLabel = (bankId) => {
  const found = banks.value.find((b) => b.id === bankId)
  return found ? found.title : `题库 ${bankId}`
}

const setType = (type) => {
  question.value.type = type
  if (type === 'short_answer') {
    question.value.options = []
    question.value.standard_answer = ''
  } else if (type === 'choice_judgment') {
    question.value.options = [
      { key: 'A', text: '正确' },
      { key: 'B', text: '错误' },
    ]
    if (!['A', 'B'].includes(question.value.standard_answer)) {
      question.value.standard_answer = 'A'
    }
  } else {
    if (!question.value.options?.length) {
      question.value.options = [
        { key: 'A', text: '' },
        { key: 'B', text: '' },
      ]
    }
  }
}

const addOption = () => {
  const nextKey = String.fromCharCode(65 + question.value.options.length)
  question.value.options.push({ key: nextKey, text: '' })
}

const removeOption = (idx) => {
  question.value.options.splice(idx, 1)
  if (question.value.type === 'choice_single' || question.value.type === 'choice_judgment') {
    if (!question.value.options.find((o) => o.key === question.value.standard_answer)) {
      question.value.standard_answer = ''
    }
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

const loadQuestion = async (qid) => {
  loading.value = true
  error.value = ''
  try {
    const data = await adminGetQuestionById(qid)
    question.value = { ...data, options: data.options || [] }
    bankLabel.value = findBankLabel(data.bank_id)
  } catch (err) {
    error.value = err.message || '加载失败'
  } finally {
    loading.value = false
  }
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

onLoad(async (opts) => {
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
  qidDisplay.value = opts.qid || ''
  await loadBanks()
  if (opts.qid) {
    await loadQuestion(opts.qid)
  } else {
    error.value = '缺少题目ID'
  }
})
</script>

<style>
.page {
  min-height: 100vh;
  background: #f8fafc;
  padding: 16rpx;
}
.card {
  background: #fff;
  border-radius: 14rpx;
  padding: 16rpx;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
  border: 1rpx solid #e2e8f0;
}
.header {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}
.title {
  font-size: 32rpx;
  font-weight: 700;
}
.meta {
  color: #64748b;
  font-size: 26rpx;
}
.row {
  display: flex;
  align-items: center;
  gap: 10rpx;
}
.label {
  width: 160rpx;
  color: #334155;
}
.chips {
  display: flex;
  gap: 10rpx;
  flex-wrap: wrap;
}
.chip {
  padding: 8rpx 14rpx;
  border-radius: 12rpx;
  border: 1rpx solid #cbd5e1;
  color: #0f172a;
  background: #f8fafc;
}
.chip-active {
  background: #0ea5e9;
  color: #fff;
  border-color: #0ea5e9;
}
.input,
.textarea {
  width: 100%;
  border: 1rpx solid #e2e8f0;
  border-radius: 10rpx;
  padding: 12rpx;
  font-size: 28rpx;
}
.textarea {
  min-height: 160rpx;
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
.empty {
  color: #94a3b8;
}
.warn {
  color: #ef4444;
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

<template>
	<view class="page">
		<view class="header">
			<view>
				<text class="title">练习中</text>
				<text class="meta">模式：{{ modeLabel }} ｜ 第 {{ currentIndex + 1 }} / {{ questions.length }} 题</text>
			</view>
			<view class="picker-group">
				<picker mode="selector" :range="banks" range-key="title" @change="onBankChange">
					<view class="picker">
						<text>{{ currentBankLabel }}</text>
						<text class="arrow">▼</text>
					</view>
				</picker>
				<button class="ghost small" :loading="loading" @click="initSession">刷新题目</button>
			</view>
		</view>
		<view class="toggles">
			<label class="switch-row">
				<text>实时显示解析</text>
				<switch :checked="realtime" @change="onRealtimeChange" />
			</label>
		</view>

		<view v-if="loading" class="empty">加载题目中...</view>
		<view v-else-if="!banks.length" class="empty">暂无题库，请先在录题中心或题库管理创建。</view>
		<view v-else-if="!currentQuestion" class="empty">暂无题目，先去录入吧。</view>

		<view class="card" v-else>
			<view class="card-top">
				<text class="question-type">{{ typeLabel(currentQuestion.type) }}</text>
				<view class="card-actions">
					<button class="ghost small" @click="toggleFavorite">
						{{ isFavorited ? '取消收藏' : '收藏' }}
					</button>
					<button v-if="isAdmin" class="edit-btn" size="mini" @click="startEdit(currentQuestion)">编辑</button>
				</view>
			</view>
			<text class="question-content">{{ currentQuestion.content }}</text>

			<view v-if="['choice_single', 'choice_judgment'].includes(currentQuestion.type)" class="options">
				<view
					v-for="opt in currentQuestion.options"
					:key="opt.key"
					class="option"
					:class="{ active: answers[currentQuestion.id] === opt.key }"
					@click="selectOption(currentQuestion.id, opt.key)"
				>
					<text class="opt-key">{{ opt.key }}</text>
					<text class="opt-text">{{ opt.text }}</text>
				</view>
			</view>

			<view v-else-if="currentQuestion.type === 'choice_multi'" class="options">
				<view
					v-for="opt in currentQuestion.options"
					:key="opt.key"
					class="option"
					:class="{ active: (multiSelections[currentQuestion.id] || []).includes(opt.key) }"
					@click="toggleMulti(currentQuestion.id, opt.key)"
				>
					<text class="opt-key">{{ opt.key }}</text>
					<text class="opt-text">{{ opt.text }}</text>
				</view>
				<button v-if="realtime" class="ghost small" @click="confirmMulti">确认</button>
				<view v-if="isAdmin && multiSelections[currentQuestion.id]?.length" class="admin-hint">
					<text class="hint">当前选择：{{ (multiSelections[currentQuestion.id] || []).join(',') }}</text>
				</view>
			</view>

			<view v-else class="textarea-wrap">
				<textarea
					v-model="answers[currentQuestion.id]"
					placeholder="输入你的答案..."
					class="textarea"
					@input="(e) => onTextInput(currentQuestion.id, e.detail.value)"
				/>
			</view>

			<view v-if="feedback[currentQuestion.id]" class="feedback">
				<text :class="['status', feedback[currentQuestion.id].correct ? 'ok' : 'bad']">
					{{ feedback[currentQuestion.id].correct ? '回答正确' : '回答错误' }}
				</text>
				<text class="hint">正确答案：{{ feedback[currentQuestion.id].correctAnswer }}</text>
				<text class="analysis">解析：{{ feedback[currentQuestion.id].analysis || '无' }}</text>
			</view>

			<view v-if="editingId === currentQuestion.id" class="edit-panel">
				<text class="label">修正题目</text>
				<textarea v-model="editForm.content" class="textarea tiny" />
				<view v-if="editForm.type === 'choice_single'" class="options">
					<view v-for="(opt, idx) in editForm.options" :key="idx" class="option">
						<text class="opt-key">{{ opt.key }}</text>
						<input class="opt-text" v-model="opt.text" placeholder="选项内容" />
					</view>
				</view>
				<input class="input" v-model="editForm.standard_answer" placeholder="标准答案" />
				<textarea class="textarea tiny" v-model="editForm.analysis" placeholder="解析（可选）" />
				<view class="edit-actions">
					<button class="ghost small" @click="cancelEdit">取消</button>
					<button class="primary small" :loading="savingEdit" @click="saveEdit">保存修正</button>
				</view>
			</view>
		</view>

		<view class="footer">
			<button class="ghost" @click="prev" :disabled="currentIndex === 0">上一题</button>
			<button class="primary" :loading="submitting" @click="next">
				{{ currentIndex === questions.length - 1 ? '提交' : '下一题' }}
			</button>
		</view>
	</view>
</template>

<script setup>
import { onLoad } from '@dcloudio/uni-app'
import { computed, reactive, ref } from 'vue'
import {
  favoriteQuestion,
  fetchBanks,
  fetchFavoriteQuestions,
  getRole,
  getToken,
  recordAnswer,
  startSession,
  submitSession,
  unfavoriteQuestion,
  updateQuestionApi,
} from '../../services/api'

const questions = ref([])
const answers = reactive({})
const multiSelections = reactive({})
const currentIndex = ref(0)
const sessionId = ref('')
const bankId = ref('')
const mode = ref('random')
const loading = ref(false)
const submitting = ref(false)
const editingId = ref(null)
const savingEdit = ref(false)
const banks = ref([])
const LAST_BANK_KEY = 'last_practice_bank_id'
const editForm = reactive({
  id: null,
  content: '',
  type: '',
  options: [],
  standard_answer: '',
  analysis: '',
})
const realtime = ref(false)
const feedback = reactive({})
const isFavorited = ref(false)
const role = ref(getRole() || '')
const isAdmin = computed(() => role.value === 'admin')
const isMemorize = computed(() => mode.value.startsWith('memorize'))

const currentQuestion = computed(() => questions.value[currentIndex.value])

const modeLabel = computed(() => {
  if (mode.value === 'wrong') return '错题重练'
  if (mode.value === 'favorite') return '收藏刷题'
  if (mode.value === 'ordered') return '顺序'
  if (mode.value === 'memorize') return '背题（顺序）'
  if (mode.value === 'memorize_wrong') return '背题（错题）'
  if (mode.value === 'memorize_favorite') return '背题（收藏）'
  return '随机'
})

const currentBankLabel = computed(() => {
  const found = banks.value.find((b) => b.id === bankId.value)
  return found ? found.title : '选择题库'
})

const typeLabel = (type) => {
  if (type === 'choice_single') return '单选题'
  if (type === 'choice_judgment') return '判断题'
  if (type === 'choice_multi') return '多选题'
  if (type === 'short_answer') return '简答题'
  return type
}

const loadBanks = async () => {
  try {
    const res = await fetchBanks()
    banks.value = res || []
    if (!bankId.value && banks.value.length) {
      const saved = uni.getStorageSync(LAST_BANK_KEY)
      const found = banks.value.find((b) => b.id === saved)
      bankId.value = found ? found.id : banks.value[0].id
    }
  } catch (err) {
    uni.showToast({ title: err.message || '题库加载失败', icon: 'none' })
  }
}

const initSession = async () => {
  if (!getToken()) {
    return uni.showToast({ title: '请先登录', icon: 'none' })
  }
  const requiresBank =
    (!isMemorize.value && mode.value !== 'favorite') ||
    (isMemorize.value && !mode.value.includes('wrong') && !mode.value.includes('favorite'))
  if (requiresBank && !bankId.value) {
    return uni.showToast({ title: '请先选择题库', icon: 'none' })
  }
  loading.value = true
  try {
    const res = await startSession(mode.value === 'favorite' ? '' : bankId.value, mode.value)
    sessionId.value = res.session_id
    questions.value = res.questions || []
    const savedIdx = getMemorizeIndex()
    currentIndex.value = isMemorize.value ? Math.min(savedIdx, Math.max(questions.value.length - 1, 0)) : 0
    if (isMemorize.value) {
      realtime.value = true
    } else {
      realtime.value = false
    }
    Object.keys(answers).forEach((key) => delete answers[key])
    Object.keys(multiSelections).forEach((key) => delete multiSelections[key])
    feedbackClear()
    questions.value.forEach((q) => {
      answers[q.id] = ''
      if (q.type === 'choice_multi') {
        multiSelections[q.id] = []
      }
    })
    if (isMemorize.value) {
      loadMemorizeState()
    }
    if (realtime.value) {
      questions.value.forEach((q) => {
        if (answers[q.id]) showFeedback(q.id)
      })
    }
    syncFavoriteStatus()
  } catch (err) {
    uni.showToast({ title: err.message || '加载题目失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

onLoad((options) => {
  bankId.value = options && options.bankId ? Number(options.bankId) : ''
  mode.value = (options && options.mode) || 'random'
  role.value = getRole() || ''
  if (isMemorize.value) {
    realtime.value = true
  }
  loadBanks().then(() => initSession())
})

const onBankChange = (event) => {
  const idx = Number(event.detail.value)
  const picked = banks.value[idx]
  if (picked) {
    bankId.value = picked.id
    uni.setStorageSync(LAST_BANK_KEY, bankId.value)
    initSession()
  }
}

const selectOption = (questionId, value) => {
  answers[questionId] = value
  if (isMemorize.value) saveMemorizeState()
  if (realtime.value) {
    showFeedback(questionId)
  }
}

const toggleMulti = (questionId, value) => {
  if (!multiSelections[questionId]) multiSelections[questionId] = []
  const idx = multiSelections[questionId].indexOf(value)
  if (idx >= 0) {
    multiSelections[questionId].splice(idx, 1)
  } else {
    multiSelections[questionId].push(value)
  }
}

const confirmMulti = () => {
  const q = currentQuestion.value
  if (!q) return
  answers[q.id] = normalizeMultiAnswer(multiSelections[q.id])
  if (isMemorize.value) saveMemorizeState()
  if (realtime.value) {
    showFeedback(q.id)
  } else {
    next()
  }
}

const recordCurrentAnswer = async () => {
  const q = currentQuestion.value
  if (!q) return
  if (q.type === 'choice_multi' && !answers[q.id]) {
    answers[q.id] = normalizeMultiAnswer(multiSelections[q.id])
  }
  const ans = answers[q.id]
  if (!ans) return
  try {
    await recordAnswer(q.id, ans)
  } catch (err) {
    // silently ignore to not block navigation, but can toast for debugging
  }
}

const next = async () => {
  await recordCurrentAnswer()
  if (currentIndex.value < questions.value.length - 1) {
    currentIndex.value += 1
    isFavorited.value = !!questions.value[currentIndex.value]?.is_favorited
    if (isMemorize.value) saveMemorizeIndex()
    return
  }
  await submit()
}

const submit = async () => {
  if (!sessionId.value) {
    return uni.showToast({ title: '暂无练习会话', icon: 'none' })
  }
  if (realtime.value && Object.keys(feedback).length < questions.value.length) {
    // ensure all answered before提交
    const unanswered = questions.value.find((q) => !feedback[q.id] && !answers[q.id])
    if (unanswered) {
      return uni.showToast({ title: '还有题目未作答', icon: 'none' })
    }
  }
  submitting.value = true
  try {
    const payload = {
      session_id: sessionId.value,
      answers: questions.value.map((q) => ({
        question_id: q.id,
        answer:
          q.type === 'choice_multi'
            ? normalizeMultiAnswer(answers[q.id] || multiSelections[q.id])
            : answers[q.id] || '',
      })),
    }
    const res = await submitSession(payload)
    uni.setStorageSync('quizResult', {
      ...res,
      bankId: bankId.value,
      mode: mode.value,
    })
    uni.navigateTo({ url: '/pages/quiz/result' })
  } catch (err) {
    uni.showToast({ title: err.message || '提交失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}

const prev = () => {
  if (currentIndex.value > 0) {
    currentIndex.value -= 1
    isFavorited.value = !!questions.value[currentIndex.value]?.is_favorited
    if (isMemorize.value) saveMemorizeIndex()
  }
}

const startEdit = (question) => {
  editingId.value = question.id
  editForm.id = question.id
  editForm.content = question.content
  editForm.type = question.type
  editForm.options = JSON.parse(JSON.stringify(question.options || []))
  editForm.standard_answer = question.standard_answer || ''
  editForm.analysis = question.analysis || ''
}

const cancelEdit = () => {
  editingId.value = null
}

const saveEdit = async () => {
  if (!editingId.value) return
  savingEdit.value = true
  try {
    const payload = {
      content: editForm.content,
      options: editForm.options,
      standard_answer: editForm.standard_answer,
      analysis: editForm.analysis,
    }
    const updated = await updateQuestionApi(editForm.id, payload)
    const idx = questions.value.findIndex((q) => q.id === updated.id)
    if (idx !== -1) {
      questions.value[idx] = updated
    }
    editingId.value = null
    uni.showToast({ title: '已保存修正', icon: 'none' })
  } catch (err) {
    uni.showToast({ title: err.message || '保存失败', icon: 'none' })
  } finally {
    savingEdit.value = false
  }
}

const showFeedback = (questionId) => {
  const q = questions.value.find((item) => item.id === questionId)
  if (!q) return
  const userAns = (answers[questionId] || '').trim()
  const correct = (q.standard_answer || '').trim()
  const normalize = (val, multi) => {
    if (multi) {
      return normalizeMultiAnswer(val.split(','))
    }
    return val.toUpperCase()
  }
  const normalizedUser = normalize(userAns, q.type === 'choice_multi')
  const normalizedCorrect = normalize(correct, q.type === 'choice_multi')
  feedback[questionId] = {
    correct: normalizedUser === normalizedCorrect && normalizedUser !== '',
    correctAnswer: correct || '未提供',
    analysis: q.analysis,
  }
}

const feedbackClear = () => {
  Object.keys(feedback).forEach((k) => delete feedback[k])
}

const onRealtimeChange = (e) => {
  realtime.value = !!(e?.detail?.value)
}

const onTextInput = (questionId, value) => {
  answers[questionId] = value
  if (isMemorize.value) saveMemorizeState()
}

const normalizeMultiAnswer = (vals) => {
  if (!vals) return ''
  const arr = Array.isArray(vals) ? vals : String(vals).split(',')
  return arr
    .join(',') // unify to comma string
    .replace(/\s+/g, ',') // replace spaces with commas
    .split(',')
    .map((s) => s.toString().trim().toUpperCase())
    .filter(Boolean)
    .sort()
    .join(',')
}

const MEMO_STATE_KEY = 'memorize_state'
const memorizeKey = () =>
  `${mode.value}:${mode.value.includes('favorite') ? 'all' : bankId.value || 'all'}`

const saveMemorizeState = () => {
  if (!isMemorize.value) return
  const data = uni.getStorageSync(MEMO_STATE_KEY) || {}
  const answersCopy = {}
  Object.keys(answers).forEach((k) => {
    answersCopy[k] = answers[k]
  })
  const multiCopy = {}
  Object.keys(multiSelections).forEach((k) => {
    multiCopy[k] = [...(multiSelections[k] || [])]
  })
  data[memorizeKey()] = {
    index: currentIndex.value,
    answers: answersCopy,
    multi: multiCopy,
  }
  uni.setStorageSync(MEMO_STATE_KEY, data)
}

const loadMemorizeState = () => {
  if (!isMemorize.value) return
  const data = uni.getStorageSync(MEMO_STATE_KEY) || {}
  const state = data[memorizeKey()]
  if (!state) return
  if (typeof state.index === 'number') {
    currentIndex.value = Math.min(state.index, Math.max(questions.value.length - 1, 0))
  }
  if (state.answers) {
    Object.keys(state.answers).forEach((k) => {
      answers[k] = state.answers[k]
    })
  }
  if (state.multi) {
    Object.keys(state.multi).forEach((k) => {
      multiSelections[k] = state.multi[k]
    })
  }
}

const MEMO_PROGRESS_KEY = 'memorize_progress'
const saveMemorizeIndex = () => {
  if (!isMemorize.value) return
  const data = uni.getStorageSync(MEMO_PROGRESS_KEY) || {}
  data[memorizeKey()] = currentIndex.value
  uni.setStorageSync(MEMO_PROGRESS_KEY, data)
}

const getMemorizeIndex = () => {
  if (!isMemorize.value) return 0
  const data = uni.getStorageSync(MEMO_PROGRESS_KEY) || {}
  const val = data[memorizeKey()]
  return typeof val === 'number' ? val : 0
}

const toggleFavorite = async () => {
  const q = currentQuestion.value
  if (!q) return
  try {
    if (isFavorited.value) {
      await unfavoriteQuestion(q.id)
      isFavorited.value = false
      q.is_favorited = false
    } else {
      await favoriteQuestion(q.id)
      isFavorited.value = true
      q.is_favorited = true
    }
  } catch (err) {
    uni.showToast({ title: err.message || '操作失败', icon: 'none' })
  }
}

const syncFavoriteStatus = () => {
  const current = questions.value[currentIndex.value]
  isFavorited.value = !!current?.is_favorited
}

</script>

<style>
.page {
	display: flex;
	flex-direction: column;
	gap: 20rpx;
	padding: 24rpx;
	min-height: 100vh;
	background: #f8fafc;
}

.header {
	display: flex;
	justify-content: space-between;
	align-items: baseline;
}

.title {
	font-size: 36rpx;
	font-weight: 700;
	color: #0f172a;
}

.meta {
	font-size: 24rpx;
	color: #64748b;
}

.toggles {
	display: flex;
	justify-content: flex-end;
}

.switch-row {
	display: flex;
	align-items: center;
	gap: 8rpx;
}

.picker-group {
	display: flex;
	align-items: center;
	gap: 10rpx;
}

.picker {
	background: #f8fafc;
	border: 1rpx solid #e2e8f0;
	border-radius: 12rpx;
	padding: 10rpx 14rpx;
	display: flex;
	align-items: center;
	gap: 6rpx;
}

.arrow {
	color: #94a3b8;
	font-size: 24rpx;
}

.card {
	background: #ffffff;
	border-radius: 18rpx;
	padding: 20rpx;
	box-shadow: 0 6rpx 24rpx rgba(15, 23, 42, 0.04);
	min-height: 520rpx;
	display: flex;
	flex-direction: column;
	gap: 16rpx;
}

.question-type {
	font-size: 24rpx;
	color: #0ea5e9;
	font-weight: 600;
}

.question-content {
	font-size: 32rpx;
	color: #0f172a;
	line-height: 1.6;
}

.card-actions {
	display: flex;
	gap: 10rpx;
	align-items: center;
}

.options {
	display: flex;
	flex-direction: column;
	gap: 12rpx;
}

.option {
	border: 1rpx solid #e2e8f0;
	border-radius: 14rpx;
	padding: 16rpx;
	display: flex;
	align-items: center;
	gap: 12rpx;
	background: #f8fafc;
}

.option.active {
	border-color: #0ea5e9;
	background: #e0f2fe;
}

.opt-key {
	width: 48rpx;
	height: 48rpx;
	border-radius: 50%;
	background: #0ea5e9;
	color: #ffffff;
	display: flex;
	align-items: center;
	justify-content: center;
	font-weight: 700;
}

.opt-text {
	flex: 1;
	color: #0f172a;
}

.textarea-wrap {
	flex: 1;
}

.textarea {
	width: 100%;
	min-height: 260rpx;
	border: 1rpx solid #e2e8f0;
	border-radius: 14rpx;
	padding: 16rpx;
	background: #f8fafc;
	box-sizing: border-box;
}

.feedback {
	border-top: 1rpx dashed #e2e8f0;
	padding-top: 12rpx;
	display: flex;
	flex-direction: column;
	gap: 6rpx;
}

.admin-hint .hint {
	color: #b45309;
	font-size: 24rpx;
}

.status {
	font-size: 26rpx;
	font-weight: 700;
}

.status.ok {
	color: #16a34a;
}

.status.bad {
	color: #dc2626;
}

.analysis {
	color: #475569;
	font-size: 24rpx;
}

.footer {
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 12rpx;
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

.small {
	padding: 12rpx 18rpx;
	font-size: 24rpx;
}

.empty {
	padding: 60rpx 0;
	text-align: center;
	color: #94a3b8;
}

.card-top {
	display: flex;
	justify-content: space-between;
	align-items: center;
}

.edit-btn {
	background: #f8fafc;
	color: #0f172a;
	border: 1rpx solid #e2e8f0;
}

.edit-panel {
	margin-top: 12rpx;
	padding: 12rpx;
	border: 1rpx dashed #cbd5e1;
	border-radius: 12rpx;
	display: flex;
	flex-direction: column;
	gap: 10rpx;
	background: #f8fafc;
}

.label {
	color: #475569;
	font-size: 24rpx;
}

.input {
	border: 1rpx solid #e2e8f0;
	border-radius: 12rpx;
	padding: 12rpx;
	background: #ffffff;
}

.textarea.tiny {
	min-height: 160rpx;
}

.edit-actions {
	display: flex;
	justify-content: flex-end;
	gap: 10rpx;
}
</style>

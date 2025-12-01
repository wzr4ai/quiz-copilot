<template>
  <view class="page">
    <view class="card" v-if="!group">
      <view class="card-header">
        <text class="title">智能刷题设置</text>
        <text class="hint">选择题库、题组数量与题型占比，保存后开始智能刷题。</text>
      </view>
      <view class="form-row">
        <text class="label">题库（可多选）</text>
        <checkbox-group @change="onBankSelect">
          <label v-for="bank in banks" :key="bank.id" class="checkbox">
            <checkbox :value="String(bank.id)" :checked="form.bankIds.includes(bank.id)" />
            <text>{{ bank.title }}</text>
          </label>
        </checkbox-group>
      </view>
      <view class="form-row">
        <text class="label">每组题目数量</text>
        <input class="input" type="number" v-model.number="form.targetCount" placeholder="默认 50" />
      </view>
      <view class="form-row">
        <text class="label">题型占比（总计 {{ ratioTotal }}%）</text>
        <view class="ratio-grid">
          <view v-for="opt in typeOptions" :key="opt.value" class="ratio-item">
            <text class="ratio-label">{{ opt.label }}</text>
            <input
              class="input"
              type="number"
              :placeholder="opt.defaultRatio"
              v-model.number="form.typeRatio[opt.value]"
            />
            <text class="ratio-unit">%</text>
          </view>
        </view>
      </view>
      <view class="form-row switch-row">
        <text class="label">实时解析</text>
        <switch :checked="form.realtimeAnalysis" @change="(e) => (form.realtimeAnalysis = !!e.detail.value)" />
      </view>
      <view class="actions">
        <button class="ghost" :loading="saving" @click="saveSettings">保存设置</button>
        <button class="primary" :loading="starting" @click="startSmart">开始智能刷题</button>
      </view>
    </view>

    <view class="card compact" v-if="group && group.questions && group.questions.length">
      <view class="card-header compact-header">
        <view class="header-left">
          <text class="title">第 {{ currentIndex + 1 }}/{{ group.questions.length }} 题</text>
          <text class="hint">Round {{ status.round || group.round }} · {{ group.mode === 'reinforce' ? '错题强化' : '正常' }}</text>
        </view>
        <view class="header-right">
          <view class="tag">
            剩余待刷：{{ remainingLabel }}
          </view>
        </view>
      </view>

        <view v-if="currentQuestion" class="question-card">
          <view class="question-head">
          <text class="type" :class="'type-' + currentQuestion.type">{{ typeLabel(currentQuestion.type) }}</text>
          <text v-if="isAdmin" class="qid">QID: {{ currentQuestion.id }}</text>
          <text v-if="group.mode === 'reinforce'" class="badge">强化</text>
          <button v-if="isAdmin" class="ghost small" @click="toggleEdit">
            {{ editMode ? '收起编辑' : '编辑' }}
          </button>
        </view>
        <text class="question-content">{{ currentQuestion.content }}</text>

        <view v-if="['choice_single', 'choice_judgment'].includes(currentQuestion.type)" class="options">
          <view
            v-for="opt in currentQuestion.options"
            :key="opt.key"
            class="option"
            :class="{ active: answers[currentQuestion.id] === opt.key, disabled: group.realtime_analysis && locked[currentQuestion.id] }"
            @click="!group.realtime_analysis || !locked[currentQuestion.id] ? submitOption(opt.key) : null"
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
            :class="{ active: (multiSelections[currentQuestion.id] || []).includes(opt.key), disabled: group.realtime_analysis && locked[currentQuestion.id] }"
            @click="group.realtime_analysis && locked[currentQuestion.id] ? null : toggleMulti(opt.key)"
          >
            <text class="opt-key">{{ opt.key }}</text>
            <text class="opt-text">{{ opt.text }}</text>
          </view>
          <button
            class="ghost small"
            :disabled="group.realtime_analysis && locked[currentQuestion.id] || !(multiSelections[currentQuestion.id] || []).length"
            @click="confirmMulti"
          >
            确认选择
          </button>
        </view>

        <view v-else class="textarea-wrap">
          <textarea
            class="textarea"
            v-model="answers[currentQuestion.id]"
            placeholder="输入答案"
            :disabled="group.realtime_analysis && locked[currentQuestion.id]"
            @blur="submitText"
          />
        </view>

        <view v-if="shouldShowFeedback" class="feedback">
          <text :class="['status', feedback[currentQuestion.id].is_correct ? 'ok' : 'bad']">
            {{ feedback[currentQuestion.id].is_correct ? '回答正确' : '回答错误' }}
          </text>
          <text class="hint">正确答案：{{ feedback[currentQuestion.id].standard_answer || '未提供' }}</text>
          <text class="analysis">解析：{{ feedback[currentQuestion.id].analysis || '未提供' }}</text>
          <text v-if="feedback[currentQuestion.id].counted" class="tag">已计入练习次数</text>
        </view>

        <view v-if="isAdmin && editMode" class="edit-panel">
          <text class="label">修正题目</text>
          <textarea class="textarea tiny" v-model="editForm.content" placeholder="题干" />
          <view v-if="editForm.type === 'choice_single' || editForm.type === 'choice_multi'" class="options">
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
        <view class="feedback-actions">
          <button class="ghost danger" size="mini" @click="openFeedback">题目有问题，反馈并跳过</button>
        </view>
      </view>

      <view class="footer">
        <button class="ghost" :disabled="currentIndex === 0" @click="prev">上一题</button>
        <button class="primary" :loading="jumping && isLastQuestion" @click="handleNext">
          {{ nextLabel }}
        </button>
      </view>
    </view>

    <view v-else class="empty">
      <text>尚未加载题组，保存设置后点击“开始智能刷题”。</text>
    </view>
  </view>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { onHide, onShow, onUnload } from '@dcloudio/uni-app'
import {
  answerSmartPracticeQuestion,
  fetchBanks,
  fetchCurrentSmartPracticeGroup,
  fetchSmartPracticeSettings,
  fetchSmartPracticeStatus,
  feedbackSmartPracticeQuestion,
  saveSmartPracticeSettings,
  startSmartPracticeSession,
  toggleSmartPracticeAnalysis,
  nextSmartPracticeGroup,
  getRole,
  updateQuestionApi,
} from '../../services/api'

const banks = ref([])
const status = reactive({
  has_active: false,
  session_id: null,
  status: null,
  current_group_index: null,
  round: null,
  realtime_analysis: null,
  pending_wrong: null,
})
const form = reactive({
  bankIds: [],
  targetCount: 50,
  typeRatio: {
    choice_single: 50,
    choice_multi: 30,
    choice_judgment: 20,
    short_answer: 0,
  },
  realtimeAnalysis: false,
})
const typeOptions = [
  { value: 'choice_single', label: '单选', defaultRatio: 50 },
  { value: 'choice_multi', label: '多选', defaultRatio: 30 },
  { value: 'choice_judgment', label: '判断', defaultRatio: 20 },
  { value: 'short_answer', label: '简答', defaultRatio: 0 },
]
const sessionId = ref('')
const group = ref(null)
const answers = reactive({})
const multiSelections = reactive({})
const feedback = reactive({})
const locked = reactive({})
const initialCounts = reactive({})
const everWrong = reactive({})
const editForm = reactive({
  id: null,
  content: '',
  type: '',
  options: [],
  standard_answer: '',
  analysis: '',
})
const saving = ref(false)
const starting = ref(false)
const jumping = ref(false)
const savingEdit = ref(false)
const _safeIndex = ref(0)
const role = ref(getRole() || '')
const isAdmin = computed(() => role.value === 'admin')
const realtimeSwitch = ref(true)
const feedbackReason = ref('')
const feedbackVisible = ref(false)
const selectionSummary = ref([])
const editMode = ref(false)

const currentIndex = computed(() => {
  if (!group.value || !group.value.questions) return 0
  return Math.min(_safeIndex.value, group.value.questions.length - 1)
})
const isLastQuestion = computed(() => {
  if (!group.value || !group.value.questions) return false
  return currentIndex.value >= group.value.questions.length - 1
})
const nextLabel = computed(() => (isLastQuestion.value ? '完成本组' : '下一题'))
const currentQuestion = computed(() => (group.value?.questions || [])[currentIndex.value])
const ratioTotal = computed(() => {
  return Object.values(form.typeRatio || {}).reduce((acc, val) => acc + Number(val || 0), 0)
})
const shouldShowFeedback = computed(() => {
  if (!group.value?.realtime_analysis) return false
  const q = currentQuestion.value
  if (!q) return false
  return !!feedback[q.id]
})
const remainingLabel = computed(() => {
  const val = group.value?.lowest_count_remaining ?? status.lowest_count_remaining
  if (typeof val === 'number') {
    return val > 0 ? `${val}` : '已通关'
  }
  return '未知'
})

const typeLabel = (type) => {
  if (type === 'choice_single') return '单选'
  if (type === 'choice_multi') return '多选'
  if (type === 'choice_judgment') return '判断'
  if (type === 'short_answer') return '简答'
  return type
}

const onBankSelect = (e) => {
  const vals = (e?.detail?.value || []).map((v) => Number(v))
  form.bankIds = vals
}

const loadBanks = async () => {
  try {
    const res = await fetchBanks()
    banks.value = res || []
  } catch (err) {
    uni.showToast({ title: err.message || '加载题库失败', icon: 'none' })
  }
}

const loadSettings = async () => {
  try {
    const res = await fetchSmartPracticeSettings()
    if (!res) return
    form.bankIds = res.bank_ids || []
    form.targetCount = res.target_count || 50
    form.typeRatio = res.type_ratio || form.typeRatio
    form.realtimeAnalysis = true
    realtimeSwitch.value = true
  } catch (err) {
    // allow empty
  }
}

const loadStatus = async () => {
  try {
    const res = await fetchSmartPracticeStatus()
    Object.assign(status, res)
    if (res.has_active && res.session_id) {
      sessionId.value = res.session_id
    }
    realtimeSwitch.value = true
  } catch (err) {
    // ignore
  }
}

const saveSettings = async () => {
  if (!form.bankIds.length) {
    return uni.showToast({ title: '请至少选择一个题库', icon: 'none' })
  }
  if (ratioTotal.value !== 100 && ratioTotal.value !== 0) {
    return uni.showToast({ title: '题型占比需合计 100%（或留空）', icon: 'none' })
  }
  saving.value = true
  try {
    await saveSmartPracticeSettings({
      bank_ids: form.bankIds,
      target_count: form.targetCount || 50,
      type_ratio: form.typeRatio,
      realtime_analysis: form.realtimeAnalysis,
    })
    uni.showToast({ title: '已保存', icon: 'none' })
  } catch (err) {
    uni.showToast({ title: err.message || '保存失败', icon: 'none' })
  } finally {
    saving.value = false
  }
}

const resetAnswers = (questions, currentIndex = 0) => {
  Object.keys(answers).forEach((k) => delete answers[k])
  Object.keys(multiSelections).forEach((k) => delete multiSelections[k])
  Object.keys(feedback).forEach((k) => delete feedback[k])
  Object.keys(locked).forEach((k) => delete locked[k])
  Object.keys(initialCounts).forEach((k) => delete initialCounts[k])
  Object.keys(everWrong).forEach((k) => delete everWrong[k])
  questions.forEach((q) => {
    initialCounts[q.id] = typeof q.practice_count === 'number' ? q.practice_count : 0
    const ua = q.user_answer || ''
    answers[q.id] = ua
    if (q.type === 'choice_multi') {
      multiSelections[q.id] = ua ? ua.split(',') : []
    }
    if (group.value?.realtime_analysis && ua) {
      locked[q.id] = true
      feedback[q.id] = {
        is_correct: q.is_correct,
        counted: typeof q.counted === 'boolean' ? q.counted : false,
        standard_answer: q.standard_answer || '',
        analysis: q.analysis || '',
      }
      if (q.is_correct === false) {
        everWrong[q.id] = true
      }
    }
  })
  _safeIndex.value = currentIndex || 0
  if (questions[currentIndex]) {
    editMode.value = false
    loadEditForm(questions[currentIndex])
  }
}

const startSmart = async () => {
  if (!form.bankIds.length) {
    return uni.showToast({ title: '请至少选择一个题库', icon: 'none' })
  }
  starting.value = true
  try {
    const res = await startSmartPracticeSession()
    sessionId.value = res.session_id
    group.value = { ...res, realtime_analysis: true }
    status.has_active = true
    status.session_id = res.session_id
    status.status = res.mode === 'reinforce' ? 'reinforce' : 'in_progress'
    realtimeSwitch.value = true
    resetAnswers(res.questions || [], res.current_question_index || 0)
    handleSelectionSummary(res)
  } catch (err) {
    uni.showToast({ title: err.message || '开启失败', icon: 'none' })
  } finally {
    starting.value = false
  }
}

const loadCurrentGroup = async () => {
  if (!sessionId.value) return
  try {
    const res = await fetchCurrentSmartPracticeGroup(sessionId.value)
    group.value = { ...res, realtime_analysis: true }
    realtimeSwitch.value = true
    resetAnswers(res.questions || [], res.current_question_index || 0)
    handleSelectionSummary(res)
  } catch (err) {
    uni.showToast({ title: err.message || '加载题组失败', icon: 'none' })
  }
}

const submitOption = async (value) => {
  const q = currentQuestion.value
  if (!q || !sessionId.value) return
  answers[q.id] = value
  await sendAnswer(q.id, value)
}

const toggleMulti = (value) => {
  const q = currentQuestion.value
  if (!q) return
  if (!multiSelections[q.id]) multiSelections[q.id] = []
  const idx = multiSelections[q.id].indexOf(value)
  if (idx >= 0) multiSelections[q.id].splice(idx, 1)
  else multiSelections[q.id].push(value)
}

const confirmMulti = async () => {
  const q = currentQuestion.value
  if (!q || !sessionId.value) return
  const normalized = normalizeMultiAnswer(multiSelections[q.id])
  if (!normalized) {
    return uni.showToast({ title: '请先选择选项', icon: 'none' })
  }
  answers[q.id] = normalized
  await sendAnswer(q.id, answers[q.id])
}

const submitText = async () => {
  const q = currentQuestion.value
  if (!q || !sessionId.value) return
  if (!answers[q.id]) return
  await sendAnswer(q.id, answers[q.id])
}

const flushCurrentAnswer = async () => {
  const q = currentQuestion.value
  if (!q || !sessionId.value) return
  if (q.type === 'short_answer' && answers[q.id]) {
    await submitText()
  }
}

const sendAnswer = async (questionId, answer) => {
  if (group.value?.realtime_analysis && locked[questionId]) return
  const q = (group.value?.questions || []).find((item) => item.id === questionId)
  try {
    const res = await answerSmartPracticeQuestion(sessionId.value, {
      question_id: questionId,
      answer,
      current_index: currentIndex.value,
    })
    feedback[questionId] = {
      ...res,
      standard_answer: res.standard_answer || q?.standard_answer || '',
      analysis: res.analysis || q?.analysis || '',
      counted: res.counted,
    }
    if (!res.is_correct) {
      everWrong[questionId] = true
    }
    if (group.value?.realtime_analysis) {
      locked[questionId] = true
    }
  } catch (err) {
    uni.showToast({ title: err.message || '提交失败', icon: 'none' })
  }
}

const prev = () => {
  if (currentIndex.value > 0) {
    _safeIndex.value -= 1
  }
}

const handleNext = async () => {
  const q = currentQuestion.value
  if (!q) return
  if (q.type === 'choice_multi' && !(answers[q.id] || (multiSelections[q.id] || []).length)) {
    return uni.showToast({ title: '请先作答本题', icon: 'none' })
  }
  if (q.type === 'choice_multi' && !answers[q.id]) {
    await confirmMulti()
    if (!answers[q.id]) return
  }
  if (q.type === 'short_answer') {
    await flushCurrentAnswer()
  }
  if (!isLastQuestion.value) {
    _safeIndex.value = Math.min(currentIndex.value + 1, (group.value?.questions?.length || 1) - 1)
    return
  }
  await completeGroup()
}

const buildRoundCountSummary = () => {
  const summary = {
    increments: {},
    drops: {},
    stayZero: 0,
    hasWrong: false,
  }
  if (!group.value?.questions?.length) return summary
  group.value.questions.forEach((q) => {
    const fb = feedback[q.id]
    const initial = typeof initialCounts[q.id] === 'number' ? initialCounts[q.id] : 0
    const wasWrong = !!everWrong[q.id] || fb?.is_correct === false
    const countedUp = !!fb?.counted
    let nextCount = initial
    if (wasWrong) {
      summary.hasWrong = true
      nextCount = 0
    } else if (countedUp) {
      nextCount = initial + 1
    }
    if (countedUp) {
      summary.increments[initial] = (summary.increments[initial] || 0) + 1
    }
    if (wasWrong && initial > 0) {
      summary.drops[initial] = (summary.drops[initial] || 0) + 1
    }
    if (initial === 0 && nextCount === 0) {
      summary.stayZero += 1
    }
  })
  return summary
}

const confirmReinforceTransition = (summaryText) =>
  new Promise((resolve) => {
    uni.showModal({
      title: '进入强化模式',
      content: summaryText,
      showCancel: false,
      confirmText: '确认进入强化',
      success: () => resolve(true),
      fail: () => resolve(false),
    })
  })

const formatSummaryText = (summary) => {
  const parts = []
  const incEntries = Object.keys(summary.increments)
    .map((k) => Number(k))
    .sort((a, b) => a - b)
    .map((from) => `${from}->${from + 1}：${summary.increments[from]} 题`)
  if (incEntries.length) {
    parts.push(`计数上升：${incEntries.join('，')}`)
  }

  const dropEntries = Object.keys(summary.drops)
    .map((k) => Number(k))
    .sort((a, b) => a - b)
    .map((from) => `${from}->0：${summary.drops[from]} 题`)
  if (dropEntries.length) {
    parts.push(`计数归零：${dropEntries.join('，')}`)
  }
  if (summary.stayZero) {
    parts.push(`保持为 0：${summary.stayZero} 题`)
  }
  if (!parts.length) {
    parts.push('本轮未产生计数变化')
  }
  return parts.join('\n')
}

const completeGroup = async () => {
  if (!sessionId.value) return
  await flushCurrentAnswer()
  const missing = (group.value?.questions || []).find((q) => !answers[q.id])
  if (missing) {
    return uni.showToast({ title: '还有未作答题目', icon: 'none' })
  }
  const summary = buildRoundCountSummary()
  const shouldConfirmReinforce = group.value?.mode === 'normal' && summary.hasWrong
  if (shouldConfirmReinforce) {
    const summaryText = formatSummaryText(summary)
    const confirmed = await confirmReinforceTransition(summaryText)
    if (!confirmed) return
  }
  jumping.value = true
  try {
    const res = await nextSmartPracticeGroup(sessionId.value)
    group.value = { ...res, realtime_analysis: true }
    realtimeSwitch.value = true
    resetAnswers(res.questions || [], res.current_question_index || 0)
    status.status = res.mode === 'reinforce' ? 'reinforce' : 'in_progress'
    status.current_group_index = res.group_index
    status.round = res.round
    if (group.value?.questions?.[0]) loadEditForm(group.value.questions[0])
    handleSelectionSummary(res)
  } catch (err) {
    uni.showToast({ title: err.message || '无法进入下一组', icon: 'none' })
  } finally {
    jumping.value = false
  }
}

const toggleRealtime = async () => {
  if (!sessionId.value) return
  try {
    const target = !group.value?.realtime_analysis
    const res = await toggleSmartPracticeAnalysis(sessionId.value, target)
    status.realtime_analysis = res.realtime_analysis
    if (group.value) {
      group.value.realtime_analysis = target
    }
    uni.showToast({ title: target ? '已开启解析' : '已关闭解析', icon: 'none' })
  } catch (err) {
    uni.showToast({ title: err.message || '更新失败', icon: 'none' })
  }
}

const onToggleRealtime = async (e) => {
  realtimeSwitch.value = !!e?.detail?.value
  try {
    const res = await toggleSmartPracticeAnalysis(sessionId.value, realtimeSwitch.value)
    status.realtime_analysis = res.realtime_analysis
    if (group.value) group.value.realtime_analysis = res.realtime_analysis
  } catch (err) {
    realtimeSwitch.value = !!group.value?.realtime_analysis
    uni.showToast({ title: err.message || '更新失败', icon: 'none' })
  }
}

const loadEditForm = (question) => {
  editForm.id = question.id
  editForm.content = question.content
  editForm.type = question.type
  editForm.options = JSON.parse(JSON.stringify(question.options || []))
  editForm.standard_answer = question.standard_answer || ''
  editForm.analysis = question.analysis || ''
}

watch(currentQuestion, (q) => {
  if (q) {
    editMode.value = false
    loadEditForm(q)
  }
})

const cancelEdit = () => {
  if (currentQuestion.value) loadEditForm(currentQuestion.value)
  editMode.value = false
}

const saveEdit = async () => {
  if (!editForm.id) return
  savingEdit.value = true
  try {
    const payload = {
      content: editForm.content,
      options: editForm.options,
      standard_answer: editForm.standard_answer,
      analysis: editForm.analysis,
    }
    const updated = await updateQuestionApi(editForm.id, payload)
    const idx = group.value.questions.findIndex((q) => q.id === updated.id)
    if (idx !== -1) {
      group.value.questions[idx] = { ...group.value.questions[idx], ...updated }
      loadEditForm(group.value.questions[idx])
    }
    uni.showToast({ title: '已保存修正', icon: 'none' })
  } catch (err) {
    uni.showToast({ title: err.message || '保存失败', icon: 'none' })
  } finally {
    savingEdit.value = false
  }
}

const toggleEdit = () => {
  editMode.value = !editMode.value
  if (editMode.value && currentQuestion.value) {
    loadEditForm(currentQuestion.value)
  }
}

const normalizeMultiAnswer = (vals) => {
  if (!vals) return ''
  const arr = Array.isArray(vals) ? vals : String(vals).split(',')
  return arr
    .join(',')
    .replace(/\s+/g, ',')
    .split(',')
    .map((s) => s.toString().trim().toUpperCase())
    .filter(Boolean)
    .sort()
    .join(',')
}

const openFeedback = () => {
  feedbackReason.value = ''
  uni.showModal({
    title: '题目反馈',
    editable: true,
    placeholderText: '请输入问题，例如题型/答案有误等',
    success: async (res) => {
      if (!res.confirm) {
        return
      }
      feedbackReason.value = res.content || ''
      await submitFeedback()
    },
  })
}

const submitFeedback = async () => {
  const q = currentQuestion.value
  if (!q || !sessionId.value) return
  try {
    await feedbackSmartPracticeQuestion(sessionId.value, {
      question_id: q.id,
      reason: feedbackReason.value || '用户反馈',
    })
    uni.showToast({ title: '已反馈并跳过', icon: 'none' })
    feedback[q.id] = { is_correct: true, counted: false, standard_answer: q.standard_answer, analysis: q.analysis }
    locked[q.id] = true
    answers[q.id] = answers[q.id] || '反馈跳过'
    if (!isLastQuestion.value) {
      _safeIndex.value = Math.min(currentIndex.value + 1, group.value.questions.length - 1)
    } else {
      await completeGroup()
    }
  } catch (err) {
    uni.showToast({ title: err.message || '反馈失败', icon: 'none' })
  }
}

const formatType = (type) => {
  if (type === 'choice_single') return '单选'
  if (type === 'choice_multi') return '多选'
  if (type === 'choice_judgment') return '判断'
  if (type === 'short_answer') return '简答'
  return type
}

const handleSelectionSummary = (groupData) => {
  selectionSummary.value = groupData.selection_summary || []
  if (!selectionSummary.value.length) return
  const lines = selectionSummary.value.map((item) => {
    const levelPairs = Object.keys(item.count_by_level || {})
      .map((k) => Number(k))
      .sort((a, b) => a - b)
      .map((level) => `计数 ${level}：${item.count_by_level[level]} 题`)
    const levelText = levelPairs.length ? levelPairs.join('，') : `计数最小 ${item.count_min} 题`
    return `${formatType(item.type)}：${levelText}`
  })
  uni.showModal({
    title: '抽题结果',
    content: lines.join('\n'),
    showCancel: false,
  })
}

onShow(async () => {
  role.value = getRole() || ''
  await loadBanks()
  await loadSettings()
  await loadStatus()
  if (sessionId.value) {
    await loadCurrentGroup()
  }
})

onHide(async () => {
  await flushCurrentAnswer()
})

onUnload(async () => {
  await flushCurrentAnswer()
})
</script>

<style>
.page {
  padding: 24rpx;
  padding-bottom: 200rpx;
  display: flex;
  flex-direction: column;
  gap: 20rpx;
  background: #f8fafc;
  min-height: 100vh;
  touch-action: manipulation;
}

.card {
  background: #ffffff;
  border-radius: 18rpx;
  padding: 20rpx;
  box-shadow: 0 6rpx 24rpx rgba(15, 23, 42, 0.04);
}
.card.compact {
  padding: 14rpx;
}

.card-header {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  margin-bottom: 12rpx;
}
.compact-header {
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
  gap: 10rpx;
  margin-bottom: 8rpx;
}
.header-left {
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.title {
  font-size: 32rpx;
  font-weight: 700;
  color: #0f172a;
}

.hint {
  color: #64748b;
  font-size: 24rpx;
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  margin-bottom: 12rpx;
}

.label {
  font-size: 26rpx;
  color: #0f172a;
}

.checkbox {
  display: inline-flex;
  align-items: center;
  margin-right: 16rpx;
  margin-bottom: 8rpx;
  gap: 6rpx;
}

.input {
  border: 1rpx solid #e2e8f0;
  border-radius: 12rpx;
  padding: 12rpx;
  background: #f8fafc;
}

.ratio-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10rpx;
}

.ratio-item {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.ratio-label {
  width: 120rpx;
  color: #334155;
}

.ratio-unit {
  color: #94a3b8;
}

.switch-row {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
}

.actions {
  display: flex;
  gap: 10rpx;
  margin-top: 8rpx;
}

.session-actions {
  display: flex;
  gap: 10rpx;
  flex-wrap: wrap;
}

.mode-btn {
  border: none;
  color: #0f172a;
  padding: 16rpx 22rpx;
  border-radius: 14rpx;
  font-size: 26rpx;
  font-weight: 600;
  box-shadow: 0 6rpx 16rpx rgba(15, 23, 42, 0.08);
}

.mode-practice {
  background: #22c55e;
  color: #0b2f19;
}

.mode-exam {
  background: #fcd34d;
  color: #5b4210;
}

.info-row {
  margin-top: 12rpx;
}

.tag {
  background: #e0f2fe;
  color: #0ea5e9;
  padding: 6rpx 12rpx;
  border-radius: 12rpx;
  font-size: 22rpx;
}

.question-card {
  border: 1rpx solid #e2e8f0;
  border-radius: 14rpx;
  padding: 16rpx;
  background: #f8fafc;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.question-head {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.qid {
  color: #94a3b8;
  font-size: 22rpx;
}

.type {
  color: #0ea5e9;
  font-weight: 600;
}
.type.type-choice_single {
  color: #0ea5e9;
}
.type.type-choice_multi {
  color: #22c55e;
}
.type.type-choice_judgment {
  color: #f59e0b;
}
.type.type-short_answer {
  color: #8b5cf6;
}

.badge {
  background: #fef3c7;
  color: #b45309;
  padding: 6rpx 12rpx;
  border-radius: 12rpx;
  font-size: 22rpx;
}

.question-content {
  font-size: 30rpx;
  color: #0f172a;
  line-height: 1.6;
}

.options {
  display: flex;
  flex-direction: column;
  gap: 10rpx;
}

.option {
  border: 1rpx solid #e2e8f0;
  border-radius: 12rpx;
  padding: 14rpx;
  display: flex;
  align-items: center;
  gap: 10rpx;
  background: #ffffff;
}

.option.active {
  border-color: #0ea5e9;
  background: #e0f2fe;
}

.opt-key {
  width: 44rpx;
  height: 44rpx;
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

.textarea {
  border: 1rpx solid #e2e8f0;
  border-radius: 12rpx;
  padding: 12rpx;
  min-height: 200rpx;
  background: #ffffff;
  box-sizing: border-box;
}

.feedback {
  border-top: 1rpx dashed #e2e8f0;
  padding-top: 8rpx;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.status {
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
}

.progress {
  margin: 12rpx 0;
  color: #475569;
}

.footer {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 14rpx 24rpx 24rpx;
  background: rgba(248, 250, 252, 0.98);
  box-shadow: 0 -8rpx 24rpx rgba(15, 23, 42, 0.08);
  z-index: 10;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10rpx;
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
  padding: 10rpx 12rpx;
  font-size: 24rpx;
}

.empty {
  text-align: center;
  color: #94a3b8;
  padding: 40rpx 0;
}
</style>

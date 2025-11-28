<template>
	<view class="page">
		<view class="section">
			<view class="section-header">
				<view>
					<text class="eyebrow">题库</text>
					<text class="title">增删改查</text>
				</view>
				<view class="header-actions">
					<button class="ghost" size="mini" @click="resetBankForm">新建题库</button>
					<button class="ghost" size="mini" @click="goMerge">合并题库</button>
				</view>
			</view>
			<view class="form-card">
				<input v-model="bankForm.title" placeholder="题库名称" class="input" />
				<input v-model="bankForm.description" placeholder="描述（可选）" class="input" />
				<label class="switch-row">
					<text>公开题库</text>
					<switch :checked="bankForm.is_public" @change="(e) => (bankForm.is_public = e.detail.value)" />
				</label>
				<button class="primary" :loading="bankSaving" @click="submitBank">
					{{ bankForm.id ? '更新题库' : '创建题库' }}
				</button>
			</view>

			<view class="list" v-if="banks.length">
				<view v-for="bank in banks" :key="bank.id" class="item">
					<view class="item-main">
						<text class="item-title">{{ bank.title }}</text>
						<text class="item-desc">{{ bank.description || '暂无描述' }}</text>
					</view>
					<view class="actions">
						<button size="mini" @click="editBank(bank)">编辑</button>
						<button size="mini" type="warn" @click="removeBank(bank.id)">删除</button>
						<button size="mini" class="ghost" @click="selectBank(bank.id)">查看题目</button>
					</view>
				</view>
			</view>
			<view v-else class="empty">暂无题库，先创建一个吧。</view>
		</view>

		<view class="section">
			<view class="section-header">
				<view>
					<text class="eyebrow">题目</text>
					<text class="title">管理当前题库</text>
				</view>
				<picker mode="selector" :range="banks" range-key="title" @change="onBankChange">
					<view class="picker">
						<text>{{ currentBankLabel }}</text>
						<text class="arrow">▼</text>
					</view>
				</picker>
			</view>

			<view class="form-card">
				<view class="row">
					<text class="label">批量导入</text>
					<input v-model="importDir" placeholder="服务器目录，如 /data/papers" class="input" />
					<label class="switch-row">
						<text>递归扫描子目录</text>
						<switch :checked="importRecursive" @change="(e) => (importRecursive = e.detail.value)" />
					</label>
					<button class="primary" :loading="importLoading" @click="runBatchImport">开始扫描导入</button>
				</view>
				<view v-if="importReport" class="import-report">
					<text class="label">导入结果</text>
					<text class="meta">文件 {{ importReport.processed_files }}/{{ importReport.total_files }} ｜ 新增 {{ importReport.imported_questions }} ｜ 重复 {{ importReport.duplicate_questions }} ｜ 失败 {{ importReport.failed_files }}</text>
					<view v-for="file in importReport.file_results" :key="file.filename" class="import-file">
						<text class="file-name">{{ file.filename }}</text>
						<text class="meta">导入 {{ file.imported }} ｜ 重复 {{ file.duplicates }}</text>
						<view v-if="file.errors?.length" class="warn">错误: {{ file.errors.join('；') }}</view>
						<view v-if="file.warnings?.length" class="warn secondary">警告: {{ file.warnings.join('；') }}</view>
					</view>
				</view>
			</view>

			<view class="form-card">
				<view class="row">
					<text class="label">题型</text>
				<view class="chips">
					<view
						v-for="type in questionTypes"
						:key="type.value"
						:class="['chip', newQuestion.type === type.value ? 'chip-active' : '']"
						@click="setNewType(type.value)"
					>
						<text v-if="type.value === 'choice_single'">🔘</text>
						<text v-else-if="type.value === 'choice_multi'">☑️</text>
						<text v-else-if="type.value === 'choice_judgment'">✅❌</text>
						<text v-else>✏️</text>
						<text class="chip-text">{{ type.label }}</text>
					</view>
				</view>
				</view>
				<input v-model="newQuestion.content" placeholder="题干" class="input" />
				<view v-if="newQuestion.type !== 'short_answer'" class="options">
					<view v-for="(opt, idx) in newQuestion.options" :key="idx" class="option">
						<text class="opt-key">{{ opt.key }}</text>
						<input v-model="opt.text" class="opt-input" placeholder="选项内容" />
						<button size="mini" class="ghost mini" @click="removeOption(newQuestion, idx)">-</button>
					</view>
					<button class="ghost mini" @click="addOption(newQuestion)">添加选项</button>
				</view>
				<view v-if="newQuestion.type === 'choice_single'" class="options">
					<view v-for="(opt, idx) in newQuestion.options" :key="`ans-${idx}`" class="option">
						<radio
							:value="opt.key"
							:checked="newQuestion.standard_answer === opt.key"
							@change="() => setSingleAnswer(newQuestion, opt.key)"
						/>
						<text class="opt-text">{{ opt.key }}. {{ opt.text || '未填写' }}</text>
					</view>
				</view>
				<view v-else-if="newQuestion.type === 'choice_multi'" class="options">
					<view v-for="(opt, idx) in newQuestion.options" :key="`ans-${idx}`" class="option">
						<checkbox
							:value="opt.key"
							:checked="isMultiChecked(newQuestion, opt.key)"
							@change="() => toggleMultiAnswer(newQuestion, opt.key)"
						/>
						<text class="opt-text">{{ opt.key }}. {{ opt.text || '未填写' }}</text>
					</view>
					<text class="hint">多选可勾选多个作为正确答案</text>
				</view>
				<input
					v-else
					v-model="newQuestion.standard_answer"
					placeholder="答案（如 A 或文本）"
					class="input"
				/>
				<textarea v-model="newQuestion.analysis" class="textarea" placeholder="解析（可选）" />
				<button class="primary" :loading="creatingQuestion" @click="createQuestion">添加题目</button>
			</view>

			<view v-if="questionLoading" class="empty">题目加载中...</view>
			<view v-else-if="!questions.length" class="empty">当前题库暂无题目。</view>
			<view v-else>
				<view v-if="questionTotal" class="pagination">
					<button size="mini" class="ghost" :disabled="questionPage === 1" @click="goPrevPage">上一页</button>
					<text class="pager-text">第 {{ questionPage }} / {{ totalPages }} 页 · 共 {{ questionTotal }} 题</text>
					<button size="mini" class="ghost" :disabled="questionPage >= totalPages" @click="goNextPage">
						下一页
					</button>
				</view>
				<view class="question-list">
					<view v-for="question in questions" :key="question.id" class="question-card">
						<view class="question-summary" @click="toggleQuestion(question.id)">
							<view class="summary-left">
								<text class="summary-title">{{ truncate(question.content) }}</text>
								<text class="summary-meta">题型：{{ typeLabel(question.type) }}</text>
							</view>
							<text class="arrow">{{ expandedId === question.id ? '▲' : '▼' }}</text>
						</view>
						<view v-if="expandedId === question.id" class="question-detail">
							<view class="question-row">
								<text class="label">题型</text>
								<view class="chips">
									<view
										v-for="type in questionTypes"
										:key="type.value"
										:class="['chip', question.type === type.value ? 'chip-active' : '']"
										@click="setQuestionType(question, type.value)"
									>
										<text v-if="type.value === 'choice_single'">🔘</text>
										<text v-else-if="type.value === 'choice_multi'">☑️</text>
										<text v-else-if="type.value === 'choice_judgment'">✅❌</text>
										<text v-else>✏️</text>
										<text class="chip-text">{{ type.label }}</text>
									</view>
								</view>
							</view>
							<input v-model="question.content" class="input" />
							<view v-if="question.type !== 'short_answer'" class="options">
								<view v-for="(opt, idx) in question.options" :key="idx" class="option">
									<text class="opt-key">{{ opt.key }}</text>
									<input v-model="opt.text" class="opt-input" />
									<button size="mini" class="ghost mini" @click="removeOption(question, idx)">-</button>
								</view>
								<button class="ghost mini" @click="addOption(question)">添加选项</button>
							</view>
							<view v-if="question.type === 'choice_single'" class="options">
								<view v-for="(opt, idx) in question.options" :key="`edit-ans-${idx}`" class="option">
									<radio
										:value="opt.key"
										:checked="question.standard_answer === opt.key"
										@change="() => setSingleAnswer(question, opt.key)"
									/>
									<text class="opt-text">{{ opt.key }}. {{ opt.text || '未填写' }}</text>
								</view>
							</view>
							<view v-else-if="question.type === 'choice_multi'" class="options">
								<view v-for="(opt, idx) in question.options" :key="`edit-ans-${idx}`" class="option">
									<checkbox
										:value="opt.key"
										:checked="isMultiChecked(question, opt.key)"
										@change="() => toggleMultiAnswer(question, opt.key)"
									/>
									<text class="opt-text">{{ opt.key }}. {{ opt.text || '未填写' }}</text>
								</view>
								<text class="hint">多选可勾选多个作为正确答案</text>
							</view>
							<input v-else v-model="question.standard_answer" class="input" />
							<textarea v-model="question.analysis" class="textarea" placeholder="解析" />
							<view class="card-actions">
								<button size="mini" :loading="savingQuestionId === question.id" @click="saveQuestion(question)">
									保存
								</button>
								<button size="mini" type="warn" @click="removeQuestion(question.id)">删除</button>
							</view>
						</view>
					</view>
				</view>
			</view>
		</view>
	</view>
</template>

<script setup>
import { onLoad } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import {
  createBank,
  deleteBank,
  deleteQuestion,
  batchImportQuestions,
  fetchBanks,
  fetchQuestions,
  getToken,
  getRole,
  saveManualQuestion,
  updateBank,
  updateQuestionApi,
} from '../../services/api'

const banks = ref([])
const bankForm = ref({ id: null, title: '', description: '', is_public: false })
const bankSaving = ref(false)
const questionLoading = ref(false)
const questions = ref([])
const questionPage = ref(1)
const questionTotal = ref(0)
const selectedBankId = ref(null)
const creatingQuestion = ref(false)
const savingQuestionId = ref(null)
const expandedId = ref(null)
const importDir = ref('')
const importRecursive = ref(true)
const importLoading = ref(false)
const importReport = ref(null)
const QUESTION_PAGE_SIZE = 10

const questionTypes = [
  { label: '单选', value: 'choice_single' },
  { label: '判断', value: 'choice_judgment' },
  { label: '多选', value: 'choice_multi' },
  { label: '简答', value: 'short_answer' },
]

const newQuestion = ref({
  type: 'choice_single',
  content: '',
  options: [
    { key: 'A', text: '' },
    { key: 'B', text: '' },
  ],
  standard_answer: '',
  analysis: '',
})

const currentBankLabel = computed(() => {
  const found = banks.value.find((b) => b.id === selectedBankId.value)
  return found ? found.title : '选择题库'
})

const totalPages = computed(() => {
  return questionTotal.value ? Math.ceil(questionTotal.value / QUESTION_PAGE_SIZE) : 1
})

const goToPage = (page) => {
  if (page < 1 || page > totalPages.value) return
  questionPage.value = page
  loadQuestions()
}

const goPrevPage = () => goToPage(questionPage.value - 1)
const goNextPage = () => goToPage(questionPage.value + 1)
const goMerge = () => {
  uni.navigateTo({ url: '/pages/manager/merge' })
}

onLoad(() => {
  if (!getToken()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  if (getRole() !== 'admin') {
    uni.showToast({ title: '需要管理员权限', icon: 'none' })
    setTimeout(() => uni.switchTab({ url: '/pages/index/index' }), 800)
    return
  }
  loadBanks()
})

const resetBankForm = () => {
  bankForm.value = { id: null, title: '', description: '', is_public: false }
}

const editBank = (bank) => {
  bankForm.value = { ...bank }
}

const submitBank = async () => {
  if (!bankForm.value.title.trim()) {
    return uni.showToast({ title: '请输入题库名称', icon: 'none' })
  }
  bankSaving.value = true
  try {
    if (bankForm.value.id) {
      await updateBank(bankForm.value.id, {
        title: bankForm.value.title,
        description: bankForm.value.description,
        is_public: bankForm.value.is_public,
      })
      uni.showToast({ title: '题库已更新', icon: 'success' })
    } else {
      await createBank({
        title: bankForm.value.title,
        description: bankForm.value.description,
        is_public: bankForm.value.is_public,
      })
      uni.showToast({ title: '题库已创建', icon: 'success' })
    }
    await loadBanks()
    resetBankForm()
  } catch (err) {
    uni.showToast({ title: err.message || '操作失败', icon: 'none' })
  } finally {
    bankSaving.value = false
  }
}

const removeBank = async (bankId) => {
  const res = await uni.showModal({ title: '确认删除', content: '删除题库将清空其题目，确认？' })
  if (res.confirm) {
    try {
      await deleteBank(bankId)
      uni.showToast({ title: '已删除', icon: 'success' })
      if (selectedBankId.value === bankId) {
        selectedBankId.value = null
        questions.value = []
        questionTotal.value = 0
        questionPage.value = 1
      }
      await loadBanks()
    } catch (err) {
      uni.showToast({ title: err.message || '删除失败', icon: 'none' })
    }
  }
}

const loadBanks = async () => {
  try {
    const res = await fetchBanks()
    banks.value = res || []
    if (!selectedBankId.value && banks.value.length) {
      selectedBankId.value = banks.value[0].id
      questionPage.value = 1
      loadQuestions()
    }
  } catch (err) {
    uni.showToast({ title: err.message || '题库加载失败', icon: 'none' })
  }
}

const onBankChange = (event) => {
  const idx = Number(event.detail.value)
  const picked = banks.value[idx]
  if (picked) {
    selectBank(picked.id)
  }
}

const selectBank = (bankId) => {
  selectedBankId.value = bankId
  questionPage.value = 1
  loadQuestions()
}

const loadQuestions = async () => {
  if (!selectedBankId.value) {
    questions.value = []
    questionTotal.value = 0
    return
  }
  questionLoading.value = true
  try {
    const res = await fetchQuestions(selectedBankId.value, {
      page: questionPage.value,
      pageSize: QUESTION_PAGE_SIZE,
    })
    const items = Array.isArray(res) ? res : res?.items || []
    questionTotal.value = res?.total ?? items.length
    questionPage.value = res?.page ?? questionPage.value
    questions.value = items.map((q) => ({
      ...q,
      options: q.options || [],
    }))
    if (!questions.value.length && questionTotal.value > 0 && questionPage.value > 1) {
      const lastPage = Math.max(1, Math.ceil(questionTotal.value / QUESTION_PAGE_SIZE))
      if (lastPage !== questionPage.value) {
        questionPage.value = lastPage
        await loadQuestions()
      }
    }
    expandedId.value = null
  } catch (err) {
    uni.showToast({ title: err.message || '题目加载失败', icon: 'none' })
  } finally {
    questionLoading.value = false
  }
}

const addOption = (question) => {
  const nextKey = String.fromCharCode(65 + (question.options?.length || 0))
  if (!question.options) question.options = []
  question.options.push({ key: nextKey, text: '' })
}

const removeOption = (question, idx) => {
  if (!question.options) return
  question.options.splice(idx, 1)
}

const setQuestionType = (question, type) => {
  question.type = type
  if (type === 'short_answer') {
    question.options = []
    question.standard_answer = ''
    return
  }
  if (!question.options || !question.options.length) {
    if (type === 'choice_judgment') {
      question.options = [
        { key: 'A', text: '正确' },
        { key: 'B', text: '错误' },
      ]
      question.standard_answer = 'A'
    } else {
      question.options = [
        { key: 'A', text: '' },
        { key: 'B', text: '' },
      ]
    }
  }
}

const setNewType = (type) => {
  newQuestion.value.type = type
  if (type === 'short_answer') {
    newQuestion.value.options = []
    return
  }
  if (!newQuestion.value.options || !newQuestion.value.options.length) {
    if (type === 'choice_judgment') {
      newQuestion.value.options = [
        { key: 'A', text: '正确' },
        { key: 'B', text: '错误' },
      ]
      newQuestion.value.standard_answer = 'A'
    } else {
      newQuestion.value.options = [
        { key: 'A', text: '' },
        { key: 'B', text: '' },
      ]
    }
  }
}

const createQuestion = async () => {
  if (!selectedBankId.value) {
    return uni.showToast({ title: '请先选择题库', icon: 'none' })
  }
  if (!newQuestion.value.content.trim()) {
    return uni.showToast({ title: '请输入题干', icon: 'none' })
  }
  creatingQuestion.value = true
  try {
    const payload = {
      ...newQuestion.value,
      bank_id: selectedBankId.value,
      options: newQuestion.value.type === 'short_answer' ? [] : newQuestion.value.options,
      standard_answer:
        newQuestion.value.type === 'choice_multi'
          ? (newQuestion.value.standard_answer || '').split(',').map((s) => s.trim()).filter(Boolean).join(',')
          : newQuestion.value.standard_answer,
    }
    await saveManualQuestion(payload)
    uni.showToast({ title: '题目已添加', icon: 'success' })
    resetNewQuestion()
    questionPage.value = 1
    await loadQuestions()
  } catch (err) {
    uni.showToast({ title: err.message || '添加失败', icon: 'none' })
  } finally {
    creatingQuestion.value = false
  }
}

const resetNewQuestion = () => {
  newQuestion.value = {
    type: 'choice_single',
    content: '',
    options: [
      { key: 'A', text: '' },
      { key: 'B', text: '' },
    ],
    standard_answer: '',
    analysis: '',
  }
}

const saveQuestion = async (question) => {
  if (!question.content.trim()) {
    return uni.showToast({ title: '题干不能为空', icon: 'none' })
  }
  savingQuestionId.value = question.id
  try {
    const payload = {
      bank_id: selectedBankId.value,
      type: question.type,
      content: question.content,
      options: question.type === 'short_answer' ? [] : question.options,
      standard_answer:
        question.type === 'choice_multi'
          ? (question.standard_answer || '').split(',').map((s) => s.trim()).filter(Boolean).join(',')
          : question.standard_answer,
      analysis: question.analysis,
    }
    await updateQuestionApi(question.id, payload)
    uni.showToast({ title: '已保存', icon: 'success' })
    await loadQuestions()
  } catch (err) {
    uni.showToast({ title: err.message || '保存失败', icon: 'none' })
  } finally {
    savingQuestionId.value = null
  }
}

const removeQuestion = async (questionId) => {
  const res = await uni.showModal({ title: '确认删除', content: '删除后不可恢复，确定删除该题目？' })
  if (res.confirm) {
    try {
      await deleteQuestion(questionId)
      uni.showToast({ title: '已删除', icon: 'success' })
      await loadQuestions()
    } catch (err) {
      uni.showToast({ title: err.message || '删除失败', icon: 'none' })
    }
  }
}

const toggleQuestion = (id) => {
  expandedId.value = expandedId.value === id ? null : id
}

const typeLabel = (type) => {
  const found = questionTypes.find((t) => t.value === type)
  return found ? found.label : type
}

const truncate = (text, len = 60) => {
  if (!text) return ''
  return text.length > len ? `${text.slice(0, len)}...` : text
}

const setSingleAnswer = (target, key) => {
  target.standard_answer = key
}

const toggleMultiAnswer = (target, key) => {
  const existing = (target.standard_answer || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
  const idx = existing.indexOf(key)
  if (idx >= 0) {
    existing.splice(idx, 1)
  } else {
    existing.push(key)
  }
  target.standard_answer = existing.join(',')
}

const isMultiChecked = (target, key) => {
  return (target.standard_answer || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
    .includes(key)
}

const runBatchImport = async () => {
  if (!selectedBankId.value) {
    return uni.showToast({ title: '请先选择题库', icon: 'none' })
  }
  if (!importDir.value.trim()) {
    return uni.showToast({ title: '请输入目录路径', icon: 'none' })
  }
  importLoading.value = true
  // fire-and-forget: 发送后端立即返回，不等待全量结果
  batchImportQuestions({
    bank_id: selectedBankId.value,
    directory: importDir.value,
    recursive: importRecursive.value,
  })
    .then(() => {
      uni.showToast({ title: '已提交导入任务，稍后刷新', icon: 'none' })
      loadQuestions()
    })
    .catch((err) => {
      uni.showToast({ title: err.message || '导入失败', icon: 'none' })
    })
    .finally(() => {
      importLoading.value = false
    })
}
</script>

<style>
.page {
	padding: 24rpx;
	display: flex;
	flex-direction: column;
	gap: 20rpx;
	background: linear-gradient(180deg, #f7faff 0%, #ffffff 90%);
}

.section {
	background: #ffffff;
	border-radius: 18rpx;
	padding: 18rpx;
	box-shadow: 0 6rpx 18rpx rgba(15, 23, 42, 0.05);
	display: flex;
	flex-direction: column;
	gap: 12rpx;
}

.section-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
}

.header-actions {
	display: flex;
	gap: 12rpx;
}

.eyebrow {
	font-size: 22rpx;
	color: #94a3b8;
}

.title {
	display: block;
	font-size: 36rpx;
	font-weight: 700;
	color: #0f172a;
}

.form-card {
	border: 1rpx solid #e2e8f0;
	border-radius: 14rpx;
	padding: 14rpx;
	display: flex;
	flex-direction: column;
	gap: 10rpx;
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
	transition: all 0.2s ease;
	display: flex;
	align-items: center;
	gap: 6rpx;
}

.chip-active {
	background: #0ea5e9;
	color: #ffffff;
	border-color: #0ea5e9;
	box-shadow: 0 4rpx 12rpx rgba(14, 165, 233, 0.25);
}

.chip-text {
	display: inline-block;
}

.import-report {
	border-top: 1rpx dashed #e2e8f0;
	padding-top: 10rpx;
	display: flex;
	flex-direction: column;
	gap: 8rpx;
}

.import-file {
	border: 1rpx solid #e2e8f0;
	border-radius: 10rpx;
	padding: 8rpx;
}

.file-name {
	font-size: 24rpx;
	color: #0f172a;
}

.warn {
	color: #dc2626;
	font-size: 22rpx;
}

.warn.secondary {
	color: #b45309;
}

.input {
	border: 1rpx solid #e2e8f0;
	border-radius: 12rpx;
	padding: 12rpx;
	background: #f8fafc;
}

.textarea {
	min-height: 120rpx;
	border: 1rpx solid #e2e8f0;
	border-radius: 12rpx;
	padding: 12rpx;
	background: #f8fafc;
}

.switch-row {
	display: flex;
	justify-content: space-between;
	align-items: center;
	color: #475569;
}

.list {
	display: flex;
	flex-direction: column;
	gap: 10rpx;
}

.item {
	border: 1rpx solid #e2e8f0;
	border-radius: 12rpx;
	padding: 12rpx;
	display: flex;
	justify-content: space-between;
	align-items: center;
}

.item-main {
	display: flex;
	flex-direction: column;
	gap: 6rpx;
}

.item-title {
	font-size: 28rpx;
	font-weight: 600;
	color: #0f172a;
}

.item-desc {
	font-size: 24rpx;
	color: #64748b;
}

.actions {
	display: flex;
	gap: 8rpx;
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

.question-list {
	display: flex;
	flex-direction: column;
	gap: 12rpx;
}

.pagination {
	display: flex;
	justify-content: space-between;
	align-items: center;
	padding: 10rpx 0;
}

.pager-text {
	font-size: 24rpx;
	color: #475569;
}

.question-card {
	border: 1rpx solid #e2e8f0;
	border-radius: 12rpx;
	padding: 0;
	overflow: hidden;
}

.question-summary {
	display: flex;
	justify-content: space-between;
	align-items: center;
	padding: 12rpx;
	background: #f8fafc;
	border-bottom: 1rpx solid #e2e8f0;
}

.summary-left {
	display: flex;
	flex-direction: column;
	gap: 4rpx;
}

.summary-title {
	font-size: 26rpx;
	color: #0f172a;
}

.summary-meta {
	font-size: 22rpx;
	color: #64748b;
}

.question-detail {
	padding: 12rpx;
	display: flex;
	flex-direction: column;
	gap: 8rpx;
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

.opt-input {
	flex: 1;
	border: 1rpx solid #e2e8f0;
	border-radius: 12rpx;
	padding: 10rpx;
	background: #f8fafc;
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

.ghost.mini {
	padding: 8rpx 10rpx;
}

.card-actions {
	display: flex;
	gap: 10rpx;
}

.empty {
	color: #94a3b8;
	font-size: 24rpx;
	text-align: center;
	padding: 12rpx 0;
}
</style>

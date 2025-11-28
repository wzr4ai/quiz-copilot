<template>
	<view class="page">
		<view class="header">
			<view>
				<text class="eyebrow">导入题目</text>
				<text class="title">AI 录题中心</text>
				<text class="desc">先选择题库，再用文本或图片让 AI 识别题目。</text>
			</view>
			<view class="picker-group">
				<picker mode="selector" :range="banks" range-key="title" @change="onBankChange">
					<view class="picker">
						<text>{{ currentBankLabel }}</text>
						<text class="arrow">▼</text>
					</view>
				</picker>
				<button class="ghost mini" @click="toggleCreateBank">新建</button>
			</view>
		</view>

		<view v-if="creatingBank" class="card">
			<text class="card-title">新建题库</text>
			<input v-model="newBankTitle" placeholder="题库名称" class="input" />
			<input v-model="newBankDesc" placeholder="描述（可选）" class="input" />
			<view class="actions">
				<button class="ghost" @click="toggleCreateBank">取消</button>
				<button class="primary" @click="createNewBank">创建</button>
			</view>
		</view>

		<view class="tabs">
			<button :class="['tab', mode === 'text' ? 'active' : '']" @click="setMode('text')">文本识别</button>
			<button :class="['tab', mode === 'image' ? 'active' : '']" @click="setMode('image')">图片识别</button>
		</view>

		<view class="card" v-if="mode === 'text'">
			<textarea
				v-model="inputText"
				placeholder="粘贴题干或知识点，AI 将生成题目与答案"
				class="textarea"
			/>
			<button class="primary" :loading="loading" @click="submitText">生成题目</button>
		</view>

		<view class="card" v-else>
			<view class="upload-box" @click="chooseImage">
				<image v-if="imagePreview" :src="imagePreview" class="preview" mode="aspectFill" />
				<text v-else class="upload-text">上传或拍摄试卷照片</text>
			</view>
			<button class="primary" :loading="loading" :disabled="!imagePath" @click="submitImage">识别试卷</button>
		</view>

		<view class="card" v-if="recognizedQuestions.length">
			<view class="card-header">
				<text class="card-title">识别到的题目</text>
				<text class="hint">可在保存前编辑修正</text>
			</view>

			<view v-for="(question, idx) in recognizedQuestions" :key="idx" class="question-editor">
				<view class="question-header">
					<text class="sub">题目 {{ idx + 1 }}</text>
					<button class="ghost mini danger" @click="removeQuestion(idx)">删除</button>
				</view>
				<view class="row">
					<text class="label">题型</text>
					<view class="chips">
						<view
							v-for="type in questionTypes"
							:key="type.value"
							:class="['chip', question.type === type.value ? 'chip-active' : '']"
							@click="setQuestionType(question, type.value)"
						>
							{{ type.label }}
						</view>
					</view>
				</view>

				<view class="row">
					<text class="label">题干</text>
					<textarea v-model="question.content" class="textarea small" placeholder="输入题干" />
				</view>

				<view v-if="question.type !== 'short_answer'" class="row">
					<text class="label">选项</text>
					<view class="options">
						<view v-for="(opt, oIdx) in question.options" :key="oIdx" class="option">
							<text class="opt-key">{{ opt.key }}</text>
							<input class="opt-input" v-model="opt.text" placeholder="选项内容" />
						</view>
						<button class="ghost mini" @click="addOption(question)">添加选项</button>
					</view>
				</view>

				<view class="row">
					<text class="label">答案</text>
					<input v-model="question.standard_answer" class="input" placeholder="标准答案，如 A 或 文本" />
				</view>
				<view class="row">
					<text class="label">解析</text>
					<textarea v-model="question.analysis" class="textarea tiny" placeholder="可选" />
				</view>
			</view>

			<button class="primary" :loading="saving" @click="saveQuestions">保存到题库</button>
		</view>
	</view>
</template>

<script setup>
import { onLoad } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import {
  aiImageToQuiz,
  aiTextToQuiz,
  createBank,
  fetchBanks,
  getToken,
  getRole,
  saveManualQuestion,
} from '../../services/api'

const mode = ref('text')
const inputText = ref('')
const imagePath = ref('')
const imageFile = ref(null)
const imagePreview = ref('')
const recognizedQuestions = ref([])
const banks = ref([])
const selectedBankId = ref(null)
const creatingBank = ref(false)
const newBankTitle = ref('')
const newBankDesc = ref('')
const loading = ref(false)
const saving = ref(false)
const LAST_BANK_KEY = 'last_import_bank_id'

const questionTypes = [
  { label: '单选', value: 'choice_single' },
  { label: '判断', value: 'choice_judgment' },
  { label: '多选', value: 'choice_multi' },
  { label: '简答', value: 'short_answer' },
]

const currentBankLabel = computed(() => {
  const found = banks.value.find((b) => b.id === selectedBankId.value)
  return found ? found.title : '选择题库'
})

onLoad((options) => {
  if (options && options.mode === 'image') {
    mode.value = 'image'
  }
  if (getRole() !== 'admin') {
    uni.showToast({ title: '需要管理员权限', icon: 'none' })
    return
  }
  loadBanks()
})

const loadBanks = async () => {
  if (!getToken()) {
    uni.showToast({ title: '请先登录后再导入题目', icon: 'none' })
    return
  }
  if (getRole() !== 'admin') {
    uni.showToast({ title: '需要管理员权限', icon: 'none' })
    return
  }
  try {
    const res = await fetchBanks()
    banks.value = res || []
    if (!selectedBankId.value) {
      const saved = uni.getStorageSync(LAST_BANK_KEY)
      const found = banks.value.find((b) => b.id === saved)
      selectedBankId.value = found ? found.id : banks.value[0]?.id || null
    }
  } catch (err) {
    uni.showToast({ title: err.message || '加载题库失败', icon: 'none' })
  }
}

const onBankChange = (event) => {
  const idx = Number(event.detail.value)
  selectedBankId.value = banks.value[idx]?.id
  if (selectedBankId.value) {
    uni.setStorageSync(LAST_BANK_KEY, selectedBankId.value)
  }
}

const setMode = (value) => {
  mode.value = value
}

const toggleCreateBank = () => {
  creatingBank.value = !creatingBank.value
  if (!creatingBank.value) {
    newBankTitle.value = ''
    newBankDesc.value = ''
  }
}

const createNewBank = async () => {
  if (!newBankTitle.value.trim()) {
    return uni.showToast({ title: '请输入题库名称', icon: 'none' })
  }
  try {
    const bank = await createBank({ title: newBankTitle.value, description: newBankDesc.value })
    banks.value.push(bank)
    selectedBankId.value = bank.id
    uni.setStorageSync(LAST_BANK_KEY, bank.id)
    uni.showToast({ title: '题库已创建', icon: 'success' })
    toggleCreateBank()
  } catch (err) {
    uni.showToast({ title: err.message || '创建失败', icon: 'none' })
  }
}

const submitText = async () => {
  if (!getToken()) {
    return uni.showToast({ title: '请先登录', icon: 'none' })
  }
  if (!inputText.value.trim()) {
    return uni.showToast({ title: '请先输入文本', icon: 'none' })
  }
  if (!selectedBankId.value) {
    return uni.showToast({ title: '请选择题库', icon: 'none' })
  }
  loading.value = true
  try {
    const res = await aiTextToQuiz({ bank_id: selectedBankId.value, text: inputText.value })
    recognizedQuestions.value = res || []
    uni.showToast({ title: '已生成题目', icon: 'none' })
  } catch (err) {
    uni.showToast({ title: err.message || '生成失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

const chooseImage = () => {
  uni.chooseImage({
    count: 1,
    success: (res) => {
      imagePath.value = res.tempFilePaths[0]
      imageFile.value = res.tempFiles && res.tempFiles[0]
      imagePreview.value = imagePath.value
    },
  })
}

const toBase64 = (fileObj, path) =>
  new Promise((resolve, reject) => {
    const safeReject = (err) => reject(err || new Error('无法读取图片'))

    // 1) FileReader branch (H5)
    if (fileObj && (fileObj.file || fileObj instanceof Blob)) {
      const reader = new FileReader()
      reader.onload = (e) => {
        const result = (e && e.target && e.target.result) || ''
        resolve(String(result).split(',').pop())
      }
      reader.onerror = () => safeReject(new Error('读取图片失败'))
      reader.readAsDataURL(fileObj.file || fileObj)
      return
    }

    // 2) Data URL path already provided
    if (typeof path === 'string' && path.startsWith('data:')) {
      return resolve(path.split(',').pop())
    }

    // 3) Native FS branch (App/小程序)
    if (uni.getFileSystemManager) {
      uni.getFileSystemManager().readFile({
        filePath: path,
        encoding: 'base64',
        success: (res) => resolve(res.data),
        fail: (err) => safeReject(err),
      })
      return
    }

    // 4) Fallback: fetch as arraybuffer then convert
    if (typeof path === 'string') {
      uni.request({
        url: path,
        method: 'GET',
        responseType: 'arraybuffer',
        success: (res) => {
          try {
            const bytes = new Uint8Array(res.data)
            let binary = ''
            bytes.forEach((b) => (binary += String.fromCharCode(b)))
            resolve(btoa(binary))
          } catch (err) {
            safeReject(err)
          }
        },
        fail: (err) => safeReject(err),
      })
      return
    }

    safeReject()
  })

const submitImage = async () => {
  if (!getToken()) {
    return uni.showToast({ title: '请先登录', icon: 'none' })
  }
  if (!imagePath.value) {
    return uni.showToast({ title: '请先选择图片', icon: 'none' })
  }
  if (!selectedBankId.value) {
    return uni.showToast({ title: '请选择题库', icon: 'none' })
  }
  loading.value = true
  try {
    const base64 = await toBase64(imageFile.value, imagePath.value)
    const res = await aiImageToQuiz({ bank_id: selectedBankId.value, image_base64: base64 })
    recognizedQuestions.value = res || []
    uni.showToast({ title: '识别成功', icon: 'none' })
  } catch (err) {
    uni.showToast({ title: err.message || '识别失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

const addOption = (question) => {
  const nextKey = String.fromCharCode(65 + (question.options?.length || 0))
  if (!question.options) {
    question.options = []
  }
  question.options.push({ key: nextKey, text: '' })
}

const setQuestionType = (question, type) => {
  question.type = type
  if (type === 'short_answer') {
    question.options = []
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

const removeQuestion = (index) => {
  if (index < 0 || index >= recognizedQuestions.value.length) return
  recognizedQuestions.value.splice(index, 1)
}

const saveQuestions = async () => {
  if (!selectedBankId.value) {
    return uni.showToast({ title: '请选择题库', icon: 'none' })
  }
  if (!recognizedQuestions.value.length) {
    return uni.showToast({ title: '请先生成题目', icon: 'none' })
  }
  saving.value = true
  try {
    const tasks = recognizedQuestions.value.map((q) =>
      saveManualQuestion({ ...q, bank_id: selectedBankId.value })
    )
    await Promise.all(tasks)
    uni.showToast({ title: '已保存到题库', icon: 'success' })
    recognizedQuestions.value = []
    inputText.value = ''
    imagePath.value = ''
    imagePreview.value = ''
  } catch (err) {
    uni.showToast({ title: err.message || '保存失败', icon: 'none' })
  } finally {
    saving.value = false
  }
}
</script>

<style>
.page {
	min-height: 100vh;
	padding: 24rpx;
	display: flex;
	flex-direction: column;
	gap: 16rpx;
	background: linear-gradient(180deg, #f7faff 0%, #ffffff 90%);
}

.header {
	background: #0f172a;
	color: #e2e8f0;
	padding: 28rpx;
	border-radius: 20rpx;
	display: flex;
	justify-content: space-between;
	align-items: center;
	gap: 12rpx;
}

.eyebrow {
	font-size: 22rpx;
	letter-spacing: 2rpx;
	color: #94a3b8;
}

.title {
	display: block;
	font-size: 40rpx;
	font-weight: 700;
	margin-top: 8rpx;
}

.desc {
	display: block;
	color: #cbd5e1;
	margin-top: 6rpx;
	font-size: 26rpx;
}

.picker {
	background: rgba(255, 255, 255, 0.08);
	border: 1rpx solid rgba(148, 163, 184, 0.6);
	border-radius: 14rpx;
	padding: 12rpx 16rpx;
	display: flex;
	align-items: center;
	gap: 8rpx;
}

.picker-group {
	display: flex;
	align-items: center;
	gap: 8rpx;
}

.arrow {
	color: #94a3b8;
	font-size: 24rpx;
}

.tabs {
	display: grid;
	grid-template-columns: repeat(2, 1fr);
	gap: 12rpx;
}

.tab {
	border: 1rpx solid #e2e8f0;
	border-radius: 14rpx;
	padding: 14rpx;
	background: #ffffff;
	color: #0f172a;
}

.tab.active {
	background: #22c55e;
	color: #ffffff;
	border-color: #22c55e;
}

.card {
	background: #ffffff;
	border-radius: 18rpx;
	padding: 20rpx;
	display: flex;
	flex-direction: column;
	gap: 14rpx;
	box-shadow: 0 6rpx 24rpx rgba(15, 23, 42, 0.04);
}

.card-header {
	display: flex;
	justify-content: space-between;
	align-items: baseline;
}

.card-title {
	font-size: 30rpx;
	font-weight: 700;
	color: #0f172a;
}

.hint {
	color: #94a3b8;
	font-size: 24rpx;
}

.textarea {
	width: 100%;
	min-height: 280rpx;
	border: 1rpx solid #e2e8f0;
	border-radius: 14rpx;
	padding: 16rpx;
	box-sizing: border-box;
	background: #f8fafc;
}

.textarea.small {
	min-height: 200rpx;
}

.textarea.tiny {
	min-height: 120rpx;
}

.upload-box {
	height: 260rpx;
	border: 1rpx dashed #94a3b8;
	border-radius: 14rpx;
	display: flex;
	align-items: center;
	justify-content: center;
	color: #64748b;
	background: #f8fafc;
}

.preview {
	width: 100%;
	height: 100%;
	border-radius: 12rpx;
}

.upload-text {
	font-size: 26rpx;
	text-align: center;
}

.question-editor {
	border: 1rpx solid #e2e8f0;
	border-radius: 14rpx;
	padding: 16rpx;
	display: flex;
	flex-direction: column;
	gap: 12rpx;
}

.question-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
}

.sub {
	color: #475569;
	font-size: 24rpx;
}

.row {
	display: flex;
	flex-direction: column;
	gap: 8rpx;
}

.label {
	font-size: 26rpx;
	color: #475569;
}

.chips {
	display: flex;
	gap: 10rpx;
	flex-wrap: wrap;
}

.chip {
	padding: 10rpx 16rpx;
	border-radius: 12rpx;
	border: 1rpx solid #cbd5e1;
	color: #0f172a;
}

.chip-active {
	background: #0ea5e9;
	color: #ffffff;
	border-color: #0ea5e9;
}

.options {
	display: flex;
	flex-direction: column;
	gap: 10rpx;
}

.option {
	display: flex;
	align-items: center;
	gap: 10rpx;
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

.opt-input {
	flex: 1;
	border: 1rpx solid #e2e8f0;
	border-radius: 12rpx;
	padding: 10rpx 12rpx;
	background: #f8fafc;
}

.input {
	border: 1rpx solid #e2e8f0;
	border-radius: 12rpx;
	padding: 12rpx;
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
	align-self: flex-start;
	padding: 10rpx 16rpx;
}

.ghost.mini.danger {
	color: #dc2626;
	border-color: #fecdd3;
	background: #fff1f2;
}
</style>

const API_BASE = 'http://localhost:8000/api/v1'

const request = (url, { method = 'GET', data = {} } = {}) => {
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${API_BASE}${url}`,
      method,
      data,
      header: { 'Content-Type': 'application/json' },
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
        } else {
          reject(new Error(res.data?.detail || '请求失败'))
        }
      },
      fail: (err) => reject(err),
    })
  })
}

export const fetchBanks = () => request('/banks')
export const createBank = (payload) => request('/banks', { method: 'POST', data: payload })
export const aiTextToQuiz = (payload) => request('/questions/ai/text-to-quiz', { method: 'POST', data: payload })
export const aiImageToQuiz = (payload) => request('/questions/ai/image-to-quiz', { method: 'POST', data: payload })
export const saveManualQuestion = (payload) => request('/questions/manual', { method: 'POST', data: payload })
export const updateQuestionApi = (questionId, payload) =>
  request(`/questions/${questionId}`, { method: 'PUT', data: payload })
export const startSession = (bankId, mode = 'random') =>
  request(`/study/session/start?bank_id=${bankId}&mode=${mode}`)
export const submitSession = (payload) => request('/study/submit', { method: 'POST', data: payload })
export const listWrongQuestions = () => request('/study/wrong')

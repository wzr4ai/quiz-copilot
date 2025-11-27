const API_BASE = 'https://fnos.dfwzr.com:8233/api/v1'

export const getToken = () => uni.getStorageSync('token')
export const getRole = () => uni.getStorageSync('role')
export const getUsername = () => uni.getStorageSync('username')
export const setAuth = ({ token, role, username }) => {
  if (token) uni.setStorageSync('token', token)
  if (role) uni.setStorageSync('role', role)
  if (username) uni.setStorageSync('username', username)
}
export const clearToken = () => {
  uni.removeStorageSync('token')
  uni.removeStorageSync('role')
  uni.removeStorageSync('username')
}

const request = (url, { method = 'GET', data = {} } = {}) => {
  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${API_BASE}${url}`,
      method,
      data,
      header: headers,
      success: (res) => {
        if (res.statusCode === 401) {
          clearToken()
        }
        if (res.statusCode >= 200 && res.statusCode < 300) return resolve(res.data)
        reject(new Error(res.data?.detail || `请求失败(${res.statusCode})`))
      },
      fail: (err) => reject(err),
    })
  })
}

export const login = ({ username, password }) =>
  new Promise((resolve, reject) => {
    uni.request({
      url: `${API_BASE}/auth/login`,
      method: 'POST',
      data: `username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`,
      header: { 'Content-Type': 'application/x-www-form-urlencoded' },
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300 && res.data?.access_token) {
          setAuth({ token: res.data.access_token, role: res.data.role, username: res.data.username })
          resolve(res.data)
        } else {
          reject(new Error(res.data?.detail || '登录失败'))
        }
      },
      fail: (err) => reject(err),
    })
  })

export const register = ({ username, password }) =>
  request('/auth/register', { method: 'POST', data: { username, password } }).then((res) => {
    if (res?.access_token) setAuth({ token: res.access_token, role: res.role, username: res.username })
    return res
  })

export const fetchBanks = () => request('/banks')
export const createBank = (payload) => request('/banks', { method: 'POST', data: payload })
export const updateBank = (bankId, payload) =>
  request(`/banks/${bankId}`, { method: 'PUT', data: payload })
export const deleteBank = (bankId) => request(`/banks/${bankId}`, { method: 'DELETE' })
export const aiTextToQuiz = (payload) => request('/questions/ai/text-to-quiz', { method: 'POST', data: payload })
export const aiImageToQuiz = (payload) => request('/questions/ai/image-to-quiz', { method: 'POST', data: payload })
export const saveManualQuestion = (payload) => request('/questions/manual', { method: 'POST', data: payload })
export const updateQuestionApi = (questionId, payload) =>
  request(`/questions/${questionId}`, { method: 'PUT', data: payload })
export const deleteQuestion = (questionId) => request(`/questions/${questionId}`, { method: 'DELETE' })
export const fetchQuestions = (bankId) =>
  request(`/questions${bankId ? `?bank_id=${bankId}` : ''}`)
export const batchImportQuestions = (payload) =>
  request('/questions/ai/batch-import', { method: 'POST', data: payload })
export const fetchFavoriteQuestions = () => request('/questions/favorites')
export const favoriteQuestion = (questionId) =>
  request(`/questions/${questionId}/favorite`, { method: 'POST' })
export const unfavoriteQuestion = (questionId) =>
  request(`/questions/${questionId}/favorite`, { method: 'DELETE' })
export const startSession = (bankId, mode = 'random') =>
  request(`/study/session/start?${bankId ? `bank_id=${bankId}&` : ''}mode=${mode}`)
export const submitSession = (payload) => request('/study/submit', { method: 'POST', data: payload })
export const listWrongQuestions = () => request('/study/wrong')

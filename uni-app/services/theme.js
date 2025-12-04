const THEME_KEY = 'theme-preference'
const VALID = ['light', 'dark', 'system']

let mediaQuery
let systemListenerBound = false
const listeners = new Set()

const getStoredPreference = () => uni.getStorageSync(THEME_KEY) || 'system'

const detectSystemTheme = () => {
  if (typeof window !== 'undefined' && window.matchMedia) {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }
  try {
    const info = uni.getSystemInfoSync?.()
    if (info?.theme === 'dark') return 'dark'
  } catch (err) {
    // ignore
  }
  return 'light'
}

const notify = (theme, preference) => {
  listeners.forEach((cb) => cb(theme, preference))
}

const applyThemeClass = (theme, preference) => {
  const root = typeof document !== 'undefined' ? document.documentElement : null
  if (root) {
    root.setAttribute('data-theme', theme)
    root.style.setProperty('color-scheme', theme === 'dark' ? 'dark' : 'light')
  }
  notify(theme, preference || getStoredPreference())
}

const handleMediaChange = (e) => {
  if (getStoredPreference() === 'system') {
    applyThemeClass(e.matches ? 'dark' : 'light', 'system')
  }
}

const bindSystemListener = () => {
  if (systemListenerBound) return
  systemListenerBound = true
  if (typeof window !== 'undefined' && window.matchMedia) {
    mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handleMediaChange)
    } else if (mediaQuery.addListener) {
      mediaQuery.addListener(handleMediaChange)
    }
    return
  }
  if (typeof uni !== 'undefined' && typeof uni.onThemeChange === 'function') {
    uni.onThemeChange((res) => {
      if (getStoredPreference() === 'system') {
        applyThemeClass(res.theme === 'dark' ? 'dark' : 'light', 'system')
      }
    })
  }
}

export const resolveTheme = (preference = getStoredPreference()) =>
  preference === 'system' ? detectSystemTheme() : preference

export const getThemePreference = () => getStoredPreference()

export const getActiveTheme = () => resolveTheme(getStoredPreference())

export const setThemePreference = (preference) => {
  const pref = VALID.includes(preference) ? preference : 'system'
  uni.setStorageSync(THEME_KEY, pref)
  const theme = resolveTheme(pref)
  applyThemeClass(theme, pref)
  bindSystemListener()
  return theme
}

export const initTheme = () => {
  const pref = getStoredPreference()
  const theme = resolveTheme(pref)
  applyThemeClass(theme, pref)
  bindSystemListener()
}

export const subscribeTheme = (callback) => {
  if (typeof callback !== 'function') return () => {}
  listeners.add(callback)
  return () => listeners.delete(callback)
}

export const THEME_STORAGE_KEY = 'firebreak-theme'

function browserStorage() {
  try {
    return globalThis.localStorage
  } catch {
    return null
  }
}

export function initializeTheme(root = globalThis.document?.documentElement, storage = browserStorage()) {
  let savedTheme
  try {
    savedTheme = storage?.getItem(THEME_STORAGE_KEY)
  } catch {
    // A blocked storage API should not prevent the app from loading.
  }
  const theme = savedTheme === 'light' ? 'light' : 'dark'
  if (root) root.dataset.theme = theme
  return theme
}

export function setTheme(theme, root = globalThis.document?.documentElement, storage = browserStorage()) {
  if (theme !== 'light' && theme !== 'dark') throw new Error('Invalid theme')
  if (root) root.dataset.theme = theme
  try {
    storage?.setItem(THEME_STORAGE_KEY, theme)
  } catch {
    // The current page can still use the chosen theme when storage is blocked.
  }
  return theme
}

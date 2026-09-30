import assert from 'node:assert/strict'
import test from 'node:test'
import { initializeTheme, setTheme, THEME_STORAGE_KEY } from '../src/theme.js'

function environment(savedTheme = null) {
  const values = new Map(savedTheme === null ? [] : [[THEME_STORAGE_KEY, savedTheme]])
  return {
    root: { dataset: {} },
    storage: {
      getItem: (key) => values.get(key) ?? null,
      setItem: (key, value) => values.set(key, value),
    },
    values,
  }
}

test('defaults to Dark without a saved preference', () => {
  const { root, storage } = environment()
  assert.equal(initializeTheme(root, storage), 'dark')
  assert.equal(root.dataset.theme, 'dark')
})

test('switches to Light, stores it, and restores it on a new root', () => {
  const { root, storage, values } = environment()
  initializeTheme(root, storage)
  assert.equal(setTheme('light', root, storage), 'light')
  assert.equal(root.dataset.theme, 'light')
  assert.equal(values.get(THEME_STORAGE_KEY), 'light')

  const reloadedRoot = { dataset: {} }
  assert.equal(initializeTheme(reloadedRoot, storage), 'light')
  assert.equal(reloadedRoot.dataset.theme, 'light')
})

test('switches back to Dark and persists the change', () => {
  const { root, storage, values } = environment('light')
  initializeTheme(root, storage)
  assert.equal(setTheme('dark', root, storage), 'dark')
  assert.equal(root.dataset.theme, 'dark')
  assert.equal(values.get(THEME_STORAGE_KEY), 'dark')
})

test('ignores unknown saved values and works when storage is blocked', () => {
  const { root, storage } = environment('unexpected')
  assert.equal(initializeTheme(root, storage), 'dark')
  const blockedStorage = {
    getItem: () => { throw new Error('blocked') },
    setItem: () => { throw new Error('blocked') },
  }
  assert.equal(initializeTheme(root, blockedStorage), 'dark')
  assert.equal(setTheme('light', root, blockedStorage), 'light')
  assert.equal(root.dataset.theme, 'light')
})

import assert from 'node:assert/strict'
import test from 'node:test'
import { initializeTheme } from '../src/theme.js'

test('always applies the light theme', () => {
  const root = { dataset: {} }
  assert.equal(initializeTheme(root), 'light')
  assert.equal(root.dataset.theme, 'light')
})

test('ignores a dark preference saved by an earlier version', () => {
  const root = { dataset: { theme: 'dark' } }
  assert.equal(initializeTheme(root), 'light')
  assert.equal(root.dataset.theme, 'light')
})

test('does not throw without a document root', () => {
  assert.equal(initializeTheme(null), 'light')
})

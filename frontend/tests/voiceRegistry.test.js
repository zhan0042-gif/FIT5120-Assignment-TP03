import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'

const {
  nestedScope,
  registerContext,
  registerTargets,
  resetVoiceRegistry,
  snapshotContext,
  snapshotTargets,
} = await import('../src/voice/registry.js')

afterEach(() => resetVoiceRegistry())

test('a snapshot calls every getter afresh, so labels are never stale', () => {
  let label = 'Before'
  registerTargets(() => [{ id: 'a', label }])
  assert.equal(snapshotTargets()[0].label, 'Before')
  label = 'After'
  assert.equal(snapshotTargets()[0].label, 'After')
})

test('unregistering removes only that component’s targets', () => {
  const removeFirst = registerTargets(() => [{ id: 'first' }])
  registerTargets(() => [{ id: 'second' }])
  removeFirst()
  assert.deepEqual(snapshotTargets().map((target) => target.id), ['second'])
})

test('targets keep registration order, so the layout’s globals come first', () => {
  registerTargets(() => [{ id: 'global' }])
  registerTargets(() => [{ id: 'page' }, { id: 'page-2' }])
  assert.deepEqual(snapshotTargets().map((target) => target.id), ['global', 'page', 'page-2'])
})

test('context from several components merges', () => {
  registerContext(() => ({ page: 'plan-builder' }))
  registerContext(() => ({ step: 'people' }))
  assert.deepEqual(snapshotContext(), { page: 'plan-builder', step: 'people' })
})

test('context defaults to no page and no step', () => {
  assert.deepEqual(snapshotContext(), { page: null, step: null })
})

test('a nested scope is active only when every enclosing scope is', () => {
  assert.equal(nestedScope(() => true, () => true)(), true)
  assert.equal(nestedScope(() => false, () => true)(), false)
  assert.equal(nestedScope(() => true, () => false)(), false)
})

import assert from 'node:assert/strict'
import test from 'node:test'
import { PICK_GRACE_MS, acceptsPick, isPointerClick } from '../src/wizard/pick.js'

test('a pick right after a question appears is ignored, so a double-click cannot answer twice', () => {
  assert.equal(acceptsPick(1000, 1000 + PICK_GRACE_MS - 1), false)
  assert.equal(acceptsPick(1000, 1000 + PICK_GRACE_MS), true)
})

test('only a real pointer click advances a radio choice; arrow keys only select', () => {
  assert.equal(isPointerClick({ detail: 1 }), true)
  assert.equal(isPointerClick({ detail: 2 }), true)
  assert.equal(isPointerClick({ detail: 0 }), false)
})

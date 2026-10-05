import assert from 'node:assert/strict'
import test from 'node:test'
import { EMPTY_MESSAGE, SAFETY_NOTICE } from '../src/utils/safetyGuidanceCopy.js'

test('the fixed notice says this is not for emergencies and gives 000', () => {
  assert.match(SAFETY_NOTICE, /not for emergencies/i)
  assert.match(SAFETY_NOTICE, /\b000\b/)
})

test('the empty message does not promise guidance', () => {
  assert.match(EMPTY_MESSAGE, /no guidance/i)
})

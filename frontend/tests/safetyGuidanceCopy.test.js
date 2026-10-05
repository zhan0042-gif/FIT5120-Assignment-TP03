import assert from 'node:assert/strict'
import test from 'node:test'
import {
  EMERGENCY_MESSAGE,
  EMPTY_MESSAGE,
  MAX_QUESTION_LENGTH,
  NO_MATCH_MESSAGE,
  SAFETY_NOTICE,
  UNAVAILABLE_MESSAGE,
} from '../src/utils/safetyGuidanceCopy.js'

test('the fixed notice says this is not for emergencies and gives 000', () => {
  assert.match(SAFETY_NOTICE, /not for emergencies/i)
  assert.match(SAFETY_NOTICE, /\b000\b/)
})

test('the empty message does not promise guidance', () => {
  assert.match(EMPTY_MESSAGE, /no guidance/i)
})

test('the emergency message tells the person to call 000', () => {
  assert.match(EMERGENCY_MESSAGE, /call 000 now/i)
})

test('the no-match message says it cannot predict or decide, and points to the suggestions', () => {
  assert.match(NO_MATCH_MESSAGE, /reviewed answer/i)
  assert.match(NO_MATCH_MESSAGE, /predict/i)
  assert.match(NO_MATCH_MESSAGE, /suggested questions/i)
})

test('the unavailable message points to the suggested questions', () => {
  assert.match(UNAVAILABLE_MESSAGE, /suggested questions/i)
})

test('the length limit matches the backend', () => {
  assert.equal(MAX_QUESTION_LENGTH, 300)
})

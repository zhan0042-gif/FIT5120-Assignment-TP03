import assert from 'node:assert/strict'
import test from 'node:test'
import { locationNote } from '../src/utils/safetyGuidanceNote.js'

test('no note when the location conditions were applied', () => {
  assert.equal(locationNote({ applied: true, locationVerified: true }), null)
})

test('asks for a verified address when there is none', () => {
  assert.equal(locationNote({ applied: false, locationVerified: false }), 'verify')
})

test('does not ask for an address the household already verified', () => {
  assert.equal(locationNote({ applied: false, locationVerified: true }), 'unavailable')
})

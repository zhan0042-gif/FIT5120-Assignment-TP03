import assert from 'node:assert/strict'
import test from 'node:test'
import { isStale } from '../src/utils/guidanceFreshness.js'

const on = (iso) => { const [y, m, d] = iso.split('-').map(Number); return new Date(y, m - 1, d) }

test('a card checked today is not stale', () => {
  assert.equal(isStale('2026-10-05', on('2026-10-05')), false)
})

test('a card is still fresh on the day exactly six months later', () => {
  assert.equal(isStale('2026-10-05', on('2027-04-05')), false)
})

test('a card is stale the day after six months have passed', () => {
  assert.equal(isStale('2026-10-05', on('2027-04-06')), true)
})

test('month-end dates clamp to the last day of the target month', () => {
  assert.equal(isStale('2026-08-31', on('2027-02-28')), false)
  assert.equal(isStale('2026-08-31', on('2027-03-01')), true)
})

test('a date in the future is not stale', () => {
  assert.equal(isStale('2026-12-01', on('2026-10-05')), false)
})

test('a date that cannot be read counts as stale rather than silently fresh', () => {
  assert.equal(isStale('not-a-date', on('2026-10-05')), true)
  assert.equal(isStale(undefined, on('2026-10-05')), true)
})

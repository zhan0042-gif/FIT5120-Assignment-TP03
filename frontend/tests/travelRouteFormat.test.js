import assert from 'node:assert/strict'
import { test } from 'node:test'

const { routeKilometres, routeMinutes } = await import('../src/utils/travelRouteFormat.js')

test('distances are shown in kilometres with one decimal, like the fire map', () => {
  assert.equal(routeKilometres(22_400), '22.4')
  assert.equal(routeKilometres(960), '1.0')
  assert.equal(routeKilometres(0), '0.0')
})

test('driving times are whole minutes and never read as zero', () => {
  assert.equal(routeMinutes(31 * 60), 31)
  assert.equal(routeMinutes(31 * 60 + 29), 31)
  assert.equal(routeMinutes(31 * 60 + 30), 32)
  assert.equal(routeMinutes(5), 1)
})

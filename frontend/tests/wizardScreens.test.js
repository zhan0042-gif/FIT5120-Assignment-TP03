import assert from 'node:assert/strict'
import test from 'node:test'
import {
  SCREENS, firstIncompleteScreen, nextScreen, previousScreen, resolveScreenParam, screenComplete, screenOfSection,
} from '../src/wizard/screens.js'

const completion = (statuses) => ({
  sections: Object.entries(statuses).map(([section, status]) => ({ section, status })),
})
const ALL = {
  household_profile: 'complete', member_locations: 'complete', transport: 'complete',
  backup_transport: 'complete', primary_destination: 'complete', backup_destination: 'complete',
  responsibilities: 'complete',
}

test('five screens cover the seven backend sections in order', () => {
  assert.deepEqual(SCREENS.map((screen) => screen.id), ['household', 'daytime', 'vehicles', 'places', 'jobs'])
  assert.deepEqual(SCREENS.flatMap((screen) => screen.sections), [
    'household_profile', 'member_locations', 'transport', 'backup_transport',
    'primary_destination', 'backup_destination', 'responsibilities',
  ])
})

test('a section maps to the screen that holds it', () => {
  assert.equal(screenOfSection('backup_transport'), 'vehicles')
  assert.equal(screenOfSection('backup_destination'), 'places')
  assert.equal(screenOfSection('nope'), null)
})

test('a screen is complete only when every one of its sections is', () => {
  assert.equal(screenComplete(completion(ALL), 'vehicles'), true)
  assert.equal(screenComplete(completion({ ...ALL, backup_transport: 'needs_information' }), 'vehicles'), false)
  assert.equal(screenComplete(null, 'household'), false)
})

test('first incomplete screen, or null when all are complete', () => {
  assert.equal(firstIncompleteScreen(completion({ ...ALL, primary_destination: 'needs_information' })), 'places')
  assert.equal(firstIncompleteScreen(completion(ALL)), null)
})

test('next and previous screens; review follows the last', () => {
  assert.equal(nextScreen('household'), 'daytime')
  assert.equal(nextScreen('jobs'), 'review')
  assert.equal(previousScreen('daytime'), 'household')
  assert.equal(previousScreen('household'), null)
})

test('the section parameter accepts screens, sections, legacy names and review', () => {
  assert.equal(resolveScreenParam('review'), 'review')
  assert.equal(resolveScreenParam('vehicles'), 'vehicles')
  assert.equal(resolveScreenParam('backup_transport'), 'vehicles')
  assert.equal(resolveScreenParam('responsibilities'), 'jobs')
  assert.equal(resolveScreenParam('people'), 'household')
  assert.equal(resolveScreenParam('destinations'), 'places')
  assert.equal(resolveScreenParam('bogus'), null)
  assert.equal(resolveScreenParam(['x']), null)
})

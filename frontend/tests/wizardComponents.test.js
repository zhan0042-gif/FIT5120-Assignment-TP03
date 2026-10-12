import assert from 'node:assert/strict'
import test from 'node:test'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createEmptyHouseholdPlan } from '../src/domain/householdPlan.js'
import { addAnimal, addMember, setHasVehicle } from '../src/wizard/formActions.js'
import { SCREENS } from '../src/wizard/screens.js'
import { importComponent } from './helpers/loadComponent.js'

const render = async (path, props) => {
  const Component = await importComponent(path)
  return renderToString(createSSRApp(Component, props))
}

const sectionsDone = (done) => ({
  sections: SCREENS.flatMap((screen) => screen.sections).map((section, index) => ({
    section, status: index < done ? 'complete' : 'needs_information',
  })),
  immediate_checks: [],
})

test('the progress bar reports N of 5 in text, in ARIA, and per screen', async () => {
  // Four backend sections done: household, daytime and both vehicle sections.
  const html = await render('../src/components/wizard/ProgressBar.vue', {
    completion: sectionsDone(4), currentScreen: 'places', loading: false,
  })
  assert.match(html, /role="progressbar"/)
  assert.match(html, /aria-valuenow="3"/)
  assert.match(html, /aria-valuemax="5"/)
  assert.match(html, /3 of 5 parts complete/)
  assert.match(html, /aria-current="step"/)
  for (const label of ['Household', 'Daytime', 'Vehicles', 'Places', 'Jobs']) assert.match(html, new RegExp(label))
})

test('a screen with one unfinished section is not counted complete', async () => {
  // Three done: household, daytime, transport; backup_transport is not.
  const html = await render('../src/components/wizard/ProgressBar.vue', {
    completion: sectionsDone(3), currentScreen: null, loading: false,
  })
  assert.match(html, /2 of 5 parts complete/)
})

test('the progress bar shows 0 of 5 before the first save and survives loading', async () => {
  const none = await render('../src/components/wizard/ProgressBar.vue', { completion: null, currentScreen: 'household', loading: false })
  assert.match(none, /0 of 5 parts complete/)
  const loading = await render('../src/components/wizard/ProgressBar.vue', { completion: sectionsDone(2), currentScreen: null, loading: true })
  assert.match(loading, /2 of 5 parts complete/)
})

test('review lists five rows, each with an Edit button and an honest status', async () => {
  const plan = createEmptyHouseholdPlan()
  addMember(plan).display_name = 'Maya'
  addAnimal(plan)
  setHasVehicle(plan, false)
  const html = await render('../src/components/wizard/ReviewScreen.vue', {
    plan, completion: sectionsDone(2), completionLoading: false, saving: false, error: null,
  })
  assert.equal((html.match(/>Edit</g) ?? []).length, 5)
  assert.match(html, /Maya/)
  assert.match(html, /No private vehicle/)
  assert.equal((html.match(/>Complete</g) ?? []).length, 2)
  assert.match(html, /Save &amp; Review Plan/)
})

test('a failed save is shown on the review screen', async () => {
  const html = await render('../src/components/wizard/ReviewScreen.vue', {
    plan: createEmptyHouseholdPlan(), completion: sectionsDone(7), completionLoading: false, saving: false, error: 'Your plan could not be saved.',
  })
  assert.match(html, /role="alert"[^>]*>Your plan could not be saved\./)
})

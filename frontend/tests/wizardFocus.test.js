import assert from 'node:assert/strict'
import test from 'node:test'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createEmptyHouseholdPlan } from '../src/domain/householdPlan.js'
import { focusAfterRender } from '../src/wizard/focus.js'
import { addAnimal, addJob, addMember, setHasVehicle } from '../src/wizard/formActions.js'
import { importComponent } from './helpers/loadComponent.js'

test('focusAfterRender focuses the element with the given id once rendering is done', async () => {
  const focused = []
  globalThis.document = { getElementById: (id) => ({ focus: () => focused.push(id) }) }
  try {
    await focusAfterRender('member:1:name')
    assert.deepEqual(focused, ['member:1:name'])
  } finally {
    delete globalThis.document
  }
})

test('focusAfterRender does nothing when the element is missing', async () => {
  globalThis.document = { getElementById: () => null }
  try {
    await focusAfterRender('nope')
  } finally {
    delete globalThis.document
  }
})

const screen = async (name, plan) =>
  renderToString(createSSRApp(await importComponent(`../src/components/wizard/screens/${name}.vue`), { plan, errors: {} }))

test('every Add another button has a stable id so Remove can send focus back to it', async () => {
  const plan = createEmptyHouseholdPlan()
  addMember(plan)
  addAnimal(plan)
  assert.match(await screen('HouseholdScreen', plan), /id="add-person"/)
  assert.match(await screen('HouseholdScreen', plan), /id="add-animal"/)
  const vehicles = createEmptyHouseholdPlan()
  setHasVehicle(vehicles, true)
  assert.match(await screen('VehiclesScreen', vehicles), /id="add-vehicle"/)
  assert.match(await screen('PlacesScreen', createEmptyHouseholdPlan()), /id="add-place"/)
  const jobs = createEmptyHouseholdPlan()
  addMember(jobs)
  addJob(jobs)
  assert.match(await screen('JobsScreen', jobs), /id="add-job"/)
})

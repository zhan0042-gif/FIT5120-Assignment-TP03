import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import { saveAndReview } from '../src/utils/planReviewNavigation.js'

const source = async (path) => readFile(new URL(path, import.meta.url), 'utf8')

test('the plan view saves one draft through the household store and the API client', async () => {
  const plan = await source('../src/views/PlanBuilderView.vue')
  const store = await source('../src/stores/household.js')
  const client = await source('../src/api/client.js')

  assert.equal((plan.match(/householdStore\.savePlan\(draft\.value\)/g) ?? []).length, 1)
  assert.match(store, /api\.saveHouseholdPlan\(id, next\)/)
  assert.match(client, /method: 'PUT',[\s\S]*?body: JSON\.stringify\(plan\)/)
})

test('dirty Review saves before navigation', async () => {
  const calls = []
  const result = await saveAndReview({
    needsSave: true,
    save: async () => { calls.push('save'); return true },
    navigate: async (path) => { calls.push(path) },
  })
  assert.equal(result, true)
  assert.deepEqual(calls, ['save', '/overview'])
})

test('failed Review save stays on Review', async () => {
  const calls = []
  const result = await saveAndReview({
    needsSave: true,
    save: async () => { calls.push('save'); return false },
    navigate: async (path) => { calls.push(path) },
  })
  assert.equal(result, false)
  assert.deepEqual(calls, ['save'])
})

test('clean saved Review navigates without saving again', async () => {
  const calls = []
  const result = await saveAndReview({
    needsSave: false,
    save: async () => { calls.push('save'); return true },
    navigate: async (path) => { calls.push(path) },
  })
  assert.equal(result, true)
  assert.deepEqual(calls, ['/overview'])
  const plan = await source('../src/views/PlanBuilderView.vue')
  assert.match(plan, /needsSave: hasUnsavedChanges\.value \|\| !householdStore\.planExists/)
  const review = await source('../src/components/wizard/ReviewScreen.vue')
  assert.match(review, /Save &amp; Review Plan/)
})

test('Welcome introduces all four journey steps', async () => {
  const welcome = await source('../src/views/WelcomeView.vue')
  assert.match(welcome, /How to use FIREBREAK/)
  assert.equal((welcome.match(/<section class="journey"/g) ?? []).length, 1)
  assert.ok(welcome.indexOf('<section class="journey"') < welcome.indexOf('<div class="beats">'))
  assert.doesNotMatch(welcome, /Ranked for your household|preview-card/)
  for (const heading of [
    'Build your plan',
    'Review your plan',
    'Explore your local fire history',
    'Test your plan',
  ]) assert.match(welcome, new RegExp(`<strong>${heading}</strong>`))
  assert.match(welcome, /Start my plan/)
  assert.match(welcome, /Continue my plan/)
  assert.match(welcome, /See where I am/)
  assert.match(welcome, /@media \(max-width: 520px\)[^\n]*\.journey li span \{ display: none; \}/)
})

test('Overview and Fire Map omit the redundant Next links', async () => {
  const overview = await source('../src/views/OverviewView.vue')
  const map = await source('../src/views/MapView.vue')
  assert.doesNotMatch(overview, /Next: Explore your local fire history|next-step/)
  assert.doesNotMatch(map, /Next: Test your household plan|next-step/)
})

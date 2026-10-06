import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const source = (path) => readFile(new URL(path, import.meta.url), 'utf8')

test('the plan view is the wizard host and saves only through the household store', async () => {
  const view = await source('../src/views/PlanBuilderView.vue')
  for (const name of ['WizardShell', 'ProgressBar', 'SectionSummary', 'ReviewScreen']) {
    assert.match(view, new RegExp(`import ${name} from`))
  }
  assert.match(view, /useWizard\(draft\)/)
  assert.equal((view.match(/householdStore\.savePlan\(draft\.value\)/g) ?? []).length, 1)
  assert.match(view, /resolveSectionParam\(route\.query\.section\)/)
  assert.match(view, /firstIncompleteSection\(householdStore\.completion\)/)
  assert.match(view, /needsSave: hasUnsavedChanges\.value \|\| !householdStore\.planExists/)
  assert.match(view, /saveAndReview\(/)
})

test('unsaved answers are guarded on reload and on leaving the route', async () => {
  const view = await source('../src/views/PlanBuilderView.vue')
  assert.match(view, /beforeunload/)
  assert.match(view, /onBeforeRouteLeave/)
  assert.match(view, /removeEventListener\('beforeunload'/)
})

test('the old stepper markup is gone from the view', async () => {
  const view = await source('../src/views/PlanBuilderView.vue')
  assert.doesNotMatch(view, /class="stepper"/)
  assert.doesNotMatch(view, /HouseholdMembersForm|TransportForm|ArrangementsForm|ResponsibilitiesForm/)
})

test('the final action label lives on the review screen', async () => {
  const review = await source('../src/components/wizard/ReviewScreen.vue')
  assert.match(review, /Save &amp; Review Plan/)
})

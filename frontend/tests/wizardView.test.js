import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const source = (path) => readFile(new URL(path, import.meta.url), 'utf8')
const view = () => source('../src/views/PlanBuilderView.vue')

test('the plan view hosts the five screens, the shell, the progress bar and review', async () => {
  const text = await view()
  for (const name of ['ScreenShell', 'ProgressBar', 'ReviewScreen', 'HouseholdScreen', 'DaytimeScreen', 'VehiclesScreen', 'PlacesScreen', 'JobsScreen']) {
    assert.match(text, new RegExp(`import ${name} from`))
  }
})

test('the view saves only through the household store, once, after finalising and validating', async () => {
  const text = await view()
  assert.equal((text.match(/householdStore\.savePlan\(draft\.value\)/g) ?? []).length, 1)
  const save = text.slice(text.indexOf('async function saveScreen'))
  assert.ok(save.indexOf('finalisePlan(') < save.indexOf('validateScreen('))
  assert.ok(save.indexOf('validateScreen(') < save.indexOf('await save()'))
})

test('the starting screen comes from the section parameter, then the first incomplete screen', async () => {
  const text = await view()
  assert.match(text, /resolveScreenParam\(route\.query\.section\)/)
  assert.match(text, /firstIncompleteScreen\(householdStore\.completion\)/)
})

test('unsaved answers are compared on finalised clones and guarded on reload and on leaving the route', async () => {
  const text = await view()
  assert.match(text, /finalisedClone\(draft\.value\)/)
  assert.match(text, /finalisedClone\(householdStore\.plan\)/)
  assert.match(text, /beforeunload/)
  assert.match(text, /onBeforeRouteLeave/)
  assert.match(text, /removeEventListener\('beforeunload'/)
})

test('editing from review returns to review after saving, and Back returns there too', async () => {
  const text = await view()
  assert.match(text, /function editScreen/)
  assert.match(text, /returnToReview\.value = true/)
  assert.match(text, /goTo\('review'\)/)
  const back = text.slice(text.indexOf('function back'), text.indexOf('function back') + 200)
  assert.match(back, /returnToReview/)
})

test('the old question flow is gone from the view', async () => {
  const text = await view()
  assert.doesNotMatch(text, /WizardShell|SectionSummary|useWizard|buildSteps|HouseholdMembersForm/)
})

test('the final action label lives on the review screen', async () => {
  assert.match(await source('../src/components/wizard/ReviewScreen.vue'), /Save &amp; Review Plan/)
})

import assert from 'node:assert/strict'
import test from 'node:test'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createEmptyHouseholdPlan } from '../src/domain/householdPlan.js'
import { SECTIONS, buildSteps } from '../src/wizard/flow.js'
import { importComponent } from './helpers/loadComponent.js'

const render = async (path, props) => {
  const Component = await importComponent(path)
  return renderToString(createSSRApp(Component, props))
}

const completion = (done) => ({
  sections: SECTIONS.map((section, index) => ({
    section: section.id,
    status: index < done ? 'complete' : 'needs_information',
  })),
  immediate_checks: [],
})

test('the progress bar reports N of 7 in text, in ARIA, and per section', async () => {
  const html = await render('../src/components/wizard/ProgressBar.vue', {
    completion: completion(3), currentSection: 'transport', loading: false,
  })
  assert.match(html, /role="progressbar"/)
  assert.match(html, /aria-valuenow="3"/)
  assert.match(html, /aria-valuemax="7"/)
  assert.match(html, /3 of 7 sections complete/)
  assert.match(html, /Complete/)
  assert.match(html, /Needs information/)
  assert.match(html, /aria-current="step"/)
})

test('the progress bar shows 0 of 7 before the first save and survives loading', async () => {
  const none = await render('../src/components/wizard/ProgressBar.vue', {
    completion: null, currentSection: 'household_profile', loading: false,
  })
  assert.match(none, /0 of 7 sections complete/)
  const loading = await render('../src/components/wizard/ProgressBar.vue', {
    completion: completion(2), currentSection: null, loading: true,
  })
  assert.match(loading, /2 of 7 sections complete/)
})

test('the shell renders a text question with a label, helper, Skip and Next', async () => {
  const plan = createEmptyHouseholdPlan()
  const step = buildSteps(plan)[0]
  const html = await render('../src/components/wizard/WizardShell.vue', { step, plan, error: null, canGoBack: false })
  assert.match(html, /What is your name\?/)
  assert.match(html, /Skip for now/)
  assert.match(html, />Next</)
  assert.doesNotMatch(html, />Back</)
  assert.match(html, /<label/)
})

test('the shell shows an error as an alert tied to the input, and Back when allowed', async () => {
  const plan = createEmptyHouseholdPlan()
  const step = buildSteps(plan)[0]
  const html = await render('../src/components/wizard/WizardShell.vue', {
    step, plan, error: 'Please describe the animal.', canGoBack: true,
  })
  assert.match(html, /role="alert"[^>]*>Please describe the animal\./)
  assert.match(html, /aria-describedby/)
  assert.match(html, />Back</)
})

test('yes/no, choice, multi, address and number steps each render their control', async () => {
  const plan = createEmptyHouseholdPlan()
  plan.members.push({ member_id: 'm_a', display_name: 'Maya', relationship: 'self', usual_location: { kind: 'home', address: '', latitude: null, longitude: null, verification_status: 'unverified' }, is_dependant: false, mobility_support_required: false })
  plan.animals.push({ animal_id: 'a_1', category: 'pet', animal_type: 'dog', quantity: 1 })
  const find = (key) => buildSteps(plan).find((step) => step.key === key)
  const html = (key) => render('../src/components/wizard/WizardShell.vue', { step: find(key), plan, error: null, canGoBack: true })

  assert.match(await html('animals:any'), />Yes</)
  assert.match(await html('animals:any'), />No</)
  assert.match(await html('location:0:kind'), /type="radio"/)
  assert.match(await html('member:0:help'), /type="checkbox"/)
  assert.match(await html('location:0:address'), /Victorian/)
  assert.match(await html('animal:0:quantity'), /type="number"/)
})

test('a vehicle prompt with no second vehicle offers to add one', async () => {
  const plan = createEmptyHouseholdPlan()
  plan.has_private_transport = true
  plan.transports.push({ transport_id: 't_1', transport_type: 'car', display_name: '', driver_member_ids: [] })
  plan.arrangements.primary_transport_id = 't_1'
  const step = buildSteps(plan).find((s) => s.key === 'backup:none')
  const html = await render('../src/components/wizard/WizardShell.vue', { step, plan, error: null, canGoBack: true })
  assert.match(html, /Add another vehicle/)
})

test('the section recap shows its text, a Save and continue button, and any error', async () => {
  const html = await render('../src/components/wizard/SectionSummary.vue', {
    section: SECTIONS[0], text: 'Maya, Sam', needsAttention: true, saving: false, error: 'Could not save.', isEdit: false,
  })
  assert.match(html, /Your household/)
  assert.match(html, /Maya, Sam/)
  assert.match(html, /Save and continue/)
  assert.match(html, /Some answers are still missing/)
  assert.match(html, /role="alert"[^>]*>Could not save\./)
  const edit = await render('../src/components/wizard/SectionSummary.vue', {
    section: SECTIONS[0], text: 'x', needsAttention: false, saving: false, isEdit: true, error: null,
  })
  assert.match(edit, /Save and return to review/)
  assert.doesNotMatch(edit, /Some answers are still missing/)
  const busy = await render('../src/components/wizard/SectionSummary.vue', {
    section: SECTIONS[0], text: 'x', needsAttention: false, saving: true, isEdit: false, error: null,
  })
  assert.match(busy, /Saving…/)
  assert.match(busy, /disabled/)
})

test('the review screen lists all seven sections with status, summary and Edit', async () => {
  const plan = createEmptyHouseholdPlan()
  plan.members.push({ member_id: 'm_a', display_name: 'Maya', usual_location: null })
  const html = await render('../src/components/wizard/ReviewScreen.vue', {
    plan, completion: completion(2), completionLoading: false, editable: SECTIONS.map((s) => s.id), saving: false,
  })
  for (const section of SECTIONS) assert.match(html, new RegExp(section.title))
  assert.equal((html.match(/>Edit</g) ?? []).length, 7)
  assert.match(html, /Maya/)
  assert.match(html, /Save &amp; Review Plan/)
  assert.match(html, /Plan checks/)
})

test('the review screen hides Edit for a section that has no questions', async () => {
  const plan = createEmptyHouseholdPlan()
  plan.has_private_transport = false
  const editable = buildSteps(plan).filter((s) => s.kind === 'summary').map((s) => s.section)
  const html = await render('../src/components/wizard/ReviewScreen.vue', {
    plan, completion: completion(7), completionLoading: false, editable, saving: false,
  })
  assert.equal((html.match(/>Edit</g) ?? []).length, 6)
  assert.match(html, /Not needed without a vehicle/)
})

test('yes/no questions can be skipped, and a removable record offers Remove', async () => {
  const plan = createEmptyHouseholdPlan()
  plan.members.push({ member_id: 'm_a', display_name: 'Maya', relationship: 'self', usual_location: null }, { member_id: 'm_b', display_name: 'Sam', relationship: null, usual_location: null })
  const find = (key) => buildSteps(plan).find((step) => step.key === key)
  const yesno = await render('../src/components/wizard/WizardShell.vue', { step: find('animals:any'), plan, error: null, canGoBack: true })
  assert.match(yesno, />Skip for now</)
  assert.doesNotMatch(yesno, /aria-pressed="true"/)
  const second = await render('../src/components/wizard/WizardShell.vue', { step: find('member:1:name'), plan, error: null, canGoBack: true })
  assert.match(second, />Remove this person</)
  const first = await render('../src/components/wizard/WizardShell.vue', { step: find('member:0:name'), plan, error: null, canGoBack: false })
  assert.match(first, />Remove this person</)
})

test('choice and multi groups are named by the question', async () => {
  const plan = createEmptyHouseholdPlan()
  const find = (key) => buildSteps(plan).find((step) => step.key === key)
  const html = await render('../src/components/wizard/WizardShell.vue', { step: find('member:0:help'), plan, error: null, canGoBack: true })
  assert.match(html, /role="group"[^>]*aria-labelledby="wizard-prompt"/)
})

test('a failed save is shown on the review screen', async () => {
  const plan = createEmptyHouseholdPlan()
  const html = await render('../src/components/wizard/ReviewScreen.vue', {
    plan, completion: completion(7), completionLoading: false, editable: [], saving: false, error: 'Your plan could not be saved.',
  })
  assert.match(html, /role="alert"[^>]*>Your plan could not be saved\./)
})

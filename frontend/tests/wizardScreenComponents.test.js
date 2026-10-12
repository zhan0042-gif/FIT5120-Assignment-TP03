import assert from 'node:assert/strict'
import test from 'node:test'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createEmptyHouseholdPlan } from '../src/domain/householdPlan.js'
import { addAnimal, addJob, addMember, addVehicle, setAnimalType, setHasVehicle, setMemberHelp, setMemberRelationship, setVehicleType } from '../src/wizard/formActions.js'
import { importComponent } from './helpers/loadComponent.js'

const screen = async (name, plan, errors = {}) =>
  renderToString(createSSRApp(await importComponent(`../src/components/wizard/screens/${name}.vue`), { plan, errors }))

const planWith = (build) => {
  const plan = createEmptyHouseholdPlan()
  build(plan)
  return plan
}

test('household: the first card is "You" without a relationship field; later cards have one', async () => {
  const plan = planWith((p) => { addMember(p).display_name = 'Maya'; addMember(p).display_name = 'Sam' })
  const html = await screen('HouseholdScreen', plan)
  assert.match(html, /Maya/)
  assert.match(html, /Sam/)
  assert.equal((html.match(/related to you\?/g) ?? []).length, 1)
  assert.match(html, /Add another person/)
  assert.equal((html.match(/Remove this person/g) ?? []).length, 1)
})

test('household: the relationship description and support notes show only when needed', async () => {
  const plain = await screen('HouseholdScreen', planWith((p) => { addMember(p); addMember(p) }))
  assert.doesNotMatch(plain, /How would you describe/)
  assert.doesNotMatch(plain, /anything else we should know/i)

  const full = await screen('HouseholdScreen', planWith((p) => {
    addMember(p)
    const b = addMember(p)
    setMemberRelationship(b, 'other')
    setMemberHelp(b, ['mobility'])
  }))
  assert.match(full, /How would you describe/)
  assert.match(full, /anything else we should know/i)
})

test('household: animals ask yes or no, then show cards with their own conditional fields', async () => {
  const none = await screen('HouseholdScreen', planWith((p) => addMember(p)))
  assert.match(none, /Do any animals leave with you\?/)
  assert.doesNotMatch(none, /How many\?/)

  const some = await screen('HouseholdScreen', planWith((p) => {
    addMember(p)
    addAnimal(p)
    setAnimalType(p.animals[0], 'other')
  }))
  assert.match(some, /How many\?/)
  assert.match(some, /What kind of animal\?/)
  assert.match(some, /Add another animal/)
  assert.match(some, /Remove this animal/)
})

test('household: errors appear beside their fields', async () => {
  const plan = planWith((p) => { addMember(p); addAnimal(p) })
  const html = await screen('HouseholdScreen', plan, { 'animal:0:quantity': 'Enter a whole number of at least 1.' })
  assert.match(html, /id="animal:0:quantity-error"[^>]*>Enter a whole number of at least 1\./)
})

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

test('daytime: one row per person, with an address field only once a place is chosen', async () => {
  const empty = await screen('DaytimeScreen', createEmptyHouseholdPlan())
  assert.match(empty, /Add the people in your household first/)

  const plan = planWith((p) => { addMember(p).display_name = 'Maya'; addMember(p).display_name = 'Sam' })
  plan.members[0].usual_location = { kind: 'work', address: '1 Main St', latitude: null, longitude: null, verification_status: 'unverified' }
  const html = await screen('DaytimeScreen', plan)
  assert.match(html, /Where are you during the day\?/)
  assert.match(html, /Where is Sam during the day\?/)
  assert.equal((html.match(/What is the address\?/g) ?? []).length, 1)
})

test('jobs: a job shows its custom field only for "Something else"; backup excludes the main person', async () => {
  const empty = await screen('JobsScreen', createEmptyHouseholdPlan())
  assert.match(empty, /Add the people in your household first/)

  const plan = planWith((p) => {
    const a = addMember(p); a.display_name = 'Maya'
    const b = addMember(p); b.display_name = 'Sam'
    const job = addJob(p)
    job.task_name = ' '
    job.primary_member_id = a.member_id
  })
  const html = await screen('JobsScreen', plan, { 'resp:0:task_custom': 'Please describe the task.' })
  assert.match(html, /What is the job\?/)
  assert.match(html, /id="resp:0:task_custom-error"[^>]*>Please describe the task\./)
  const backup = html.slice(html.indexOf('Who covers it'))
  assert.match(backup, /Sam/)
  assert.doesNotMatch(backup, />Maya</)
  assert.match(html, /Add another job/)
  assert.match(html, /Remove this job/)

  const preset = planWith((p) => { addMember(p); addJob(p).task_name = 'Drive the household' })
  assert.doesNotMatch(await screen('JobsScreen', preset), /What is the job\?/)
})

test('vehicles: nothing but the question until the person says yes', async () => {
  const html = await screen('VehiclesScreen', createEmptyHouseholdPlan())
  assert.match(html, /Do you have a vehicle you would leave in\?/)
  assert.doesNotMatch(html, /What kind of vehicle/)
  assert.doesNotMatch(html, /Which one would you take first\?/)
})

test('vehicles: "no" hides the vehicle and backup parts', async () => {
  const html = await screen('VehiclesScreen', planWith((p) => setHasVehicle(p, false)))
  assert.doesNotMatch(html, /What kind of vehicle/)
  assert.doesNotMatch(html, /backup/i)
})

test('vehicles: cards, drivers, first choice and backup on one screen', async () => {
  const plan = planWith((p) => {
    addMember(p).display_name = 'Maya'
    setHasVehicle(p, true)
    addVehicle(p)
    setVehicleType(p.transports[1], 'other')
  })
  const html = await screen('VehiclesScreen', plan, { 'vehicle:1:type_other': 'Please describe the vehicle.' })
  assert.equal((html.match(/What kind of vehicle is it\?/g) ?? []).length, 2)
  assert.match(html, /Who can drive it\?/)
  assert.match(html, /id="vehicle:1:type_other-error"[^>]*>Please describe the vehicle\./)
  assert.match(html, /Which one would you take first\?/)
  assert.match(html, /Add another vehicle/)
  assert.match(html, /Remove this vehicle/)
  assert.match(html, /If your first vehicle cannot be used/)
})

test('vehicles: with one vehicle there is nothing to back it up, and the screen says so', async () => {
  const html = await screen('VehiclesScreen', planWith((p) => setHasVehicle(p, true)))
  assert.match(html, /Add a second vehicle to choose a backup\./)
})

test('vehicles: drivers are hidden when there is no one in the household', async () => {
  const html = await screen('VehiclesScreen', planWith((p) => setHasVehicle(p, true)))
  assert.doesNotMatch(html, /Who can drive it\?/)
})

test('places: destination, address and meeting point, then backup places', async () => {
  const plan = planWith((p) => {
    p.arrangements.primary_destination = { destination_id: 'd1', display_name: "Nan's house", address: null }
    p.arrangements.backup_arrangements = [{ transport_id: null, destination: { destination_id: 'd2', display_name: 'Hall', address: null } }]
  })
  const html = await screen('PlacesScreen', plan)
  assert.match(html, /Where would you go\?/)
  assert.match(html, /If your household is separated, where would you meet\?/)
  assert.match(html, /where would you go instead\?/i)
  assert.match(html, /Add another place/)
  assert.match(html, /Remove this place/)
})

test('places: a plan with no places still shows the destination fields and an add button', async () => {
  const html = await screen('PlacesScreen', createEmptyHouseholdPlan())
  assert.match(html, /Where would you go\?/)
  assert.match(html, /Add another place/)
})

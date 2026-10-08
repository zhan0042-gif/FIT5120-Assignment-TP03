import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'

const { SECTIONS } = await import('../src/voice/sections.js')

const backend = JSON.parse(
  await readFile(new URL('../../backend/app/content/voice_sections.json', import.meta.url), 'utf8'),
)

// Where each section's anchor must be, so a section named in the list always exists.
const ANCHOR_FILES = {
  safety_guidance: '../src/components/overview/SafetyChatPanel.vue',
  fire_danger_patterns: '../src/components/overview/FdrPredictionPanel.vue',
  current_conditions: '../src/views/MapView.vue',
  household_address: '../src/components/localContext/LocalContextCard.vue',
  fire_history: '../src/views/MapView.vue',
  rendezvous: '../src/components/scenario/RendezvousPanel.vue',
  travel_map: '../src/views/TravelReadinessView.vue',
  travel_disruptions: '../src/components/scenario/TravelDisruptionPanel.vue',
}

test('the browser knows exactly the sections the server offers, with the same routes', () => {
  assert.deepEqual(
    SECTIONS.map(({ id, route }) => ({ id, route })),
    backend.map(({ id, route }) => ({ id, route })),
  )
})

test('every section has something to say when it is reached', () => {
  assert.ok(SECTIONS.every((section) => section.spoken.trim().length > 0))
})

test('every section has an anchor on its page', async () => {
  assert.deepEqual(Object.keys(ANCHOR_FILES).sort(), SECTIONS.map((section) => section.id).sort())
  for (const section of SECTIONS) {
    const source = await readFile(new URL(ANCHOR_FILES[section.id], import.meta.url), 'utf8')
    const key = section.id.replaceAll('_', '-')

    assert.match(source, new RegExp(`data-voice-section="${key}"`), section.id)
  }
})

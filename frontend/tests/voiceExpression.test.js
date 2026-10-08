import assert from 'node:assert/strict'
import { test } from 'node:test'

const {
  EMOTIONS,
  FACES,
  conversationFace,
  isCheerfulAction,
  outcomeFor,
  reactionFace,
  resolveFace,
} = await import('../src/voice/expression.js')
const { MOUTHS, POSES, poseFor } = await import('../src/voice/koalaPose.js')

test('the faces and emotions are the closed lists from the spec', () => {
  assert.deepEqual(FACES, ['neutral', 'listening', 'thinking', 'happy', 'concerned', 'serious', 'sorry'])
  assert.deepEqual(EMOTIONS, ['calm', 'worried', 'urgent', 'frustrated', 'playful'])
})

test('the conversation state picks the resting face', () => {
  assert.equal(conversationFace('idle'), 'neutral')
  assert.equal(conversationFace('closing'), 'neutral')
  assert.equal(conversationFace('error'), 'sorry')
  assert.equal(conversationFace('connecting'), 'thinking')
  assert.equal(conversationFace('checking'), 'thinking')
  assert.equal(conversationFace('listening'), 'listening')
  assert.equal(conversationFace('something-new'), 'neutral')
})

test('only opening a page, scrolling or jumping to a part of a page is cheerful', () => {
  for (const action of ['open_overview', 'open_home', 'go_back', 'scroll_down', 'scroll_to_top', 'section_fire_history']) {
    assert.equal(isCheerfulAction(action), true, action)
  }
  for (const action of ['read_weather', 'read_fire_danger', 'show_fire_history', 'ask_safety_question', 'read_simulation', 'run_simulation', 'check_travel_disruptions', 'none']) {
    assert.equal(isCheerfulAction(action), false, action)
  }
})

test('each emotion has a reaction face, except calm', () => {
  assert.equal(reactionFace('calm', 'open_home'), null)
  assert.equal(reactionFace('worried', 'read_weather'), 'concerned')
  assert.equal(reactionFace('urgent', 'read_weather'), 'serious')
  assert.equal(reactionFace('frustrated', 'read_weather'), 'sorry')
  assert.equal(reactionFace('playful', 'open_home'), 'happy')
  assert.equal(reactionFace('furious', 'open_home'), null)
  assert.equal(reactionFace(undefined, 'open_home'), null)
})

test('playful is ignored for anything that is not a page or scroll action', () => {
  for (const action of ['read_weather', 'read_fire_danger', 'ask_safety_question', 'show_fire_history', 'read_travel_routes', 'none']) {
    assert.equal(reactionFace('playful', action), null, action)
  }
})

test('an outcome is sorry when it failed, happy only for a cheerful action, otherwise nothing', () => {
  assert.equal(outcomeFor({ action: 'open_home', failed: true }), 'sorry')
  assert.equal(outcomeFor({ action: 'read_weather', failed: true }), 'sorry')
  assert.equal(outcomeFor({ action: 'open_home', failed: false }), 'happy')
  assert.equal(outcomeFor({ action: 'scroll_down', failed: false }), 'happy')
  assert.equal(outcomeFor({ action: 'read_weather', failed: false }), null)
  assert.equal(outcomeFor({ action: 'ask_safety_question', failed: false }), null)
})

test('the emergency pin outranks everything', () => {
  assert.equal(
    resolveFace({ status: 'listening', emergencyPinned: true, outcome: 'happy', reaction: 'happy' }),
    'serious',
  )
  assert.equal(resolveFace({ status: 'idle', emergencyPinned: true, outcome: 'sorry', reaction: null }), 'serious')
})

test('a failed outcome outranks a reaction, which outranks a happy outcome', () => {
  assert.equal(resolveFace({ status: 'listening', emergencyPinned: false, outcome: 'sorry', reaction: 'happy' }), 'sorry')
  assert.equal(resolveFace({ status: 'listening', emergencyPinned: false, outcome: 'happy', reaction: 'concerned' }), 'concerned')
  assert.equal(resolveFace({ status: 'listening', emergencyPinned: false, outcome: 'happy', reaction: null }), 'happy')
})

test('with nothing else going on the conversation state decides', () => {
  assert.equal(resolveFace({ status: 'listening', emergencyPinned: false, outcome: null, reaction: null }), 'listening')
  assert.equal(resolveFace({ status: 'checking', emergencyPinned: false, outcome: null, reaction: null }), 'thinking')
  assert.equal(resolveFace({ status: 'idle', emergencyPinned: false, outcome: null, reaction: null }), 'neutral')
})

test('every face has a pose, and every pose names a mouth that exists', () => {
  for (const face of FACES) {
    const pose = POSES[face]
    assert.ok(pose, face)
    assert.ok(MOUTHS[pose.mouth], `${face} mouth ${pose.mouth}`)
    for (const key of ['eyeShape', 'eyeOpen', 'pupil', 'browLeft', 'browRight', 'mouth']) {
      assert.ok(key in pose, `${face} ${key}`)
    }
  }
})

test('the faces differ in eyes, eyebrows and mouth, as the spec requires', () => {
  const signature = (face) => JSON.stringify([POSES[face].eyeShape, POSES[face].eyeOpen, POSES[face].pupil, POSES[face].browLeft, POSES[face].browRight, POSES[face].mouth])
  const seen = new Set(FACES.map(signature))

  assert.equal(seen.size, FACES.length)
  assert.notEqual(POSES.serious.mouth, POSES.happy.mouth)
  assert.notEqual(POSES.concerned.browLeft.rot, POSES.neutral.browLeft.rot)
})

test('an unknown face falls back to neutral', () => {
  assert.equal(poseFor('nonsense'), POSES.neutral)
  assert.equal(poseFor(undefined), POSES.neutral)
})

test('a failed start is sorry, never the resting smile', () => {
  assert.equal(resolveFace({ status: 'error', emergencyPinned: false, outcome: null, reaction: null }), 'sorry')
})

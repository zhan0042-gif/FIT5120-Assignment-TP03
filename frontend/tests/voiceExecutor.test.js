import assert from 'node:assert/strict'
import { test } from 'node:test'

const { describeAction, executeAction } = await import('../src/voice/executor.js')
const {
  VoiceActionError,
  addressTarget,
  buttonTarget,
  checkboxTarget,
  commandTarget,
  pageTarget,
  selectTarget,
  textTarget,
} = await import('../src/voice/targets.js')

const noop = () => {}
const transport = (set = noop) => selectTarget({
  id: 'primary-transport',
  label: 'Primary transport',
  choices: [{ label: 'Not set', value: null }, { label: 'Van', value: 't_1' }],
  current: null,
  set,
})

test('the live target runs with the chosen value', async () => {
  let stored
  const target = transport((value) => { stored = value })
  const result = await executeAction({ kind: 'select', target, value: 'Van' }, [target])
  assert.deepEqual(result, { ok: true, message: '✓ Set Primary transport to Van' })
  assert.equal(stored, 't_1')
})

test('a row renamed since it was heard is still acted on through its id', async () => {
  const heard = textTarget({ id: 'm2-name', label: 'Name (member 2)', current: '', set: noop })
  let written
  const live = textTarget({ id: 'm2-name', label: 'Name (Lan)', current: 'Lan', set: (value) => { written = value } })
  const result = await executeAction({ kind: 'text', target: heard, value: 'Lan Nguyen' }, [live])
  assert.equal(written, 'Lan Nguyen')
  assert.equal(result.message, '✓ Fill in Name (Lan) with “Lan Nguyen”')
})

test('a target no longer on the page is refused', async () => {
  const target = transport()
  const result = await executeAction({ kind: 'select', target, value: 'Van' }, [])
  assert.deepEqual(result, { ok: false, message: 'That’s no longer on this page.' })
})

test('a disabled button is refused without being pressed', async () => {
  let pressed = 0
  const target = buttonTarget({ id: 'save', label: 'Save plan', disabled: true, press: () => { pressed += 1 } })
  const result = await executeAction({ kind: 'button', target, value: null }, [target])
  assert.deepEqual(result, { ok: false, message: 'That isn’t available right now.' })
  assert.equal(pressed, 0)
})

test('an option the select does not offer is refused', async () => {
  let stored = 'untouched'
  const target = transport((value) => { stored = value })
  const result = await executeAction({ kind: 'select', target, value: 'Truck' }, [target])
  assert.deepEqual(result, { ok: false, message: 'That option isn’t available.' })
  assert.equal(stored, 'untouched')
})

test('a VoiceActionError reaches the user; any other error does not', async () => {
  const fixable = textTarget({ id: 'q', label: 'Quantity (Coco)', current: '', set: () => {
    throw new VoiceActionError('Say the quantity as a whole number, such as 2.')
  } })
  assert.deepEqual(
    await executeAction({ kind: 'text', target: fixable, value: 'lots' }, [fixable]),
    { ok: false, message: 'Say the quantity as a whole number, such as 2.' },
  )
  const broken = buttonTarget({ id: 'b', label: 'Retry', press: () => { throw new Error('TypeError at line 4') } })
  assert.deepEqual(
    await executeAction({ kind: 'button', target: broken, value: null }, [broken]),
    { ok: false, message: 'That could not be done.' },
  )
})

test('an asynchronous run is finished before success is reported', async () => {
  let arrived = false
  const target = pageTarget({ id: 'page-map', label: 'Fire Map', go: async () => {
    await new Promise((resolve) => setTimeout(resolve, 5))
    arrived = true
  } })
  const result = await executeAction({ kind: 'page', target, value: null }, [target])
  assert.equal(arrived, true)
  assert.equal(result.ok, true)
})

test('every kind of action is described in plain words', () => {
  const box = checkboxTarget({ id: 'x', label: 'Has limited mobility (Minh)', current: false, set: noop })
  const address = addressTarget({ id: 'a', label: 'Primary destination address', current: '', setText: noop, suggestions: () => [], choose: noop })
  assert.equal(describeAction({ kind: 'checkbox', target: box, value: true }), 'Tick Has limited mobility (Minh)')
  assert.equal(describeAction({ kind: 'checkbox', target: box, value: false }), 'Untick Has limited mobility (Minh)')
  assert.equal(
    describeAction({ kind: 'button', target: buttonTarget({ id: 'b', label: 'Remove member Minh', press: noop }), value: null }),
    'Press Remove member Minh',
  )
  assert.equal(describeAction({ kind: 'page', target: pageTarget({ id: 'p', label: 'Overview', go: noop }), value: null }), 'Go to Overview')
  assert.equal(describeAction({ kind: 'command', target: commandTarget({ id: 'c', label: 'scroll down', run: noop }), value: null }), 'Scroll down')
  assert.equal(describeAction({ kind: 'address', target: address, value: '12 Smith St' }), 'Enter “12 Smith St” for Primary destination address')
})

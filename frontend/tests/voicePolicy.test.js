import assert from 'node:assert/strict'
import { test } from 'node:test'

const { ACT_AT, ASK_AT, decideCommand, decideConfirmation, decideSuggestion } =
  await import('../src/voice/policy.js')
const { NONE_OF_THESE, NO_SPAN, NO_SUGGESTION, buildCatalogue } = await import('../src/voice/questions.js')
const { addressTarget, buttonTarget, checkboxTarget, pageTarget, selectTarget, textTarget } =
  await import('../src/voice/targets.js')

const noop = () => {}
const catalogue = buildCatalogue([
  pageTarget({ id: 'page-map', label: 'Fire Map', go: noop }),
  selectTarget({
    id: 'primary-transport',
    label: 'Primary transport',
    choices: [{ label: 'Not set', value: null }, { label: 'Van', value: 't_1' }],
    current: null,
    set: noop,
  }),
  textTarget({ id: 'm2-name', label: 'Name (member 2)', current: '', set: noop }),
  textTarget({ id: 'm1-name', label: 'Name (Minh)', current: 'Minh', set: noop }),
  checkboxTarget({ id: 'm1-mobility', label: 'Has limited mobility (Minh)', current: false, set: noop }),
  addressTarget({
    id: 'address-1', label: 'Primary destination address', current: '',
    setText: noop, suggestions: () => [], choose: noop,
  }),
  buttonTarget({ id: 'm1-remove', label: 'Remove member Minh', confirm: true, press: noop }),
])

const a = (id, answer, probability) => ({ id, answer, probability })
const NO_STOP = a('stop', 'no', 0.95)
const decide = (...answers) => decideCommand([...answers, NO_STOP], catalogue)

test('the thresholds are exactly 0.85 to act and 0.5 to ask', () => {
  assert.equal(ACT_AT, 0.85)
  assert.equal(ASK_AT, 0.5)
})

test('a command at exactly 0.85 is carried out', () => {
  const decision = decide(a('command', 'go to Fire Map', 0.85))
  assert.equal(decision.type, 'execute')
  assert.equal(decision.action.kind, 'page')
  assert.equal(decision.action.target.id, 'page-map')
})

test('just under 0.85 asks first, and exactly 0.5 still asks', () => {
  assert.equal(decide(a('command', 'go to Fire Map', 0.84)).type, 'confirm')
  assert.equal(decide(a('command', 'go to Fire Map', 0.5)).type, 'confirm')
})

test('below 0.5 nothing happens', () => {
  assert.equal(decide(a('command', 'go to Fire Map', 0.49)).type, 'reject')
})

test('confidence is the lowest answer the decision uses', () => {
  const decision = decide(
    a('command', 'set Primary transport', 0.95),
    a('option:primary-transport', 'Van', 0.6),
  )
  assert.equal(decision.type, 'confirm')
  assert.deepEqual(
    [decision.action.kind, decision.action.target.id, decision.action.value],
    ['select', 'primary-transport', 'Van'],
  )
})

test('a confident select is carried out with the chosen option', () => {
  const decision = decide(
    a('command', 'set Primary transport', 0.95),
    a('option:primary-transport', 'Van', 0.97),
  )
  assert.equal(decision.type, 'execute')
  assert.equal(decision.action.value, 'Van')
})

test('a target marked confirm asks even at 0.99', () => {
  const decision = decide(a('command', 'press Remove member Minh', 0.99))
  assert.equal(decision.type, 'confirm')
  assert.equal(decision.action.target.id, 'm1-remove')
})

test('a confident span fills an empty text field', () => {
  const decision = decide(a('command', 'fill in Name (member 2)', 0.95), a('span', 'Lan', 0.9))
  assert.equal(decision.type, 'execute')
  assert.deepEqual([decision.action.kind, decision.action.value], ['text', 'Lan'])
})

test('an unsure or missing value turns into dictation', () => {
  const unsure = decide(a('command', 'fill in Name (member 2)', 0.95), a('span', 'Lan', 0.7))
  assert.deepEqual([unsure.type, unsure.target.id], ['dictate', 'm2-name'])
  const missing = decide(a('command', 'fill in Name (member 2)', 0.95), a('span', NO_SPAN, 0.95))
  assert.equal(missing.type, 'dictate')
})

test('replacing something already typed always asks first', () => {
  const decision = decide(a('command', 'fill in Name (Minh)', 0.95), a('span', 'Lan', 0.95))
  assert.equal(decision.type, 'confirm')
  assert.equal(decision.action.value, 'Lan')
})

test('saying the value that is already there is not an overwrite', () => {
  const decision = decide(a('command', 'fill in Name (Minh)', 0.95), a('span', 'Minh', 0.95))
  assert.equal(decision.type, 'execute')
})

test('an address is always dictated, never taken from the sentence', () => {
  const decision = decide(
    a('command', 'enter the address for Primary destination address', 0.99),
    a('span', '12 Smith Street', 0.99),
  )
  assert.deepEqual([decision.type, decision.target.id], ['dictate', 'address-1'])
})

test('a checkbox is set from the checked answer', () => {
  const decision = decide(
    a('command', 'tick or untick Has limited mobility (Minh)', 0.95),
    a('checked', 'no', 0.9),
  )
  assert.equal(decision.type, 'execute')
  assert.equal(decision.action.value, false)
})

test('none of these, a missing command, an unknown phrase or a missing value is rejected', () => {
  assert.equal(decide(a('command', NONE_OF_THESE, 0.99)).type, 'reject')
  assert.equal(decideCommand([NO_STOP], catalogue).type, 'reject')
  assert.equal(decide(a('command', 'press Launch', 0.99)).type, 'reject')
  assert.equal(decide(a('command', 'set Primary transport', 0.99)).type, 'reject')
})

test('stop wins over a confident command, but only at 0.5 or more', () => {
  const confident = a('command', 'go to Fire Map', 0.99)
  assert.equal(decideCommand([confident, a('stop', 'yes', 0.9)], catalogue).type, 'stop')
  assert.equal(decideCommand([confident, a('stop', 'yes', 0.4)], catalogue).type, 'execute')
})

test('a confirmation needs a confident yes; a no only needs to be likely', () => {
  assert.equal(decideConfirmation([a('confirm', 'yes', 0.9), NO_STOP]).type, 'execute')
  assert.equal(decideConfirmation([a('confirm', 'yes', 0.8), NO_STOP]).type, 'unclear')
  assert.equal(decideConfirmation([a('confirm', 'no', 0.6), NO_STOP]).type, 'cancel')
  assert.equal(decideConfirmation([a('confirm', 'no', 0.4), NO_STOP]).type, 'unclear')
  assert.equal(decideConfirmation([a('confirm', 'yes', 0.9), a('stop', 'yes', 0.9)]).type, 'stop')
})

test('a suggestion is chosen by its number only when confident', () => {
  assert.deepEqual(
    decideSuggestion([a('suggestion', '2 second: 12 Smith Rd, Sale VIC 3850', 0.9), NO_STOP]),
    { type: 'choose', index: 1 },
  )
  assert.equal(decideSuggestion([a('suggestion', NO_SUGGESTION, 0.9), NO_STOP]).type, 'keep')
  assert.equal(decideSuggestion([a('suggestion', '1 first: x', 0.7), NO_STOP]).type, 'unclear')
  assert.equal(decideSuggestion([a('suggestion', '1 first: x', 0.9), a('stop', 'yes', 0.9)]).type, 'stop')
})

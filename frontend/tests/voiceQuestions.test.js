import assert from 'node:assert/strict'
import { test } from 'node:test'

const {
  MAX_COMMANDS,
  NONE_OF_THESE,
  NO_SPAN,
  NO_SUGGESTION,
  buildBatch,
  buildCatalogue,
  commandPhrase,
  spanCandidates,
  suggestionOptions,
} = await import('../src/voice/questions.js')
const {
  addressTarget,
  buttonTarget,
  checkboxTarget,
  commandTarget,
  pageTarget,
  selectTarget,
  textTarget,
} = await import('../src/voice/targets.js')

const noop = () => {}
const transportSelect = (id, label) => selectTarget({
  id,
  label,
  choices: [{ label: 'Not set', value: null }, { label: 'Van', value: 't_1' }],
  current: null,
  set: noop,
})

test('each kind of target reads as a command phrase', () => {
  assert.equal(commandPhrase(pageTarget({ id: 'p', label: 'Fire Map', go: noop })), 'go to Fire Map')
  assert.equal(commandPhrase(commandTarget({ id: 'c', label: 'scroll down', run: noop })), 'scroll down')
  assert.equal(
    commandPhrase(buttonTarget({ id: 'b', label: 'Continue', aliases: ['next step'], press: noop })),
    'press Continue, or say next step',
  )
  assert.equal(commandPhrase(buttonTarget({ id: 'b', label: 'Save plan', press: noop })), 'press Save plan')
  assert.equal(commandPhrase(transportSelect('s', 'Primary transport')), 'set Primary transport')
  assert.equal(
    commandPhrase(textTarget({ id: 't', label: 'Name (member 2)', current: '', set: noop })),
    'fill in Name (member 2)',
  )
  assert.equal(
    commandPhrase(checkboxTarget({ id: 'x', label: 'Has limited mobility (Minh)', current: false, set: noop })),
    'tick or untick Has limited mobility (Minh)',
  )
  assert.equal(
    commandPhrase(addressTarget({ id: 'a', label: 'Primary destination address', current: '', setText: noop, suggestions: () => [], choose: noop })),
    'enter the address for Primary destination address',
  )
})

test('two targets with the same phrase get distinct phrases', () => {
  const catalogue = buildCatalogue([
    buttonTarget({ id: 'r1', label: 'Retry', press: noop }),
    buttonTarget({ id: 'r2', label: 'Retry', press: noop }),
  ])
  assert.deepEqual(catalogue.map((entry) => entry.phrase), ['press Retry', 'press Retry (2)'])
  assert.deepEqual(catalogue.map((entry) => entry.target.id), ['r1', 'r2'])
})

test('a page offering more than the judge accepts keeps the earliest targets', () => {
  const targets = Array.from({ length: 150 }, (_, index) =>
    buttonTarget({ id: `b${index}`, label: `Button ${index}`, press: noop }))
  const catalogue = buildCatalogue(targets)
  assert.equal(MAX_COMMANDS, 99)
  assert.equal(catalogue.length, 99)
  assert.equal(catalogue[0].target.id, 'b0')

  const { questions, state } = buildBatch({ transcript: 'hello', targets, context: { page: 'plan-builder' } })
  assert.equal(questions[0].options.length, 100)
  assert.equal(state.targets.length, 99)
})

test('a normal batch asks for the command, every select, a span, checked and stop', () => {
  const targets = [
    pageTarget({ id: 'page-overview', label: 'Overview', go: noop }),
    transportSelect('primary-transport', 'Primary transport'),
    transportSelect('backup-0-transport', 'Backup transport (backup 1)'),
    textTarget({ id: 'meeting-point', label: 'Meeting point', current: '', set: noop }),
  ]
  const { state, questions, catalogue } = buildBatch({
    transcript: 'primary transport is a van',
    targets,
    context: { page: 'plan-builder', step: 'destinations' },
  })

  assert.deepEqual(questions.map((question) => question.id), [
    'command', 'option:primary-transport', 'option:backup-0-transport', 'span', 'checked', 'stop',
  ])
  assert.equal(questions[0].type, 'pick_one')
  assert.equal(questions[0].options.at(-1), NONE_OF_THESE)
  assert.deepEqual(questions[1].options, ['Not set', 'Van'])
  assert.deepEqual(questions[4], { id: 'checked', type: 'yes_no', options: [] })
  assert.equal(catalogue.length, 4)
  assert.deepEqual(
    [state.page, state.step, state.mode, state.transcript],
    ['plan-builder', 'destinations', 'normal', 'primary transport is a van'],
  )
})

test('state describes targets as plain data, without their handlers', () => {
  const { state } = buildBatch({
    transcript: 'hello',
    targets: [
      checkboxTarget({ id: 'x', label: 'Has limited mobility (Minh)', current: true, set: noop }),
      textTarget({ id: 't', label: 'Name (member 2)', current: '', set: noop }),
    ],
    context: { page: 'plan-builder', step: 'people' },
  })
  assert.deepEqual(state.targets, [
    { id: 'x', kind: 'checkbox', label: 'Has limited mobility (Minh)', current: 'true' },
    { id: 't', kind: 'text', label: 'Name (member 2)' },
  ])
})

test('spans cover runs of up to eight words, cleaned of punctuation, ending in (none)', () => {
  const spans = spanCandidates('Name is Minh.')
  assert.ok(spans.includes('Minh'))
  assert.ok(spans.includes('Name is Minh'))
  assert.ok(!spans.some((span) => span.endsWith('.')))
  assert.equal(spans.at(-1), NO_SPAN)
  assert.equal(new Set(spans).size, spans.length)
})

test('long transcripts keep the spans nearest the end, where values usually are', () => {
  // Seventeen different words give 108 distinct spans, more than fit.
  const spans = spanCandidates(
    'please could you now set the name for my second household member over here to Lan Nguyen',
  )
  assert.equal(spans.length, 100)
  assert.ok(spans.includes('Lan Nguyen'))
})

test('a confirming batch asks only yes/no questions', () => {
  const { questions, catalogue } = buildBatch({
    transcript: 'yes', targets: [], context: {}, mode: 'confirming',
  })
  assert.deepEqual(questions, [
    { id: 'confirm', type: 'yes_no', options: [] },
    { id: 'stop', type: 'yes_no', options: [] },
  ])
  assert.deepEqual(catalogue, [])
})

test('a choosing batch numbers the suggestions and offers none', () => {
  const { questions } = buildBatch({
    transcript: 'the first one',
    targets: [],
    context: {},
    mode: 'choosing',
    choosing: ['12 Smith St, Ballarat VIC 3350', '12 Smith Rd, Sale VIC 3850'],
  })
  assert.deepEqual(questions[0], {
    id: 'suggestion',
    type: 'pick_one',
    options: ['1 first: 12 Smith St, Ballarat VIC 3350', '2 second: 12 Smith Rd, Sale VIC 3850', NO_SUGGESTION],
  })
  assert.equal(questions[1].id, 'stop')
})

test('at most nine suggestions are offered', () => {
  const options = suggestionOptions(Array.from({ length: 12 }, (_, index) => `Address ${index}`))
  assert.equal(options.length, 10)
  assert.equal(options[8], '9 ninth: Address 8')
  assert.equal(options[9], NO_SUGGESTION)
})

test('a page is always named, even before the layout registers', () => {
  const { state } = buildBatch({ transcript: 'hello', targets: [], context: { page: null, step: null } })
  assert.equal(state.page, 'unknown')
  assert.equal(state.step, null)
})

test('current values are cut to what the backend accepts', () => {
  const { state } = buildBatch({
    transcript: 'hello',
    targets: [textTarget({ id: 't', label: 'Notes', current: 'x'.repeat(600), set: noop })],
    context: {},
  })
  assert.equal(state.targets[0].current.length, 500)
})

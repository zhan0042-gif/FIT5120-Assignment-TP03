import assert from 'node:assert/strict'
import { test } from 'node:test'

const {
  VoiceActionError,
  addressTarget,
  buttonTarget,
  checkboxTarget,
  rowName,
  selectTarget,
  spokenWholeNumber,
  textTarget,
  uniqueLabels,
} = await import('../src/voice/targets.js')

test('a select offers labels and stores the value behind the chosen one', () => {
  let stored = 'unset'
  const target = selectTarget({
    id: 'rel',
    label: 'Relationship to household (Minh)',
    choices: [{ label: 'Prefer not to specify', value: null }, { label: 'Parent', value: 'parent' }],
    current: 'parent',
    set: (value) => { stored = value },
  })
  assert.equal(target.kind, 'select')
  assert.deepEqual(target.options, ['Prefer not to specify', 'Parent'])
  assert.equal(target.current, 'Parent')
  target.run('Prefer not to specify')
  assert.equal(stored, null)
})

test('repeated option labels are numbered and still map to their own values', () => {
  let stored
  const target = selectTarget({
    id: 'who',
    label: 'Primary person',
    choices: [{ label: 'Unnamed member', value: 'm_1' }, { label: 'Unnamed member', value: 'm_2' }],
    current: null,
    set: (value) => { stored = value },
  })
  assert.deepEqual(target.options, ['Unnamed member', 'Unnamed member (2)'])
  assert.equal(target.current, null)
  target.run('Unnamed member (2)')
  assert.equal(stored, 'm_2')
})

test('uniqueLabels never produces a duplicate, even against a numbered label', () => {
  assert.deepEqual(uniqueLabels(['A', 'A (2)', 'A']), ['A', 'A (2)', 'A (3)'])
})

test('text, checkbox and button targets carry their kind and defaults', () => {
  const text = textTarget({ id: 't', label: 'Name (member 2)', current: null, set: () => {} })
  assert.equal(text.kind, 'text')
  assert.equal(text.current, '')
  const box = checkboxTarget({ id: 'c', label: 'Has limited mobility (Minh)', current: undefined, set: () => {} })
  assert.equal(box.kind, 'checkbox')
  assert.equal(box.current, false)
  const button = buttonTarget({ id: 'b', label: 'Save plan', press: () => {} })
  assert.deepEqual(
    [button.kind, button.aliases, button.confirm, button.disabled],
    ['button', [], false, false],
  )
})

test('an address target exposes its text, suggestions and chooser', () => {
  const chosen = []
  const target = addressTarget({
    id: 'address-1',
    label: 'Primary destination address',
    current: '12 Smith St',
    setText: () => {},
    suggestions: () => ['12 Smith St, Ballarat VIC 3350'],
    choose: (index) => chosen.push(index),
  })
  assert.equal(target.kind, 'address')
  assert.deepEqual(target.suggestions(), ['12 Smith St, Ballarat VIC 3350'])
  target.choose(0)
  assert.deepEqual(chosen, [0])
})

test('rows are named by the person, or by position until they have a name', () => {
  assert.equal(rowName('Minh', 'member', 0), 'Minh')
  assert.equal(rowName('  ', 'member', 1), 'member 2')
  assert.equal(rowName(null, 'transport', 0), 'transport 1')
})

test('whole numbers can be said as words or digits', () => {
  assert.equal(spokenWholeNumber('two'), 2)
  assert.equal(spokenWholeNumber(' 3 '), 3)
  assert.equal(spokenWholeNumber('Twelve'), 12)
})

test('anything that is not a whole number of at least one is refused with a message', () => {
  for (const heard of ['a lot', '0', '2.5', '']) {
    assert.throws(() => spokenWholeNumber(heard), (error) =>
      error instanceof VoiceActionError && /whole number/.test(error.message))
  }
})

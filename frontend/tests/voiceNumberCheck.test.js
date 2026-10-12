import assert from 'node:assert/strict'
import { test } from 'node:test'

const { numbersIn, unexpectedNumbers } = await import('../src/voice/numberCheck.js')

test('numbersIn finds integers and decimals', () => {
  assert.deepEqual([...numbersIn('It is 21.5 degrees, humidity 40 and wind 18.')].sort(), ['18', '21.5', '40'])
})

test('numbers are compared by value, not by spelling', () => {
  assert.deepEqual([...numbersIn('21.50 and 1,000 and 007')].sort(), ['1000', '21.5', '7'])
})

test('numbersIn is safe on empty and missing text', () => {
  assert.equal(numbersIn('').size, 0)
  assert.equal(numbersIn(null).size, 0)
  assert.equal(numbersIn(undefined).size, 0)
})

test('speech that repeats only the sent numbers has nothing unexpected', () => {
  const sent = ['The temperature is 21.5 degrees Celsius, humidity is 40 percent.']

  assert.deepEqual(unexpectedNumbers(sent, 'It is 21.5 degrees and 40 percent humidity.'), [])
})

test('a changed number is reported', () => {
  const sent = ['The temperature is 21.5 degrees Celsius.']

  assert.deepEqual(unexpectedNumbers(sent, 'It is 25 degrees.'), ['25'])
})

test('a number that was never sent is reported even when nothing was sent', () => {
  assert.deepEqual(unexpectedNumbers([], 'About 30 fires nearby.'), ['30'])
})

test('numbers from any earlier sent text are allowed', () => {
  const sent = ['There are 12 recorded fires.', 'The nearest was 3.4 kilometres away.']

  assert.deepEqual(unexpectedNumbers(sent, 'Twelve is not a digit, but 12 and 3.4 are.'), [])
})

test('the emergency number is allowed when it was in the sent text', () => {
  const sent = ['If you are in danger, call 000 now.']

  assert.deepEqual(unexpectedNumbers(sent, 'Please call 000 now.'), [])
})

test('speech with no digits has nothing to report', () => {
  assert.deepEqual(unexpectedNumbers(['There are 12 fires.'], 'Let me check that.'), [])
})

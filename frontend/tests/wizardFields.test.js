import assert from 'node:assert/strict'
import test from 'node:test'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { importComponent } from './helpers/loadComponent.js'

const render = async (name, props) =>
  renderToString(createSSRApp(await importComponent(`../src/components/wizard/fields/${name}.vue`), props))

test('a text field has a visible label tied to its input and no error by default', async () => {
  const html = await render('TextField', { id: 'f1', label: 'Name', modelValue: 'Maya' })
  assert.match(html, /<label[^>]*for="f1"[^>]*>Name<\/label>/)
  assert.match(html, /<input[^>]*id="f1"/)
  assert.match(html, /value="Maya"/)
  assert.doesNotMatch(html, /aria-invalid/)
})

test('an error is linked to the control and shown beside it', async () => {
  const html = await render('TextField', { id: 'f1', label: 'Name', modelValue: '', error: 'Please describe it.' })
  assert.match(html, /aria-invalid="true"/)
  assert.match(html, /aria-describedby="f1-error"/)
  assert.match(html, /id="f1-error"[^>]*>Please describe it\./)
})

test('a number field keeps its minimum', async () => {
  const html = await render('NumberField', { id: 'n1', label: 'How many?', modelValue: 2, min: 1 })
  assert.match(html, /type="number"/)
  assert.match(html, /min="1"/)
})

test('a select lists its options and marks the chosen one', async () => {
  const html = await render('SelectField', { id: 's1', label: 'Kind', modelValue: 'ute', options: [['car', 'Car'], ['ute', 'Ute']] })
  assert.match(html, /<option value="car">Car<\/option>/)
  assert.match(html, /<option value="ute" selected[^>]*>Ute<\/option>/)
})

test('a check group is a fieldset with a legend and checked boxes', async () => {
  const html = await render('CheckField', { id: 'c1', label: 'Who can drive it?', modelValue: ['a'], options: [['a', 'Maya'], ['b', 'Sam']] })
  assert.match(html, /<fieldset[^>]*id="c1"/)
  assert.match(html, /<legend[^>]*>Who can drive it\?<\/legend>/)
  assert.match(html, /value="a"[^>]*checked/)
  assert.doesNotMatch(html, /value="b"[^>]*checked/)
})

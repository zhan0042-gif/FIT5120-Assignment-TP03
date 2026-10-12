import assert from 'node:assert/strict'
import test from 'node:test'
import { createSSRApp, h } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { SCREENS } from '../src/wizard/screens.js'
import { importComponent } from './helpers/loadComponent.js'

const render = async (props) => {
  const Shell = await importComponent('../src/components/wizard/ScreenShell.vue')
  return renderToString(createSSRApp({
    render: () => h(Shell, {
      screen: SCREENS[2], position: 3, total: 5, errors: [], saveError: null, saving: false, isEdit: false, canGoBack: true, ...props,
    }, { default: () => h('p', 'FORM') }),
  }))
}

test('the shell shows the part, the title and the form', async () => {
  const html = await render()
  assert.match(html, /Part 3 of 5/)
  assert.match(html, /<h2[^>]*id="wizard-prompt"[^>]*>How you would leave<\/h2>/)
  assert.match(html, /FORM/)
  assert.match(html, /Save and continue/)
  assert.match(html, /Skip for now/)
  assert.match(html, />Back</)
})

test('editing from review changes the save label; saving disables it', async () => {
  assert.match(await render({ isEdit: true }), /Save and return to review/)
  const saving = await render({ saving: true })
  assert.match(saving, /Saving…/)
  assert.match(saving, /disabled/)
})

test('the first screen has no Back button', async () => {
  assert.doesNotMatch(await render({ canGoBack: false }), />Back</)
})

test('validation errors are summarised as an alert with links to their fields', async () => {
  const html = await render({ errors: [{ field: 'vehicle:1:type_other', message: 'Please describe the vehicle.' }] })
  assert.match(html, /role="alert"/)
  assert.match(html, /href="#vehicle:1:type_other"[^>]*>Please describe the vehicle\./)
})

test('a failed save is shown as an alert', async () => {
  assert.match(await render({ saveError: 'Your plan could not be saved.' }), /role="alert"[^>]*>Your plan could not be saved\./)
})

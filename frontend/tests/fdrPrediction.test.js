import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import { parse, compileScript } from '@vue/compiler-sfc'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createPinia, setActivePinia } from 'pinia'

import { api } from '../src/api/client.js'
import { useFdrPredictionStore } from '../src/stores/fdrPrediction.js'


async function loadComponent(path) {
  const url = new URL(path, import.meta.url)
  const { descriptor } = parse(await readFile(url, 'utf8'))
  let code = compileScript(descriptor, { id: path, inlineTemplate: true }).content

  for (const match of [...code.matchAll(/from ['"]([^'"]+)['"]/g)]) {
    const name = match[1]
    const resolved = name.startsWith('.')
      ? new URL(name.endsWith('.js') ? name : `${name}.js`, url).href
      : import.meta.resolve(name)
    code = code.replace(match[0], `from '${resolved}'`)
  }

  return `data:text/javascript;base64,${Buffer.from(code).toString('base64')}`
}


async function renderPanel(arrange) {
  const pinia = createPinia()
  arrange(useFdrPredictionStore(pinia))
  const { default: Panel } = await import(
    await loadComponent('../src/components/overview/FdrPredictionPanel.vue')
  )
  return renderToString(createSSRApp(Panel).use(pinia))
}


test('FDR API success is stored and displayed with conservative wording', async (context) => {
  setActivePinia(createPinia())
  const original = api.getFdrPrediction
  context.after(() => { api.getFdrPrediction = original })
  api.getFdrPrediction = async (district, date) => ({
    district,
    date,
    prediction_class: 1,
    prediction_label: 'Elevated',
    elevated_probability: 0.8,
    model_name: 'Decision Tree',
    disclaimer: 'Not an official forecast.',
  })

  const store = useFdrPredictionStore()
  await store.predict('Central', '2026-01-15')

  assert.equal(store.status, 'success')
  assert.equal(store.result.prediction_label, 'Elevated')

  const html = await renderPanel((panelStore) => {
    panelStore.status = 'success'
    panelStore.result = store.result
  })
  assert.match(html, /Estimated pattern:[\s\S]*Elevated/)
  assert.match(html, /Estimated elevated historical pattern/)
  assert.match(html, /80\.0%/)
  assert.match(html, /not an official Fire Danger Rating forecast/)
})


test('FDR API failure is shown only inside the FDR panel', async () => {
  const html = await renderPanel((store) => {
    store.status = 'error'
    store.error = 'The fire danger pattern estimate is temporarily unavailable.'
  })

  assert.match(html, /role="alert"/)
  assert.match(html, /temporarily unavailable/)
  assert.match(html, /Fire Danger Pattern Estimate/)
})


test('FDR coexists with Safety Guidance and does not gate current Overview content', async () => {
  const overview = await readFile(
    new URL('../src/views/OverviewView.vue', import.meta.url),
    'utf8',
  )
  const template = overview.slice(
    overview.indexOf('<template>'),
    overview.lastIndexOf('</template>'),
  )

  assert.match(overview, /import SafetyChatPanel/)
  assert.match(overview, /import FdrPredictionPanel/)
  assert.ok(template.indexOf('<SafetyChatPanel />') < template.indexOf('<FdrPredictionPanel />'))
  assert.ok(template.indexOf('<FdrPredictionPanel />') < template.indexOf('Household Plan Summary'))
  assert.doesNotMatch(template, /fdrStore/)
  assert.match(template, /Export preparedness plan/)
})


test('FDR panel uses current theme tokens and keeps its mobile layout', async () => {
  const panel = await readFile(
    new URL('../src/components/overview/FdrPredictionPanel.vue', import.meta.url),
    'utf8',
  )

  assert.doesNotMatch(panel, /#222/i)
  assert.match(panel, /var\(--color-bg-card\)/)
  assert.match(panel, /var\(--color-border-strong\)/)
  assert.match(panel, /@media \(max-width: 700px\)/)
  assert.match(panel, /\.form-grid \{[\s\S]*?grid-template-columns: 1fr/)
})

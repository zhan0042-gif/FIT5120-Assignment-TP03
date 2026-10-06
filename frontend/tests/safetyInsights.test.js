import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import { compileScript, parse } from '@vue/compiler-sfc'
import { createPinia } from 'pinia'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'

import { useFdrPredictionStore } from '../src/stores/fdrPrediction.js'
import { useSafetyGuidanceStore } from '../src/stores/safetyGuidance.js'


const source = async (path) => readFile(new URL(path, import.meta.url), 'utf8')

globalThis.localStorage = {
  getItem: () => null,
  setItem: () => {},
  removeItem: () => {},
}

async function loadComponent(path) {
  const url = new URL(path, import.meta.url)
  const { descriptor } = parse(await readFile(url, 'utf8'))
  let code = compileScript(descriptor, { id: path, inlineTemplate: true }).content
  code = code.replace(/^import ['"][^'"]+['"]\s*$/gm, '')

  for (const match of [...code.matchAll(/from ['"]([^'"]+)['"]/g)]) {
    const name = match[1]
    let resolved

    if (name.endsWith('.vue')) {
      resolved = await loadComponent(new URL(name, url).href)
    } else {
      resolved = name.startsWith('.')
        ? new URL(name.endsWith('.js') ? name : `${name}.js`, url).href
        : import.meta.resolve(name)
    }

    code = code.replace(match[0], `from '${resolved}'`)
  }

  return `data:text/javascript;base64,${Buffer.from(code).toString('base64')}`
}

async function renderInsights(arrange) {
  const pinia = createPinia()
  arrange({
    fdr: useFdrPredictionStore(pinia),
    safety: useSafetyGuidanceStore(pinia),
  })
  const { default: View } = await import(
    await loadComponent('../src/views/SafetyInsightsView.vue')
  )
  return renderToString(createSSRApp(View).use(pinia))
}

const guidanceEntry = {
  id: 'reviewed-entry',
  question: 'What should I prepare?',
  answer: 'Prepare early and follow official warnings.',
  source_name: 'CFA',
  source_url: 'https://www.cfa.vic.gov.au/example',
  retrieved_on: '2026-10-07',
}

test('Safety Insights route and navigation use the requested placement', async () => {
  const router = await source('../src/router/index.js')
  const layout = await source('../src/components/layout/AppLayout.vue')

  assert.match(
    router,
    /path: '\/safety-insights',[\s\S]*?name: 'safety-insights',[\s\S]*?SafetyInsightsView\.vue/,
  )
  assert.match(
    layout,
    /to="\/plan">My Plan<\/router-link>[\s\S]*?to="\/overview">Overview<\/router-link>[\s\S]*?to="\/safety-insights">Safety Insights<\/router-link>[\s\S]*?to="\/map">Fire Map<\/router-link>[\s\S]*?to="\/travel-readiness">Travel Readiness<\/router-link>[\s\S]*?to="\/scenarios">Test My Plan<\/router-link>/,
  )
})

test('Safety Insights renders FDR first and Safety Guidance second as independent components', async () => {
  const insights = await source('../src/views/SafetyInsightsView.vue')
  const template = insights.slice(insights.indexOf('<template>'), insights.lastIndexOf('</template>'))

  assert.match(insights, /<h1>Safety Insights<\/h1>/)
  assert.ok(template.indexOf('<FdrPredictionPanel />') < template.indexOf('<SafetyChatPanel />'))
  assert.doesNotMatch(template, /v-if=.*(?:fdr|safety)|Promise\.all/)
})

test('Overview removes both insights while retaining its summary and export', async () => {
  const overview = await source('../src/views/OverviewView.vue')

  assert.doesNotMatch(overview, /FdrPredictionPanel|SafetyChatPanel/)
  assert.match(overview, /Household Plan Summary/)
  assert.match(overview, /Export preparedness plan/)
  assert.match(overview, /CompletionOverview/)
  assert.match(overview, /PreparationSupportBanner/)
})

test('FDR failure remains local while reviewed Safety Guidance still renders', async () => {
  const html = await renderInsights(({ fdr, safety }) => {
    fdr.status = 'error'
    fdr.error = 'The fire danger pattern estimate is temporarily unavailable.'
    safety.status = 'success'
    safety.entries = [guidanceEntry]
    safety.suggestedIds = [guidanceEntry.id]
  })

  assert.match(html, /temporarily unavailable/)
  assert.match(html, /Safety guidance/)
  assert.match(html, /What should I prepare\?/)
})

test('Safety Guidance failure remains local while FDR still renders', async () => {
  const html = await renderInsights(({ fdr, safety }) => {
    fdr.status = 'success'
    fdr.result = {
      district: 'Central',
      date: '2026-01-15',
      prediction_label: 'Moderate',
      elevated_probability: 0.4952,
    }
    safety.status = 'error'
    safety.error = 'Safety guidance could not be loaded. Other FIREBREAK features are unaffected.'
  })

  assert.match(html, /Historical pattern:[\s\S]*Moderate/)
  assert.match(html, /49\.5%/)
  assert.match(html, /Safety guidance could not be loaded/)
})

test('Safety Insights and navigation preserve responsive single-column behaviour', async () => {
  const insights = await source('../src/views/SafetyInsightsView.vue')
  const layout = await source('../src/components/layout/AppLayout.vue')
  const fdr = await source('../src/components/overview/FdrPredictionPanel.vue')

  assert.match(insights, /\.insights-stack \{[\s\S]*?display: grid;[\s\S]*?min-width: 0;/)
  assert.match(layout, /\.top-nav \{[^}]*overflow-x: auto;/)
  assert.match(layout, /@media \(max-width: 600px\)[\s\S]*?\.top-nav \{[^}]*width: 100%;/)
  assert.match(fdr, /@media \(max-width: 700px\)[\s\S]*?\.form-grid \{[\s\S]*?grid-template-columns: 1fr;/)
})

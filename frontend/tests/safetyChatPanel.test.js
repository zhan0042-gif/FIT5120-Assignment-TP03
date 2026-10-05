import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import { parse, compileScript } from '@vue/compiler-sfc'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createPinia } from 'pinia'
import { useSafetyGuidanceStore } from '../src/stores/safetyGuidance.js'

// Compile the real panel template without opening a page, as the travel tests do.
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

const entry = (id) => ({
  id,
  question: `Question ${id}?`,
  answer: `Answer ${id}.`,
  source_name: 'CFA',
  source_url: 'https://www.cfa.vic.gov.au/example',
  retrieved_on: '2026-10-05',
})

async function render(context, arrange) {
  const originalStorage = globalThis.localStorage
  globalThis.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} }
  context.after(() => {
    if (originalStorage === undefined) delete globalThis.localStorage
    else globalThis.localStorage = originalStorage
  })
  const { default: Panel } = await import(await loadComponent('../src/components/overview/SafetyChatPanel.vue'))
  const pinia = createPinia()
  arrange(useSafetyGuidanceStore(pinia))
  return renderToString(createSSRApp(Panel).use(pinia))
}

const NOTICE = /This is not for emergencies\. If you are in danger, call 000\./

test('the emergency notice is shown while the guidance is loading', async (context) => {
  const html = await render(context, (store) => { store.status = 'loading' })

  assert.match(html, NOTICE)
})

test('the emergency notice is shown after the guidance fails to load', async (context) => {
  const html = await render(context, (store) => {
    store.status = 'error'
    store.error = 'Safety guidance could not be loaded.'
  })

  assert.match(html, NOTICE)
  assert.match(html, /could not be loaded/)
})

test('the emergency notice and an empty message are shown when no entry is reviewed', async (context) => {
  const html = await render(context, (store) => {
    store.status = 'success'
    store.entries = []
    store.suggestedIds = []
  })

  assert.match(html, NOTICE)
  assert.match(html, /No guidance is available/)
  assert.doesNotMatch(html, /class="chip"/)
})

test('the live region exists before the first answer so the answer is announced', async (context) => {
  const html = await render(context, (store) => {
    store.status = 'success'
    store.entries = [entry('a')]
    store.suggestedIds = ['a']
  })

  assert.match(html, /role="log"/)
})

test('answers appear below the suggested questions, not above them', async (context) => {
  const html = await render(context, (store) => {
    store.status = 'success'
    store.entries = [entry('a'), entry('b')]
    store.suggestedIds = ['a', 'b']
    store.messages = [
      { id: 1, role: 'user', text: 'Question a?' },
      { id: 2, role: 'assistant', entryId: 'a' },
    ]
  })

  const chips = html.indexOf('class="chip"')
  const answer = html.indexOf('Answer a.')
  assert.ok(chips !== -1 && answer !== -1, 'both the chips and the answer are rendered')
  assert.ok(chips < answer, 'the chips come before the conversation')
})

test('there is no long list of answers any more', async (context) => {
  const html = await render(context, (store) => {
    store.status = 'success'
    store.entries = [entry('a'), entry('b')]
    store.suggestedIds = ['a']
  })

  assert.doesNotMatch(html, /Read all guidance/)
  assert.doesNotMatch(html, /<details/)
})

test('the remaining questions are behind a collapsed More questions button', async (context) => {
  const html = await render(context, (store) => {
    store.status = 'success'
    store.entries = [entry('a'), entry('b'), entry('c')]
    store.suggestedIds = ['a']
  })

  assert.match(html, /More questions/)
  assert.match(html, /aria-expanded="false"/)
  assert.doesNotMatch(html, /Question b\?/)
  assert.doesNotMatch(html, /Question c\?/)
})

test('there is no More questions button when every question is already suggested', async (context) => {
  const html = await render(context, (store) => {
    store.status = 'success'
    store.entries = [entry('a')]
    store.suggestedIds = ['a']
  })

  assert.doesNotMatch(html, /More questions/)
})

test('a typed question box is shown when there are entries', async (context) => {
  const html = await render(context, (store) => {
    store.status = 'success'
    store.entries = [entry('a')]
    store.suggestedIds = ['a']
  })

  assert.match(html, /id="safety-question"/)
  assert.match(html, /maxlength="300"/)
  assert.match(html, /<label[^>]*for="safety-question"/)
})

test('the typed question box is hidden while the guidance is loading', async (context) => {
  const html = await render(context, (store) => { store.status = 'loading' })

  assert.doesNotMatch(html, /id="safety-question"/)
})

test('the typed question box is hidden after the guidance fails to load', async (context) => {
  const html = await render(context, (store) => {
    store.status = 'error'
    store.error = 'Could not be loaded.'
  })

  assert.doesNotMatch(html, /id="safety-question"/)
})

test('the typed question box is hidden when there are no entries', async (context) => {
  const html = await render(context, (store) => {
    store.status = 'success'
    store.entries = []
    store.suggestedIds = []
  })

  assert.doesNotMatch(html, /id="safety-question"/)
})

test('the send control is disabled while a question is in flight', async (context) => {
  const html = await render(context, (store) => {
    store.status = 'success'
    store.entries = [entry('a')]
    store.suggestedIds = ['a']
    store.asking = true
  })

  assert.match(html, /ask-button[^>]*disabled/)
})

test('a no-match reply shows the fixed message', async (context) => {
  const html = await render(context, (store) => {
    store.status = 'success'
    store.entries = [entry('a')]
    store.suggestedIds = ['a']
    store.messages = [
      { id: 1, role: 'user', text: 'Should I leave tomorrow?' },
      { id: 2, role: 'assistant', kind: 'no_match' },
    ]
  })

  assert.match(html, /Should I leave tomorrow\?/)
  assert.match(html, /don&#39;t have a reviewed answer|don't have a reviewed answer/)
})

test('an emergency reply is an alert that says to call 000 now', async (context) => {
  const html = await render(context, (store) => {
    store.status = 'success'
    store.entries = [entry('a')]
    store.suggestedIds = ['a']
    store.messages = [
      { id: 1, role: 'user', text: 'My house is on fire' },
      { id: 2, role: 'assistant', kind: 'emergency' },
    ]
  })

  assert.match(html, /role="alert"/)
  assert.match(html, /call 000 now/)
})

test('an unavailable reply points to the suggested questions', async (context) => {
  const html = await render(context, (store) => {
    store.status = 'success'
    store.entries = [entry('a')]
    store.suggestedIds = ['a']
    store.messages = [
      { id: 1, role: 'user', text: 'Anything?' },
      { id: 2, role: 'assistant', kind: 'unavailable' },
    ]
  })

  assert.match(html, /not available right now/)
  assert.match(html, /suggested questions/)
})

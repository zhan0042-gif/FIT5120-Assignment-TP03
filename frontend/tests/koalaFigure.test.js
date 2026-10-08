import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { importComponent } from './helpers/loadComponent.js'

const { FACES } = await import('../src/voice/expression.js')
const { MOUTHS, POSES } = await import('../src/voice/koalaPose.js')

async function render(props) {
  const KoalaFigure = await importComponent('../src/components/layout/KoalaFigure.vue')
  return renderToString(createSSRApp(KoalaFigure, props))
}

test('it is a decorative svg that carries its face and talking state as data', async () => {
  const html = await render({ face: 'concerned', talking: false })

  assert.match(html, /^<svg/)
  assert.match(html, /aria-hidden="true"/)
  assert.match(html, /viewBox="0 0 120 120"/)
  assert.match(html, /data-face="concerned"/)
  assert.match(html, /data-talking="false"/)
})

test('every face renders, and an unknown face falls back to neutral', async () => {
  for (const face of FACES) {
    assert.match(await render({ face }), new RegExp(`data-face="${face}"`), face)
  }
  assert.match(await render({ face: 'nonsense' }), /data-face="neutral"/)
})

test('the parts that change are drawn: ears, head, nose, two eyes, two eyebrows and a mouth', async () => {
  const html = await render({ face: 'neutral' })

  assert.equal((html.match(/class="ear"/g) ?? []).length, 2)
  assert.match(html, /class="head"/)
  assert.match(html, /class="nose"/)
  assert.equal((html.match(/class="eye /g) ?? []).length, 2)
  assert.equal((html.match(/class="brow /g) ?? []).length, 2)
  assert.match(html, /class="mouth/)
})

test('the eyes are narrowed for a serious face and wide for a concerned one', async () => {
  const serious = await render({ face: 'serious' })
  const concerned = await render({ face: 'concerned' })

  assert.match(serious, new RegExp(`scale\\(1, ${POSES.serious.eyeOpen}\\)`))
  assert.match(concerned, new RegExp(`scale\\(1, ${POSES.concerned.eyeOpen}\\)`))
})

test('the eyebrows tilt the way the pose says', async () => {
  const html = await render({ face: 'concerned' })

  assert.match(html, new RegExp(`rotate\\(${POSES.concerned.browLeft.rot}deg\\)`))
  assert.match(html, new RegExp(`rotate\\(${POSES.concerned.browRight.rot}deg\\)`))
})

test('a happy face draws smiling arcs instead of round eyes', async () => {
  const happy = await render({ face: 'happy' })
  const neutral = await render({ face: 'neutral' })

  assert.match(happy, /class="eye-arc/)
  assert.doesNotMatch(neutral, /class="eye-arc/)
})

test('the active mouth is the pose mouth, and the others are hidden', async () => {
  const html = await render({ face: 'happy' })

  for (const [name, shape] of Object.entries(MOUTHS)) {
    assert.ok(html.includes(`d="${shape.d}"`), name)
  }
  const active = html.match(/class="mouth active"/g) ?? []
  assert.equal(active.length, 1)
  assert.match(html, new RegExp(`class="mouth active"[^>]*d="${MOUTHS.wide.d}"`))
})

test('while talking the open mouth shows and no resting mouth is active', async () => {
  const talking = await render({ face: 'serious', talking: true })
  const quiet = await render({ face: 'serious', talking: false })

  assert.match(talking, /class="mouth-open"/)
  assert.match(talking, /data-talking="true"/)
  assert.equal((talking.match(/class="mouth active"/g) ?? []).length, 0)
  assert.doesNotMatch(quiet, /class="mouth-open"/)
})

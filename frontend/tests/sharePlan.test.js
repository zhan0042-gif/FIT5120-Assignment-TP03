import assert from 'node:assert/strict'
import test from 'node:test'
import {
  SHARE_TEXT,
  SHARE_TITLE,
  canShareFile,
  pdfFile,
  shareFile,
  whatsappWebUrl,
} from '../src/utils/sharePlan.js'

const blob = new Blob(['%PDF-test'], { type: 'application/pdf' })

function navigatorWith({ share, canShare = () => true } = {}) {
  return { share, canShare }
}

test('the PDF becomes a named application/pdf file', () => {
  const file = pdfFile(blob, 'firebreak-household-plan.pdf')
  assert.equal(file.name, 'firebreak-household-plan.pdf')
  assert.equal(file.type, 'application/pdf')
  assert.equal(file.size, blob.size)
})

test('file sharing needs share() and a canShare() that accepts this file', () => {
  const file = pdfFile(blob, 'a.pdf')
  assert.equal(canShareFile(navigatorWith({ share: async () => {} }), file), true)
  assert.equal(canShareFile(navigatorWith({ share: async () => {}, canShare: () => false }), file), false)
  assert.equal(canShareFile({ share: async () => {} }, file), false)
  assert.equal(canShareFile({ canShare: () => true }, file), false)
  assert.equal(canShareFile(undefined, file), false)
})

test('the share sheet gets the file, a title and a generic message', async () => {
  const calls = []
  const nav = navigatorWith({ share: async (data) => { calls.push(data) } })
  const file = pdfFile(blob, 'a.pdf')
  assert.equal(await shareFile(nav, file), 'shared')
  assert.equal(calls.length, 1)
  assert.deepEqual(calls[0].files, [file])
  assert.equal(calls[0].title, SHARE_TITLE)
  assert.equal(calls[0].text, SHARE_TEXT)
})

test('the shared message carries no personal details', () => {
  assert.doesNotMatch(SHARE_TEXT, /\d/)
  assert.match(SHARE_TEXT, /FIREBREAK/)
  assert.ok(SHARE_TEXT.length < 120)
})

test('closing the share sheet is not an error', async () => {
  const nav = navigatorWith({ share: async () => { throw new DOMException('closed', 'AbortError') } })
  assert.equal(await shareFile(nav, pdfFile(blob, 'a.pdf')), 'cancelled')
})

test('a browser that wants a fresh tap asks for one', async () => {
  const nav = navigatorWith({ share: async () => { throw new DOMException('gesture', 'NotAllowedError') } })
  assert.equal(await shareFile(nav, pdfFile(blob, 'a.pdf')), 'needs-gesture')
})

test('a browser without file sharing is reported, not attempted', async () => {
  let called = false
  const nav = navigatorWith({ share: async () => { called = true }, canShare: () => false })
  assert.equal(await shareFile(nav, pdfFile(blob, 'a.pdf')), 'unsupported')
  assert.equal(called, false)
})

test('any other share failure is raised', async () => {
  const nav = navigatorWith({ share: async () => { throw new Error('boom') } })
  await assert.rejects(() => shareFile(nav, pdfFile(blob, 'a.pdf')), /boom/)
})

test('the WhatsApp Web link carries only the generic message', () => {
  const url = whatsappWebUrl()
  assert.ok(url.startsWith('https://wa.me/?text='))
  assert.equal(decodeURIComponent(url.slice('https://wa.me/?text='.length)), SHARE_TEXT)
})

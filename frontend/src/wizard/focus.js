import { nextTick } from 'vue'

// After a card is added or removed the page re-renders; keyboard and screen-reader
// users need focus to land somewhere sensible rather than on the page body.
export async function focusAfterRender(id) {
  await nextTick()
  globalThis.document?.getElementById(id)?.focus()
}

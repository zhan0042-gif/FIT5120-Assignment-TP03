// A question that has just appeared ignores picks for a moment, so the second
// half of a double-click cannot answer the next question as well.
export const PICK_GRACE_MS = 350

export function acceptsPick(openedAt, now) {
  return now - openedAt >= PICK_GRACE_MS
}

// Arrow keys inside a radio group fire a click with detail 0. Those only move
// the selection; a pointer click (detail >= 1) also answers.
export function isPointerClick(event) {
  return event.detail > 0
}

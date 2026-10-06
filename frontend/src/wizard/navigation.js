import { SECTIONS } from './flow.js'

export function indexOfKey(steps, key) {
  return steps.findIndex((step) => step.key === key)
}

export function nextKey(steps, key) {
  return steps[indexOfKey(steps, key) + 1]?.key ?? 'review'
}

export function previousKey(steps, key) {
  const index = indexOfKey(steps, key)
  return steps[Math.max(index - 1, 0)]?.key ?? 'review'
}

// After an answer is written the list is rebuilt. If the step that was answered
// still exists, move past it. If it vanished (a "yes" turned the last-person
// gate into a new person's questions) the next step now occupies its slot.
export function keyAfterWrite(steps, previousStepKey, previousIndex) {
  const index = indexOfKey(steps, previousStepKey)
  const target = index === -1 ? Math.min(previousIndex, steps.length - 1) : index + 1
  return steps[target]?.key ?? 'review'
}

export function firstKeyOfSection(steps, sectionId) {
  return steps.find((step) => step.section === sectionId)?.key ?? 'review'
}

export function nextSectionKey(steps, sectionId) {
  const last = steps.findLastIndex((step) => step.section === sectionId)
  return steps[last + 1]?.key ?? 'review'
}

export function firstIncompleteSection(completion) {
  return completion?.sections?.find((section) => section.status !== 'complete')?.section ?? null
}

const LEGACY_SECTIONS = {
  people: 'household_profile',
  destinations: 'primary_destination',
}

export function resolveSectionParam(value) {
  if (typeof value !== 'string') return null
  if (value === 'review') return 'review'
  if (SECTIONS.some((section) => section.id === value)) return value
  return LEGACY_SECTIONS[value] ?? null
}

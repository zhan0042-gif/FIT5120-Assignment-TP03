// Five form screens over the seven backend sections. The order of the sections
// matches PlanCompletionService.SECTION_ORDER in the backend.
export const SCREENS = [
  { id: 'household', title: 'Your household', short: 'Household', sections: ['household_profile'] },
  { id: 'daytime', title: 'Where everyone is by day', short: 'Daytime', sections: ['member_locations'] },
  { id: 'vehicles', title: 'How you would leave', short: 'Vehicles', sections: ['transport', 'backup_transport'] },
  { id: 'places', title: 'Where you would go', short: 'Places', sections: ['primary_destination', 'backup_destination'] },
  { id: 'jobs', title: 'Who does what', short: 'Jobs', sections: ['responsibilities'] },
]

const LEGACY = { people: 'household', destinations: 'places' }

export const screenOfSection = (sectionId) => SCREENS.find((screen) => screen.sections.includes(sectionId))?.id ?? null

export function screenComplete(completion, screenId) {
  const screen = SCREENS.find((item) => item.id === screenId)
  if (!screen) return false
  return screen.sections.every(
    (id) => completion?.sections?.find((item) => item.section === id)?.status === 'complete',
  )
}

export const firstIncompleteScreen = (completion) =>
  SCREENS.find((screen) => !screenComplete(completion, screen.id))?.id ?? null

export function nextScreen(screenId) {
  const index = SCREENS.findIndex((screen) => screen.id === screenId)
  return SCREENS[index + 1]?.id ?? 'review'
}

export function previousScreen(screenId) {
  const index = SCREENS.findIndex((screen) => screen.id === screenId)
  return index > 0 ? SCREENS[index - 1].id : null
}

export function resolveScreenParam(value) {
  if (typeof value !== 'string') return null
  if (value === 'review') return 'review'
  if (SCREENS.some((screen) => screen.id === value)) return value
  return screenOfSection(value) ?? LEGACY[value] ?? null
}

import { backupDestinationSteps } from './sections/backupDestination.js'
import { backupTransportSteps } from './sections/backupTransport.js'
import { householdProfileSteps } from './sections/householdProfile.js'
import { memberLocationSteps } from './sections/memberLocations.js'
import { primaryDestinationSteps } from './sections/primaryDestination.js'
import { responsibilitySteps } from './sections/responsibilities.js'
import { transportSteps } from './sections/transport.js'

// The order matches PlanCompletionService.SECTION_ORDER in the backend.
export const SECTIONS = [
  { id: 'household_profile', title: 'Your household', short: 'Household' },
  { id: 'member_locations', title: 'Where everyone is by day', short: 'Daytime' },
  { id: 'transport', title: 'How you would leave', short: 'Vehicle' },
  { id: 'backup_transport', title: 'If that vehicle is not available', short: 'Backup vehicle' },
  { id: 'primary_destination', title: 'Where you would go', short: 'Destination' },
  { id: 'backup_destination', title: 'Where you would go instead', short: 'Backup place' },
  { id: 'responsibilities', title: 'Who does what', short: 'Jobs' },
]

const BUILDERS = {
  household_profile: householdProfileSteps,
  member_locations: memberLocationSteps,
  transport: transportSteps,
  backup_transport: backupTransportSteps,
  primary_destination: primaryDestinationSteps,
  backup_destination: backupDestinationSteps,
  responsibilities: responsibilitySteps,
}

export function buildSteps(plan) {
  const steps = []
  for (const section of SECTIONS) {
    const questions = BUILDERS[section.id](plan)
    // An empty section (backup transport without a vehicle) is skipped whole.
    if (!questions.length) continue
    steps.push(...questions, { key: `summary:${section.id}`, section: section.id, kind: 'summary', optional: false })
  }
  steps.push({ key: 'review', section: null, kind: 'review', optional: false })
  return steps
}

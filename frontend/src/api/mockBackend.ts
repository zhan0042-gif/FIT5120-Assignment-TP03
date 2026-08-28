// Stand-in for the not-yet-built Backend (see "Iteration 1 总体分工与数据流", section 4:
// Frontend develops against Mock JSON and does not wait on Database/DS/Backend).
//
// Every exported function here mirrors one endpoint from the I1 API Contract
// (POST/GET/PUT /api/v1/households/...). When the real Backend exists, only
// `src/api/client.ts` needs to change — components never import this file directly.

import type { HouseholdPlan, PlanCompletion } from '../types/household'
import type { LocalContext, PreparationSupport } from '../types/localContext'
import type { Scenario, TestResult, TestCheck } from '../types/scenario'

const STORAGE_KEY = 'firebreak.household-plan.v1'
const LOCATION_KEY = 'firebreak.location.v1'

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function seedPlan(): HouseholdPlan {
  return {
    members: [
      {
        member_id: 'm_001',
        display_name: 'Maya',
        is_dependant: false,
        mobility_support_required: false,
        support_notes: null,
      },
    ],
    pets: [
      { pet_id: 'p_001', display_name: 'Buddy', pet_type: 'dog', support_notes: null },
    ],
    transports: [
      {
        transport_id: 't_001',
        transport_type: 'car',
        display_name: 'Family Car',
        driver_member_ids: ['m_001'],
      },
    ],
    arrangements: {
      primary_transport_id: 't_001',
      backup_transport_id: null,
      primary_destination: {
        destination_id: 'd_001',
        display_name: "Relative's House",
        address: 'Example address',
      },
      backup_destination: null,
      meeting_point: 'Front gate',
    },
    responsibilities: [
      {
        responsibility_id: 'r_001',
        task_name: 'Drive household',
        primary_member_id: 'm_001',
        backup_member_id: null,
      },
    ],
  }
}

function loadPlan(): HouseholdPlan {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return seedPlan()
  try {
    return JSON.parse(raw) as HouseholdPlan
  } catch {
    return seedPlan()
  }
}

function persistPlan(plan: HouseholdPlan) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(plan))
}

let planCache: HouseholdPlan = loadPlan()

export function genId(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 9)}`
}

// ---------------------------------------------------------------------------
// Household Plan (US1.1-US1.4)
// ---------------------------------------------------------------------------

// JSON round-trip rather than structuredClone: the plan passed in from a Vue
// component may be a reactive proxy, which structuredClone cannot clone.
function cloneViaJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

export async function fetchHouseholdPlan(): Promise<HouseholdPlan> {
  await delay(400)
  return cloneViaJson(planCache)
}

export async function saveHouseholdPlan(plan: HouseholdPlan): Promise<HouseholdPlan> {
  await delay(500)
  planCache = cloneViaJson(plan)
  persistPlan(planCache)
  return cloneViaJson(planCache)
}

// ---------------------------------------------------------------------------
// Plan Completion (US1.5) — computed here (mock backend), not in UI components
// ---------------------------------------------------------------------------

export async function fetchCompletion(): Promise<PlanCompletion> {
  await delay(300)
  return computeCompletion(planCache)
}

export function computeCompletion(plan: HouseholdPlan): PlanCompletion {
  const householdOk =
    plan.members.length > 0 &&
    plan.members.every((m) => m.display_name.trim().length > 0) &&
    plan.pets.every((p) => p.display_name.trim().length > 0 && p.pet_type.trim().length > 0)
  const transportOk = plan.transports.length > 0 && !!plan.arrangements.primary_transport_id
  const backupTransportOk = !!plan.arrangements.backup_transport_id
  const primaryDestinationOk =
    !!plan.arrangements.primary_destination &&
    plan.arrangements.primary_destination.display_name.trim().length > 0
  const backupDestinationOk =
    !!plan.arrangements.backup_destination &&
    plan.arrangements.backup_destination.display_name.trim().length > 0
  const responsibilitiesOk =
    plan.responsibilities.length > 0 &&
    plan.responsibilities.every((r) => r.task_name.trim().length > 0 && !!r.primary_member_id)

  const sections = [
    { section: 'household_profile', status: householdOk ? 'complete' : 'needs_information' },
    { section: 'transport', status: transportOk ? 'complete' : 'needs_information' },
    { section: 'backup_transport', status: backupTransportOk ? 'complete' : 'needs_information' },
    { section: 'primary_destination', status: primaryDestinationOk ? 'complete' : 'needs_information' },
    { section: 'backup_destination', status: backupDestinationOk ? 'complete' : 'needs_information' },
    { section: 'responsibilities', status: responsibilitiesOk ? 'complete' : 'needs_information' },
  ] as PlanCompletion['sections']

  const overall_status = sections.every((s) => s.status === 'complete') ? 'complete' : 'needs_information'
  return { overall_status, sections }
}

// ---------------------------------------------------------------------------
// Location & Local Context (US2.1-US2.3)
// ---------------------------------------------------------------------------

export function loadSavedAddress(): string {
  return localStorage.getItem(LOCATION_KEY) ?? ''
}

export async function saveLocation(address: string): Promise<{ address: string }> {
  await delay(350)
  localStorage.setItem(LOCATION_KEY, address)
  return { address }
}

class ApiError extends Error {}

export async function fetchLocalContext(address: string): Promise<LocalContext | null> {
  await delay(500)

  if (/error/i.test(address)) {
    throw new ApiError('The local context service did not respond. Please try again.')
  }

  // AC4 (US2.1): unavailable data when the location cannot be matched.
  if (!/vic/i.test(address)) {
    return null
  }

  const seed = hashString(address)
  const lat = -37.6 - (seed % 40) / 100
  const lng = 144.9 + (seed % 60) / 100

  return {
    location: { address, latitude: Number(lat.toFixed(2)), longitude: Number(lng.toFixed(2)) },
    bushfire_context: {
      is_bushfire_prone_area: seed % 5 !== 0,
      fire_district: 'Central',
    },
    fire_danger: {
      today: 'Moderate',
      tomorrow: 'High',
      day_3: 'High',
      day_4: 'Extreme',
      source_updated_at: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
    },
    weather: {
      temperature_c: 28.0,
      relative_humidity: 32,
      wind_speed_kmh: 30,
      wind_direction: 'NW',
      forecast_time: new Date().toISOString(),
    },
    environmental_context: {
      vegetation: null,
      terrain: null,
    },
  }
}

export async function fetchPreparationSupport(): Promise<PreparationSupport> {
  await delay(350)
  const address = loadSavedAddress()
  const context = await fetchLocalContext(address).catch(() => null)
  const completion = computeCompletion(planCache)
  const gaps = completion.sections
    .filter((section) => section.status === 'needs_information')
    .map((section) => section.section)
  const levels = ['No Rating', 'Moderate', 'High', 'Extreme', 'Catastrophic']
  const ratings = context
    ? [
        context.fire_danger.today,
        context.fire_danger.tomorrow,
        context.fire_danger.day_3,
        context.fire_danger.day_4,
      ].map((rating) => levels.indexOf(rating))
    : []
  const escalating = ratings.length > 1 && Math.max(...ratings.slice(1)) > ratings[0]
  const serious = ratings.some((rating) => rating >= levels.indexOf('High'))

  if (escalating || serious) {
    return {
      status: 'review_recommended',
      message: 'Local fire conditions are expected to become more serious.',
      sections_to_review: gaps,
    }
  }

  if (gaps.length > 0) {
    return {
      status: 'review_recommended',
      message: 'Review the incomplete sections of your household plan.',
      sections_to_review: gaps,
    }
  }

  return {
    status: 'up_to_date',
    message: 'No immediate plan review is recommended.',
    sections_to_review: [],
  }
}

// ---------------------------------------------------------------------------
// Basic Scenarios & Test Result (US3.1-US3.3)
// ---------------------------------------------------------------------------

const SCENARIOS: Scenario[] = [
  {
    scenario_id: 'vehicle_unavailable',
    title: 'Main Vehicle Unavailable',
    description: 'Check whether another transport option is available.',
  },
  {
    scenario_id: 'person_unavailable',
    title: 'Primary Responsible Person Unavailable',
    description: 'Check whether important responsibilities have backup people.',
  },
  {
    scenario_id: 'destination_unavailable',
    title: 'Primary Destination Unavailable',
    description: 'Check whether another destination is available.',
  },
]

export async function fetchScenarios(): Promise<Scenario[]> {
  await delay(300)
  return SCENARIOS
}

export async function runBasicTest(scenarioId: string): Promise<TestResult> {
  await delay(600)
  const plan = planCache
  const checks: TestCheck[] = []
  let firstProblem: TestResult['first_problem'] = null

  if (scenarioId === 'vehicle_unavailable') {
    const primaryId = plan.arrangements.primary_transport_id
    const backupId = plan.arrangements.backup_transport_id
    const backup = plan.transports.find((transport) => transport.transport_id === backupId)
    const hasBackupTransport = !!backupId && backupId !== primaryId && !!backup
    checks.push({
      check: 'backup_transport',
      status: hasBackupTransport ? 'pass' : 'fail',
      message: hasBackupTransport
        ? 'A different backup transport is set.'
        : 'No different backup transport is set.',
    })
    if (!hasBackupTransport) {
      checks.push({
        check: 'backup_driver',
        status: 'not_checked',
        message: 'A backup driver cannot be checked because no backup transport is set.',
      })
      firstProblem = {
        section: 'transport',
        message: 'Your plan needs a backup transport arrangement.',
      }
    } else {
      const memberIds = new Set(plan.members.map((member) => member.member_id))
      const hasDriver = backup.driver_member_ids.some((memberId) => memberIds.has(memberId))
      checks.push({
        check: 'backup_driver',
        status: hasDriver ? 'pass' : 'fail',
        message: hasDriver
          ? 'The backup transport has a valid driver.'
          : 'The backup transport has no valid driver.',
      })
      if (!hasDriver) {
        firstProblem = {
          section: 'transport',
          message: 'Assign a valid driver to the backup transport.',
        }
      }
    }
  } else if (scenarioId === 'person_unavailable') {
    const memberIds = new Set(plan.members.map((member) => member.member_id))
    const hasValidBackups =
      plan.responsibilities.length > 0 &&
      plan.responsibilities.every(
        (responsibility) =>
          !!responsibility.backup_member_id &&
          responsibility.backup_member_id !== responsibility.primary_member_id &&
          memberIds.has(responsibility.backup_member_id),
      )
    checks.push({
      check: 'backup_person',
      status: hasValidBackups ? 'pass' : 'fail',
      message: hasValidBackups
        ? 'Every responsibility has a different backup person.'
        : 'One or more responsibilities do not have a different backup person.',
    })
    if (!hasValidBackups) {
      firstProblem = {
        section: 'responsibilities',
        message: 'Assign a different backup person to every important responsibility.',
      }
    }
  } else if (scenarioId === 'destination_unavailable') {
    const primary = plan.arrangements.primary_destination
    const backup = plan.arrangements.backup_destination
    const hasBackupDestination = !!(
      primary &&
      backup &&
      backup.destination_id !== primary.destination_id &&
      (backup.address ?? '').trim().toLowerCase() !==
        (primary.address ?? '').trim().toLowerCase()
    )
    checks.push({
      check: 'backup_destination',
      status: hasBackupDestination ? 'pass' : 'fail',
      message: hasBackupDestination
        ? 'A different backup destination is set.'
        : 'No meaningfully different backup destination is set.',
    })
    if (!hasBackupDestination) {
      firstProblem = {
        section: 'backup_destination',
        message: 'Your plan needs a different backup destination.',
      }
    }
  }

  const overall_status = checks.some((check) => check.status === 'fail')
    ? 'needs_attention'
    : 'pass'

  return {
    test_run_id: genId('test'),
    scenario_id: scenarioId,
    overall_status,
    checks,
    first_problem: firstProblem,
    tested_at: new Date().toISOString(),
  }
}

function hashString(input: string): number {
  let hash = 0
  for (let i = 0; i < input.length; i += 1) {
    hash = (hash * 31 + input.charCodeAt(i)) >>> 0
  }
  return hash
}

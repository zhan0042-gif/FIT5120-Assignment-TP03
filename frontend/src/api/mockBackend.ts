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
    household_id: 'h_001',
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
  const householdOk = plan.members.length > 0 && plan.members.every((m) => m.display_name.trim().length > 0)
  const transportOk = plan.transports.length > 0
  const primaryDestinationOk =
    !!plan.arrangements.primary_transport_id &&
    !!plan.arrangements.primary_destination &&
    plan.arrangements.primary_destination.display_name.trim().length > 0
  const backupDestinationOk = plan.arrangements.backup_destination !== null
  const responsibilitiesOk =
    plan.responsibilities.length > 0 && plan.responsibilities.every((r) => !!r.primary_member_id)

  const sections = [
    { section: 'household_profile', status: householdOk ? 'complete' : 'needs_information' },
    { section: 'transport', status: transportOk ? 'complete' : 'needs_information' },
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
  const plan = planCache

  const gaps: string[] = []
  if (plan.arrangements.backup_transport_id === null) gaps.push('backup_transport')
  if (plan.arrangements.backup_destination === null) gaps.push('backup_destination')
  if (plan.responsibilities.some((r) => !r.backup_member_id)) gaps.push('responsibilities')

  const seriousWeather =
    !!context &&
    (['High', 'Extreme', 'Catastrophic'] as string[]).includes(context.fire_danger.tomorrow)

  if (seriousWeather && gaps.length > 0) {
    return {
      status: 'review_recommended',
      message: 'Local fire conditions are expected to become more serious.',
      sections_to_review: gaps,
    }
  }

  return {
    status: 'on_track',
    message: context
      ? 'Your household plan looks steady for current local conditions.'
      : 'Add your location to receive preparation timing guidance.',
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

  if (scenarioId === 'vehicle_unavailable') {
    const hasBackupTransport = !!plan.arrangements.backup_transport_id
    checks.push({
      check: 'backup_transport',
      status: hasBackupTransport ? 'pass' : 'fail',
      message: hasBackupTransport
        ? 'A backup transport option is recorded.'
        : 'No backup transport is set.',
    })
    if (!hasBackupTransport) {
      checks.push({
        check: 'backup_driver',
        status: 'not_checked',
        message: 'A backup driver cannot be checked because no backup transport is set.',
      })
    } else {
      const backup = plan.transports.find((t) => t.transport_id === plan.arrangements.backup_transport_id)
      const hasDriver = !!backup && backup.driver_member_ids.length > 0
      checks.push({
        check: 'backup_driver',
        status: hasDriver ? 'pass' : 'fail',
        message: hasDriver
          ? 'The backup transport has at least one available driver.'
          : 'The backup transport has no driver assigned.',
      })
    }
  } else if (scenarioId === 'person_unavailable') {
    const missingBackups = plan.responsibilities.filter((r) => r.primary_member_id && !r.backup_member_id)
    checks.push({
      check: 'responsibility_backups',
      status: plan.responsibilities.length > 0 && missingBackups.length === 0 ? 'pass' : 'fail',
      message:
        missingBackups.length === 0
          ? 'Every responsibility has a backup person.'
          : `No backup person is set for: ${missingBackups.map((r) => r.task_name).join(', ')}.`,
    })
    const primaryTransport = plan.transports.find((t) => t.transport_id === plan.arrangements.primary_transport_id)
    const redundantDrivers = (primaryTransport?.driver_member_ids.length ?? 0) > 1 || !!plan.arrangements.backup_transport_id
    checks.push({
      check: 'driver_redundancy',
      status: redundantDrivers ? 'pass' : 'fail',
      message: redundantDrivers
        ? 'More than one person can drive the household if needed.'
        : 'Only one person can currently drive the household.',
    })
  } else if (scenarioId === 'destination_unavailable') {
    const hasBackupDestination = plan.arrangements.backup_destination !== null
    checks.push({
      check: 'backup_destination',
      status: hasBackupDestination ? 'pass' : 'fail',
      message: hasBackupDestination
        ? 'A backup destination is recorded.'
        : 'No backup destination is set.',
    })
    if (!hasBackupDestination) {
      checks.push({
        check: 'meeting_point',
        status: 'not_checked',
        message: 'A meeting point cannot be relied on without a backup destination.',
      })
    } else {
      const hasMeetingPoint = !!plan.arrangements.meeting_point
      checks.push({
        check: 'meeting_point',
        status: hasMeetingPoint ? 'pass' : 'fail',
        message: hasMeetingPoint
          ? 'A meeting point is recorded in case the household is separated.'
          : 'No meeting point is set in case the household is separated.',
      })
    }
  }

  const overall_status = checks.some((c) => c.status === 'fail') ? 'needs_attention' : 'ok'
  const firstFail = checks.find((c) => c.status === 'fail')

  return {
    test_run_id: genId('test'),
    scenario_id: scenarioId,
    overall_status,
    checks,
    first_problem: firstFail
      ? { section: firstFail.check, message: firstFail.message }
      : null,
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

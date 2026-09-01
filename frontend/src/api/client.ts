import type {
  HouseholdCreate,
  HouseholdCreated,
  HouseholdPlan,
  PlanCompletion,
} from '../types/household'
import type {
  LocalContext,
  LocationRequest,
  PreparationSupport,
  ResolvedLocation,
} from '../types/localContext'
import type { Scenario, ScenarioId, TestResult } from '../types/scenario'

const API_ROOT = '/api/v1'
const HOUSEHOLD_ID_KEY = 'firebreak.household-id.v1'

interface FastApiValidationItem {
  msg?: string
  loc?: Array<string | number>
  [key: string]: unknown
}

export class ApiError extends Error {
  readonly status: number
  readonly validationDetails: unknown[]

  constructor(status: number, message: string, validationDetails: unknown[] = []) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.validationDetails = validationDetails
  }
}

function validationMessage(items: FastApiValidationItem[]): string {
  const messages = items
    .map((item) => {
      const location = item.loc?.slice(1).join('.')
      return item.msg ? `${location ? `${location}: ` : ''}${item.msg}` : null
    })
    .filter((message): message is string => message !== null)
  return messages.join('; ') || 'The request contains invalid information.'
}

async function apiError(response: Response): Promise<ApiError> {
  let body: unknown
  try {
    body = await response.json()
  } catch {
    return new ApiError(response.status, response.statusText || 'The request failed.')
  }

  if (typeof body === 'object' && body !== null && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === 'string') return new ApiError(response.status, detail)
    if (Array.isArray(detail)) {
      return new ApiError(
        response.status,
        validationMessage(detail as FastApiValidationItem[]),
        detail,
      )
    }
    if (typeof detail === 'object' && detail !== null) {
      const businessDetail = detail as { message?: unknown; errors?: unknown }
      const errors = Array.isArray(businessDetail.errors) ? businessDetail.errors : []
      const message =
        typeof businessDetail.message === 'string'
          ? businessDetail.message
          : errors.filter((item): item is string => typeof item === 'string').join('; ')
      return new ApiError(
        response.status,
        message || 'The request contains invalid information.',
        errors,
      )
    }
  }
  return new ApiError(response.status, response.statusText || 'The request failed.')
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (init?.body !== undefined) headers.set('Content-Type', 'application/json')
  const response = await fetch(`${API_ROOT}${path}`, { ...init, headers })
  if (!response.ok) throw await apiError(response)
  return (await response.json()) as T
}

export function loadStoredHouseholdId(): string | null {
  return localStorage.getItem(HOUSEHOLD_ID_KEY)
}

export function storeHouseholdId(householdId: string): void {
  localStorage.setItem(HOUSEHOLD_ID_KEY, householdId)
}

export function clearStoredHouseholdId(): void {
  localStorage.removeItem(HOUSEHOLD_ID_KEY)
}

export const api = {
  createHousehold: (input?: HouseholdCreate): Promise<HouseholdCreated> =>
    request('/households', {
      method: 'POST',
      body: input ? JSON.stringify(input) : undefined,
    }),

  getHouseholdPlan: (householdId: string): Promise<HouseholdPlan> =>
    request(`/households/${encodeURIComponent(householdId)}/plan`),

  saveHouseholdPlan: (householdId: string, plan: HouseholdPlan): Promise<HouseholdPlan> =>
    request(`/households/${encodeURIComponent(householdId)}/plan`, {
      method: 'PUT',
      body: JSON.stringify(plan),
    }),

  getCompletion: (householdId: string): Promise<PlanCompletion> =>
    request(`/households/${encodeURIComponent(householdId)}/completion`),

  saveLocation: (
    householdId: string,
    input: LocationRequest,
  ): Promise<ResolvedLocation> =>
    request(`/households/${encodeURIComponent(householdId)}/location`, {
      method: 'PUT',
      body: JSON.stringify(input),
    }),


  getLocationSuggestions: (query: string): Promise<string[]> =>
    request(`/households/location-suggestions?query=${encodeURIComponent(query)}`),
  getLocalContext: (householdId: string): Promise<LocalContext> =>
    request(`/households/${encodeURIComponent(householdId)}/local-context`),

  getPreparationSupport: (householdId: string): Promise<PreparationSupport> =>
    request(`/households/${encodeURIComponent(householdId)}/preparation-support`),

  getBasicScenarios: (householdId: string): Promise<Scenario[]> =>
    request(`/scenarios/basic?household_id=${encodeURIComponent(householdId)}`),

  runBasicTest: (householdId: string, scenarioId: ScenarioId): Promise<TestResult> =>
    request(`/households/${encodeURIComponent(householdId)}/tests`, {
      method: 'POST',
      body: JSON.stringify({ scenario_id: scenarioId }),
    }),

  getTestResult: (householdId: string, testRunId: string): Promise<TestResult> =>
    request(
      `/households/${encodeURIComponent(householdId)}/tests/${encodeURIComponent(testRunId)}`,
    ),
}

export function newId(prefix: string): string {
  return `${prefix}_${crypto.randomUUID().replaceAll('-', '')}`
}

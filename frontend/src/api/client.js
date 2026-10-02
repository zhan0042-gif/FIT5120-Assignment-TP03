const API_ROOT = '/api/v1'
const HOUSEHOLD_ID_KEY = 'firebreak.household-id.v1'

export class ApiError extends Error {
  constructor(status, message, validationDetails = []) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.validationDetails = validationDetails
  }
}

function validationMessage(items) {
  const messages = items
    .map((item) => {
      const location = item.loc?.slice(1).join('.')
      return item.msg ? `${location ? `${location}: ` : ''}${item.msg}` : null
    })
    .filter((message) => message !== null)

  return messages.join('; ') || 'The request contains invalid information.'
}

async function apiError(response) {
  // FastAPI may return a plain message, Pydantic validation items, or the
  // service-layer error envelope. Normalize all forms for stores/components.
  let body

  try {
    body = await response.json()
  } catch {
    return new ApiError(
      response.status,
      response.statusText || 'The request failed.',
    )
  }

  if (typeof body === 'object' && body !== null && 'detail' in body) {
    const detail = body.detail

    if (typeof detail === 'string') {
      return new ApiError(response.status, detail)
    }

    if (Array.isArray(detail)) {
      return new ApiError(
        response.status,
        validationMessage(detail),
        detail,
      )
    }

    if (typeof detail === 'object' && detail !== null) {
      const errors = Array.isArray(detail.errors) ? detail.errors : []

      const message =
        typeof detail.message === 'string'
          ? detail.message
          : errors
              .filter((item) => typeof item === 'string')
              .join('; ')

      return new ApiError(
        response.status,
        message || 'The request contains invalid information.',
        errors,
      )
    }
  }

  return new ApiError(
    response.status,
    response.statusText || 'The request failed.',
  )
}

async function request(path, init) {
  // This is the single HTTP boundary so every feature receives the same JSON
  // parsing and typed ApiError behavior.
  const headers = new Headers(init?.headers)

  if (init?.body !== undefined) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(
    `${API_ROOT}${path}`,
    {
      ...init,
      headers,
    },
  )

  if (!response.ok) {
    throw await apiError(response)
  }

  return await response.json()
}

async function requestPdf(path, init) {
  const headers = new Headers(init?.headers)

  if (init?.body !== undefined) {
    headers.set('Content-Type', 'application/json')
  }

  const requestInit = init
    ? {
        ...init,
        headers,
      }
    : undefined

  const response = await fetch(
    `${API_ROOT}${path}`,
    requestInit,
  )

  if (!response.ok) {
    throw await apiError(response)
  }

  const disposition =
    response.headers.get('Content-Disposition') ?? ''

  const filename =
    disposition.match(/filename="?([^";]+)"?/i)?.[1]

  return {
    blob: await response.blob(),
    filename:
      filename || 'firebreak-household-plan.pdf',
  }
}

export function loadStoredHouseholdId() {
  return localStorage.getItem(
    HOUSEHOLD_ID_KEY,
  )
}

export function storeHouseholdId(
  householdId,
) {
  localStorage.setItem(
    HOUSEHOLD_ID_KEY,
    householdId,
  )
}

export function clearStoredHouseholdId() {
  localStorage.removeItem(
    HOUSEHOLD_ID_KEY,
  )
}

export const api = {
  // Household IDs persist in the browser; plans remain server-owned aggregates.
  createHousehold: (input) =>
    request('/households', {
      method: 'POST',
      body: input
        ? JSON.stringify(input)
        : undefined,
    }),

  getHouseholdPlan: (householdId) =>
    request(
      `/households/${encodeURIComponent(householdId)}/plan`,
    ),

  getPreparednessPlanPdf: (
    householdId,
    preparednessAdvice = null,
  ) =>
    requestPdf(
      `/households/${encodeURIComponent(householdId)}/preparedness-plan.pdf`,
      preparednessAdvice
        ? {
            method: 'POST',
            body: JSON.stringify({
              preparedness_advice: preparednessAdvice,
            }),
          }
        : undefined,
    ),

  saveHouseholdPlan: (
    householdId,
    plan,
  ) =>
    request(
      `/households/${encodeURIComponent(householdId)}/plan`,
      {
        method: 'PUT',
        body: JSON.stringify(plan),
      },
    ),

  getCompletion: (householdId) =>
    request(
      `/households/${encodeURIComponent(householdId)}/completion`,
    ),

  saveLocation: (
    householdId,
    input,
  ) =>
    request(
      `/households/${encodeURIComponent(householdId)}/location`,
      {
        method: 'PUT',
        body: JSON.stringify(input),
      },
    ),

  saveDeviceLocation: (
    householdId,
    input,
  ) =>
    request(
      `/households/${encodeURIComponent(householdId)}/location/device`,
      {
        method: 'PUT',
        body: JSON.stringify(input),
      },
    ),

  getLocation: (householdId) =>
    request(
      `/households/${encodeURIComponent(householdId)}/location`,
    ),

  getAddressSuggestions: (
    query,
    signal,
  ) =>
    request(
      `/locations/suggestions?q=${encodeURIComponent(query)}`,
      {
        signal,
      },
    ),

  getNearbyAddresses: (
    latitude,
    longitude,
  ) =>
    request(
      '/locations/nearby-addresses',
      {
        method: 'POST',
        body: JSON.stringify({
          latitude,
          longitude,
        }),
      },
    ),

  getLocalContext: (householdId) =>
    request(
      `/households/${encodeURIComponent(householdId)}/local-context`,
    ),

  getPreparationSupport: (householdId) =>
    request(
      `/households/${encodeURIComponent(householdId)}/preparation-support`,
    ),

  getHistoricalFirePoints: (
    householdId,
    limit = 500,
  ) =>
    request(
      `/households/${encodeURIComponent(householdId)}/historical-fire-points?limit=${limit}`,
    ),

  getBasicScenarios: (householdId) =>
    request(
      `/scenarios/basic?household_id=${encodeURIComponent(householdId)}`,
    ),

  runBasicTest: (
    householdId,
    scenarioId,
  ) =>
    request(
      `/households/${encodeURIComponent(householdId)}/tests`,
      {
        method: 'POST',
        body: JSON.stringify({
          scenario_id: scenarioId,
        }),
      },
    ),

  simulateRendezvous: (householdId) =>
    request(
      `/households/${encodeURIComponent(householdId)}/rendezvous-simulation`,
      {
        method: 'POST',
      },
    ),

  getTravelRoutes: (householdId) =>
    request(`/households/${encodeURIComponent(householdId)}/travel-routes`),

  getTravelDisruptions: (
    householdId,
    radiusKm = 10,
  ) =>
    request(
      `/households/${encodeURIComponent(householdId)}/travel-disruptions?radius_km=${radiusKm}`,
    ),

  explainRendezvous: (
    householdId,
    result,
  ) =>
    request(
      `/households/${encodeURIComponent(householdId)}/rendezvous-explanation`,
      {
        method: 'POST',
        body: JSON.stringify(result),
      },
    ),

  getTestResult: (
    householdId,
    testRunId,
  ) =>
    request(
      `/households/${encodeURIComponent(householdId)}/tests/${encodeURIComponent(testRunId)}`,
    ),
}

export function newId(prefix) {
  return `${prefix}_${crypto.randomUUID().replaceAll('-', '')}`
}
import { routeKilometres, routeMinutes } from '../utils/travelRouteFormat.js'

// Sentences the assistant is asked to say. Each is built by code from a fixed
// template and store values, so a model never composes a figure. Distances use one
// decimal, the same as the fire map shows, so what is said matches what is on screen.
// Nothing here estimates, rounds a count, or words anything as a prediction.

export const NEEDS_VERIFIED_ADDRESS =
  'I need a verified household address before I can read that. You can add one on the overview page.'
export const WEATHER_UNAVAILABLE = 'Current weather is not available right now.'
export const FIRE_DANGER_UNAVAILABLE =
  'Current fire danger information is not available from the official source.'
export const FIRE_HISTORY_UNAVAILABLE = 'Fire history is not available right now.'
export const COMPLETION_UNAVAILABLE = 'Your plan could not be read right now.'
export const NO_SAVED_PLAN = 'You have not saved a plan yet.'
export const DISRUPTIONS_UNAVAILABLE = 'Road disruption information is not available right now.'
export const NO_VERIFIED_DESTINATION =
  'I need a verified evacuation destination before I can check road disruptions.'

export const FDR_PATTERN_NONE =
  'No historical fire danger pattern has been generated yet. Choose a fire district and a date on the page, then press the button.'
export const FDR_PATTERN_UNAVAILABLE = 'The historical fire danger pattern could not be generated.'
export const ROUTES_UNAVAILABLE = 'Road routes are not available right now.'
export const ROUTES_NEED_DESTINATION =
  'I need a verified home address and a verified evacuation destination before I can show road routes.'
export const SIMULATION_NOT_RUN = 'The meet-up simulation has not been run yet. You can ask me to run it.'
export const SIMULATION_UNAVAILABLE = 'The meet-up simulation is not available right now.'

const FDR_FALLBACK_NOTICE = 'This is based on historical patterns. It is not an official Fire Danger Rating forecast.'
const SECTION_LABELS = {
  household_profile: 'Household profile',
  member_locations: 'Member locations',
  transport: 'Transport',
  backup_transport: 'Backup transport',
  primary_destination: 'Primary destination',
  backup_destination: 'Backup destination',
  responsibilities: 'Responsibilities',
}
const ORIGIN_LABELS = { home: 'home', work: 'work', school: 'school', other: 'elsewhere' }

const km = (value) => Number(value).toFixed(1)
const needsAddress = (status) => status === 'unverified' || status === 'idle'
const minutesText = (minutes) => `${minutes} ${minutes === 1 ? 'minute' : 'minutes'}`

export function weatherReadout({ status, weather }) {
  if (needsAddress(status)) return NEEDS_VERIFIED_ADDRESS
  if (status !== 'success' || !weather) return WEATHER_UNAVAILABLE
  return `The temperature is ${weather.temperature_c} degrees Celsius, humidity is ${weather.relative_humidity} percent, and wind is ${weather.wind_speed_kmh} kilometres per hour from the ${weather.wind_direction}, observed at ${weather.station_name}.`
}

// One figure at a time: the same gate and wording as the combined weather read-out.
function singleWeatherFigure({ status, weather }, say) {
  if (needsAddress(status)) return NEEDS_VERIFIED_ADDRESS
  if (status !== 'success' || !weather) return WEATHER_UNAVAILABLE
  return say(weather)
}

export const temperatureReadout = (state) =>
  singleWeatherFigure(state, (weather) => `The temperature is ${weather.temperature_c} degrees Celsius.`)
export const humidityReadout = (state) =>
  singleWeatherFigure(state, (weather) => `The humidity is ${weather.relative_humidity} percent.`)
export const windReadout = (state) =>
  singleWeatherFigure(
    state,
    (weather) => `The wind is ${weather.wind_speed_kmh} kilometres per hour from the ${weather.wind_direction}.`,
  )

export function fireDangerReadout({ status, fireDanger }) {
  if (needsAddress(status)) return NEEDS_VERIFIED_ADDRESS
  if (status !== 'success' || fireDanger?.availability !== 'available') return FIRE_DANGER_UNAVAILABLE
  return `Today's fire danger rating is ${fireDanger.today}, from the official source.`
}

export function planCompletionReadout({ status, completion }) {
  if (status === 'error') return COMPLETION_UNAVAILABLE
  if (!completion) return NO_SAVED_PLAN
  if (completion.overall_status === 'complete') return 'Your plan is complete.'
  const sections = completion.sections ?? []
  const done = sections.filter((section) => section.status === 'complete').length
  // The same words as the progress bar on My Plan.
  return `Your plan has ${done} of ${sections.length} sections complete.`
}

export function fireHistoryReadout({ status, totalCount, searchRadiusKm, mostRecentFire, nearestFire }) {
  if (status === 'unverified') return NEEDS_VERIFIED_ADDRESS
  if (status !== 'success') return FIRE_HISTORY_UNAVAILABLE
  const radius = km(searchRadiusKm)
  if (totalCount === 0) return `There are no recorded fires within ${radius} kilometres of your address.`
  const parts = [
    `${totalCount === 1 ? 'There is 1 recorded fire' : `There are ${totalCount} recorded fires`} within ${radius} kilometres of your address.`,
  ]
  if (mostRecentFire?.season != null) {
    parts.push(`The most recent is from the ${mostRecentFire.season} season.`)
  }
  if (nearestFire) parts.push(`The nearest was ${km(nearestFire.distance_km)} kilometres away.`)
  parts.push('This is historical context, not a forecast.')
  return parts.join(' ')
}

export function travelDisruptionsReadout({ status, result }) {
  if (status !== 'success' || !result) return DISRUPTIONS_UNAVAILABLE
  if (result.status === 'not_applicable') return NO_VERIFIED_DESTINATION
  if (result.status !== 'available') return DISRUPTIONS_UNAVAILABLE

  const primary = result.primary_destination
  const backups = result.backup_destinations ?? []
  const clauses = []
  if (primary) clauses.push(`${primary.active_disruption_count} near your primary destination`)
  if (backups.length) {
    const total = backups.reduce((sum, backup) => sum + (backup.active_disruption_count ?? 0), 0)
    clauses.push(`${total} near your backup destinations`)
  }
  if (!clauses.length) return NO_VERIFIED_DESTINATION

  const radius = primary?.search_radius_km ?? backups[0]?.search_radius_km
  const within = radius == null ? '' : ` within ${km(radius)} kilometres`
  return `Reported road disruptions${within}: ${clauses.join(' and ')}. This does not mean your route is blocked or safe.`
}

// The panel on Safety Insights: a historical pattern for a district and a date, not a forecast.
// Voice only reads a result that is already on screen; it never runs the panel.
export function fireDangerPatternReadout({ status, result }) {
  if (status === 'loading') return 'The historical fire danger pattern is still being generated.'
  if (status === 'error') return FDR_PATTERN_UNAVAILABLE
  if (status !== 'success' || !result) return FDR_PATTERN_NONE
  const probability =
    typeof result.elevated_probability === 'number'
      ? ` The estimated probability of an elevated rating is ${(result.elevated_probability * 100).toFixed(1)} percent.`
      : ''
  return `For ${result.district} on ${result.date}, the historical pattern is ${result.prediction_label}.${probability} ${result.disclaimer || FDR_FALLBACK_NOTICE}`
}

// Road distance and driving time per saved destination, by name (never the street address),
// exactly as the routing service returned them. It says nothing about whether a road is safe.
export function travelRoutesReadout({ status, result }) {
  if (status === 'idle' || status === 'loading') return 'Road routes are still loading.'
  if (result?.status === 'not_applicable') return ROUTES_NEED_DESTINATION
  if (!result) return ROUTES_UNAVAILABLE
  const routes = result.routes ?? []
  if (!routes.length) return status === 'unavailable' ? ROUTES_UNAVAILABLE : ROUTES_NEED_DESTINATION

  const sentences = routes.map((route) => {
    const label = route.destination_type === 'primary' ? 'Your primary destination' : 'A backup destination'
    const known = route.status === 'available' && route.distance_m != null && route.travel_time_seconds != null
    if (!known) return `${label}, ${route.destination_name}: no road route is available.`
    return `${label}, ${route.destination_name}: ${routeKilometres(route.distance_m)} kilometres, about ${minutesText(routeMinutes(route.travel_time_seconds))} by road.`
  })
  return `${sentences.join(' ')} These are road distances and driving times only; they do not say whether a route is safe.`
}

// The meet-up simulation on Test My Plan: the headline, then each person by name, then the
// warnings, the same as the panel. The AI-written summary beside it is deliberately not read.
export function simulationReadout({ status, result }) {
  if (status === 'loading') return 'The meet-up simulation is still running.'
  if (status === 'error') return SIMULATION_UNAVAILABLE
  if (!result) return SIMULATION_NOT_RUN
  if (result.status === 'not_applicable') {
    const missing = (result.missing_sections ?? []).map((section) => SECTION_LABELS[section] ?? section)
    return missing.length
      ? `The simulation needs more of your plan first: ${missing.join(', ')}.`
      : 'The simulation cannot run yet because your plan is not complete enough.'
  }
  if (result.status !== 'ready') return SIMULATION_UNAVAILABLE

  const minutes = (seconds) => minutesText(Math.round(seconds / 60))
  const people = (result.member_etas ?? []).map(
    (eta) =>
      `${eta.display_name || 'An unnamed member'}, from ${ORIGIN_LABELS[eta.origin_kind] ?? eta.origin_kind}, ${minutes(eta.travel_seconds)}.`,
  )
  const warnings = (result.warnings ?? []).map((warning) => `Warning: ${warning}`)
  return [
    `Everyone is together after ${minutes(result.everyone_together_seconds)} at ${result.destination_name}.`,
    ...people,
    ...warnings,
  ].join(' ')
}

// The sentences that say "I can't give you that". The koala looks sorry when it speaks one.
// Dynamic wording is matched by its fixed opening.
const SHORTFALLS = new Set([
  NEEDS_VERIFIED_ADDRESS,
  WEATHER_UNAVAILABLE,
  FIRE_DANGER_UNAVAILABLE,
  FIRE_HISTORY_UNAVAILABLE,
  COMPLETION_UNAVAILABLE,
  NO_SAVED_PLAN,
  DISRUPTIONS_UNAVAILABLE,
  NO_VERIFIED_DESTINATION,
  FDR_PATTERN_NONE,
  FDR_PATTERN_UNAVAILABLE,
  ROUTES_UNAVAILABLE,
  ROUTES_NEED_DESTINATION,
  SIMULATION_NOT_RUN,
  SIMULATION_UNAVAILABLE,
])
const SHORTFALL_OPENINGS = [
  'The simulation needs more of your plan first',
  'The simulation cannot run yet',
  'Road routes are still loading',
  'The historical fire danger pattern is still being generated',
  'The meet-up simulation is still running',
]

export function isShortfall(text) {
  if (typeof text !== 'string' || !text) return false
  return SHORTFALLS.has(text) || SHORTFALL_OPENINGS.some((opening) => text.startsWith(opening))
}

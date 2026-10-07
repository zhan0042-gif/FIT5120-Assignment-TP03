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

const km = (value) => Number(value).toFixed(1)
const needsAddress = (status) => status === 'unverified' || status === 'idle'

export function weatherReadout({ status, weather }) {
  if (needsAddress(status)) return NEEDS_VERIFIED_ADDRESS
  if (status !== 'success' || !weather) return WEATHER_UNAVAILABLE
  return `The temperature is ${weather.temperature_c} degrees Celsius, humidity is ${weather.relative_humidity} percent, and wind is ${weather.wind_speed_kmh} kilometres per hour from the ${weather.wind_direction}, observed at ${weather.station_name}.`
}

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
  const needing = sections.filter((section) => section.status === 'needs_information').length
  return `Your plan still needs information in ${needing} of ${sections.length} sections.`
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

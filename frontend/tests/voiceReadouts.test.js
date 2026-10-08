import assert from 'node:assert/strict'
import { test } from 'node:test'

const {
  COMPLETION_UNAVAILABLE,
  DISRUPTIONS_UNAVAILABLE,
  FIRE_DANGER_UNAVAILABLE,
  FIRE_HISTORY_UNAVAILABLE,
  NEEDS_VERIFIED_ADDRESS,
  NO_SAVED_PLAN,
  NO_VERIFIED_DESTINATION,
  WEATHER_UNAVAILABLE,
  fireDangerReadout,
  fireHistoryReadout,
  planCompletionReadout,
  travelDisruptionsReadout,
  weatherReadout,
} = await import('../src/voice/readouts.js')

const WEATHER = {
  temperature_c: 21.5,
  relative_humidity: 40,
  wind_speed_kmh: 18,
  wind_direction: 'NW',
  observed_at: '2026-10-08T01:00:00Z',
  station_name: 'Melbourne Airport',
}

test('weather is read from the template with the values unchanged', () => {
  assert.equal(
    weatherReadout({ status: 'success', weather: WEATHER }),
    'The temperature is 21.5 degrees Celsius, humidity is 40 percent, and wind is 18 kilometres per hour from the NW, observed at Melbourne Airport.',
  )
})

test('weather says what is missing instead of guessing', () => {
  assert.equal(weatherReadout({ status: 'unverified', weather: null }), NEEDS_VERIFIED_ADDRESS)
  assert.equal(weatherReadout({ status: 'idle', weather: null }), NEEDS_VERIFIED_ADDRESS)
  assert.equal(weatherReadout({ status: 'error', weather: null }), WEATHER_UNAVAILABLE)
  assert.equal(weatherReadout({ status: 'success', weather: null }), WEATHER_UNAVAILABLE)
})

test('fire danger reads today only and cites the official source', () => {
  const fireDanger = { availability: 'available', today: 'Extreme', tomorrow: 'High' }

  assert.equal(
    fireDangerReadout({ status: 'success', fireDanger }),
    "Today's fire danger rating is Extreme, from the official source.",
  )
})

test('fire danger says so when the official source has nothing', () => {
  const fireDanger = { availability: 'unavailable', message: 'x' }

  assert.equal(fireDangerReadout({ status: 'success', fireDanger }), FIRE_DANGER_UNAVAILABLE)
  assert.equal(fireDangerReadout({ status: 'error', fireDanger: null }), FIRE_DANGER_UNAVAILABLE)
  assert.equal(fireDangerReadout({ status: 'unverified', fireDanger: null }), NEEDS_VERIFIED_ADDRESS)
})

test('plan completion says how many sections are complete, as the progress bar does', () => {
  const completion = {
    overall_status: 'needs_information',
    sections: [
      { section: 'members', status: 'complete' },
      { section: 'animals', status: 'needs_information' },
      { section: 'transport', status: 'needs_information' },
    ],
  }

  assert.equal(
    planCompletionReadout({ status: 'success', completion }),
    'Your plan has 1 of 3 sections complete.',
  )
})

test('a complete plan, a missing plan and a failed load are told apart', () => {
  assert.equal(
    planCompletionReadout({ status: 'success', completion: { overall_status: 'complete', sections: [] } }),
    'Your plan is complete.',
  )
  assert.equal(planCompletionReadout({ status: 'idle', completion: null }), NO_SAVED_PLAN)
  assert.equal(planCompletionReadout({ status: 'error', completion: null }), COMPLETION_UNAVAILABLE)
})

test('fire history reads the counts and says it is not a forecast', () => {
  assert.equal(
    fireHistoryReadout({
      status: 'success',
      totalCount: 12,
      searchRadiusKm: 10,
      mostRecentFire: { season: 2019 },
      nearestFire: { distance_km: 3.456 },
    }),
    'There are 12 recorded fires within 10.0 kilometres of your address. The most recent is from the 2019 season. The nearest was 3.5 kilometres away. This is historical context, not a forecast.',
  )
})

test('fire history handles one fire, none, and missing details', () => {
  assert.equal(
    fireHistoryReadout({ status: 'success', totalCount: 1, searchRadiusKm: 5, mostRecentFire: { season: null }, nearestFire: null }),
    'There is 1 recorded fire within 5.0 kilometres of your address. This is historical context, not a forecast.',
  )
  assert.equal(
    fireHistoryReadout({ status: 'success', totalCount: 0, searchRadiusKm: 5, mostRecentFire: null, nearestFire: null }),
    'There are no recorded fires within 5.0 kilometres of your address.',
  )
})

test('fire history says what is missing instead of guessing', () => {
  assert.equal(fireHistoryReadout({ status: 'unverified' }), NEEDS_VERIFIED_ADDRESS)
  assert.equal(fireHistoryReadout({ status: 'unavailable' }), FIRE_HISTORY_UNAVAILABLE)
  assert.equal(fireHistoryReadout({ status: 'error' }), FIRE_HISTORY_UNAVAILABLE)
})

test('road disruptions are counted per destination and never called safe or blocked', () => {
  const result = {
    status: 'available',
    primary_destination: { search_radius_km: 10, active_disruption_count: 2 },
    backup_destinations: [
      { search_radius_km: 10, active_disruption_count: 1 },
      { search_radius_km: 10, active_disruption_count: 0 },
    ],
  }

  assert.equal(
    travelDisruptionsReadout({ status: 'success', result }),
    'Reported road disruptions within 10.0 kilometres: 2 near your primary destination and 1 near your backup destinations. This does not mean your route is blocked or safe.',
  )
})

test('road disruptions only mention destinations that were checked', () => {
  const result = {
    status: 'available',
    primary_destination: null,
    backup_destinations: [{ search_radius_km: 10, active_disruption_count: 3 }],
  }

  assert.equal(
    travelDisruptionsReadout({ status: 'success', result }),
    'Reported road disruptions within 10.0 kilometres: 3 near your backup destinations. This does not mean your route is blocked or safe.',
  )
})

test('road disruptions say when there is no verified destination or no data', () => {
  assert.equal(
    travelDisruptionsReadout({ status: 'success', result: { status: 'not_applicable' } }),
    NO_VERIFIED_DESTINATION,
  )
  assert.equal(
    travelDisruptionsReadout({ status: 'success', result: { status: 'unavailable' } }),
    DISRUPTIONS_UNAVAILABLE,
  )
  assert.equal(travelDisruptionsReadout({ status: 'error', result: null }), DISRUPTIONS_UNAVAILABLE)
  assert.equal(
    travelDisruptionsReadout({
      status: 'success',
      result: { status: 'available', primary_destination: null, backup_destinations: [] },
    }),
    NO_VERIFIED_DESTINATION,
  )
})

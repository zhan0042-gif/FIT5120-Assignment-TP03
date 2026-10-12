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
  FDR_PATTERN_NONE,
  FDR_PATTERN_UNAVAILABLE,
  ROUTES_NEED_DESTINATION,
  ROUTES_UNAVAILABLE,
  SIMULATION_NOT_RUN,
  SIMULATION_UNAVAILABLE,
  fireDangerPatternReadout,
  humidityReadout,
  simulationReadout,
  temperatureReadout,
  travelRoutesReadout,
  windReadout,
  isShortfall,
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


test('each weather figure can be read on its own, exactly as the combined read-out says it', () => {
  assert.equal(temperatureReadout({ status: 'success', weather: WEATHER }), 'The temperature is 21.5 degrees Celsius.')
  assert.equal(humidityReadout({ status: 'success', weather: WEATHER }), 'The humidity is 40 percent.')
  assert.equal(
    windReadout({ status: 'success', weather: WEATHER }),
    'The wind is 18 kilometres per hour from the NW.',
  )
})

test('a single weather figure says what is missing instead of guessing', () => {
  for (const readout of [temperatureReadout, humidityReadout, windReadout]) {
    assert.equal(readout({ status: 'unverified', weather: null }), NEEDS_VERIFIED_ADDRESS)
    assert.equal(readout({ status: 'error', weather: null }), WEATHER_UNAVAILABLE)
    assert.equal(readout({ status: 'success', weather: null }), WEATHER_UNAVAILABLE)
  }
})

const PATTERN = {
  district: 'Central',
  date: '2026-01-15',
  prediction_label: 'Elevated',
  elevated_probability: 0.8123,
  disclaimer: 'This is a machine-learning estimate. It is not an official Fire Danger Rating forecast.',
}

test('the fire danger pattern is read as a historical pattern, with its probability and its own warning', () => {
  assert.equal(
    fireDangerPatternReadout({ status: 'success', result: PATTERN }),
    'For Central on 2026-01-15, the historical pattern is Elevated. The estimated probability of an elevated rating is 81.2 percent. This is a machine-learning estimate. It is not an official Fire Danger Rating forecast.',
  )
})

test('the fire danger pattern still reads without a probability, and always carries a warning', () => {
  const text = fireDangerPatternReadout({
    status: 'success',
    result: { ...PATTERN, elevated_probability: null, disclaimer: undefined },
  })

  assert.doesNotMatch(text, /probability/)
  assert.match(text, /not an official Fire Danger Rating forecast/)
})

test('the fire danger pattern says when nothing has been generated, and never runs it', () => {
  assert.equal(fireDangerPatternReadout({ status: 'idle', result: null }), FDR_PATTERN_NONE)
  assert.match(FDR_PATTERN_NONE, /Choose a fire district and a date/)
  assert.equal(fireDangerPatternReadout({ status: 'error', result: null }), FDR_PATTERN_UNAVAILABLE)
  assert.match(fireDangerPatternReadout({ status: 'loading', result: null }), /still being generated/)
})

const ROUTES = {
  status: 'available',
  routes: [
    { status: 'available', destination_type: 'primary', destination_id: 'd1', destination_name: "Relative's House", distance_m: 22_400, travel_time_seconds: 1_860 },
    { status: 'available', destination_type: 'backup', destination_id: 'd2', destination_name: 'Community Centre', distance_m: 9_000, travel_time_seconds: 600 },
  ],
}

test('road routes are read per destination by name, with distance and driving time only', () => {
  assert.equal(
    travelRoutesReadout({ status: 'available', result: ROUTES }),
    "Your primary destination, Relative's House: 22.4 kilometres, about 31 minutes by road. A backup destination, Community Centre: 9.0 kilometres, about 10 minutes by road. These are road distances and driving times only; they do not say whether a route is safe.",
  )
})

test('a destination without a route is reported as having none, not skipped or guessed', () => {
  const partial = {
    status: 'partial',
    routes: [
      ROUTES.routes[0],
      { status: 'unavailable', destination_type: 'backup', destination_id: 'd2', destination_name: 'Community Centre', distance_m: null, travel_time_seconds: null },
    ],
  }

  const text = travelRoutesReadout({ status: 'partial', result: partial })

  assert.match(text, /Community Centre: no road route is available\./)
  assert.match(text, /22\.4 kilometres/)
})

test('road routes say what is missing instead of guessing', () => {
  assert.equal(travelRoutesReadout({ status: 'unavailable', result: null }), ROUTES_UNAVAILABLE)
  assert.equal(
    travelRoutesReadout({ status: 'unavailable', result: { status: 'not_applicable', routes: [] } }),
    ROUTES_NEED_DESTINATION,
  )
  assert.equal(travelRoutesReadout({ status: 'available', result: { status: 'available', routes: [] } }), ROUTES_NEED_DESTINATION)
  assert.match(travelRoutesReadout({ status: 'loading', result: null }), /still loading/)
})

const READY = {
  status: 'ready',
  destination_name: "Relative's House",
  everyone_together_seconds: 2_820,
  member_etas: [
    { member_id: 'm1', display_name: 'Maya', origin_kind: 'home', travel_seconds: 720 },
    { member_id: 'm2', display_name: '', origin_kind: 'work', travel_seconds: 2_820 },
  ],
  warnings: ['Traffic is heavier than usual.'],
}

test('the simulation is read like the panel shows it: headline, each person by name, then warnings', () => {
  assert.equal(
    simulationReadout({ status: 'success', result: READY }),
    "Everyone is together after 47 minutes at Relative's House. Maya, from home, 12 minutes. An unnamed member, from work, 47 minutes. Warning: Traffic is heavier than usual.",
  )
})

test('the simulation does not read the AI summary or the explanation', () => {
  const text = simulationReadout({ status: 'success', result: { ...READY, explanation: 'Generated text' } })

  assert.doesNotMatch(text, /Generated text/)
})

test('the simulation says when it has not run, cannot run yet, or is unavailable', () => {
  assert.equal(simulationReadout({ status: 'idle', result: null }), SIMULATION_NOT_RUN)
  assert.equal(simulationReadout({ status: 'error', result: null }), SIMULATION_UNAVAILABLE)
  assert.equal(simulationReadout({ status: 'success', result: { status: 'unavailable' } }), SIMULATION_UNAVAILABLE)
  assert.match(simulationReadout({ status: 'loading', result: null }), /still running/)
  assert.equal(
    simulationReadout({ status: 'success', result: { status: 'not_applicable', missing_sections: ['transport', 'primary_destination'] } }),
    'The simulation needs more of your plan first: Transport, Primary destination.',
  )
  assert.match(simulationReadout({ status: 'success', result: { status: 'not_applicable', missing_sections: [] } }), /not complete enough/)
})

test('one minute is spoken in the singular', () => {
  const text = simulationReadout({
    status: 'success',
    result: { ...READY, everyone_together_seconds: 60, member_etas: [{ member_id: 'm1', display_name: 'Maya', origin_kind: 'home', travel_seconds: 60 }], warnings: [] },
  })

  assert.match(text, /after 1 minute at/)
  assert.match(text, /Maya, from home, 1 minute\./)
})


test('a sentence that says "I cannot tell you that" is recognised as a shortfall', () => {
  for (const text of [
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
    'The simulation needs more of your plan first: Transport.',
    'The simulation cannot run yet because your plan is not complete enough.',
    'Road routes are still loading.',
  ]) {
    assert.equal(isShortfall(text), true, text)
  }
})

test('a real answer is not a shortfall', () => {
  assert.equal(isShortfall('The temperature is 21.5 degrees Celsius.'), false)
  assert.equal(isShortfall("Today's fire danger rating is High, from the official source."), false)
  assert.equal(isShortfall('Your plan is complete.'), false)
  assert.equal(isShortfall(''), false)
  assert.equal(isShortfall(undefined), false)
})

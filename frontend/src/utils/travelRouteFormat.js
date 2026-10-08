// How a road route's distance and driving time are written, on screen and in speech, so the
// two always agree. One decimal for kilometres is what the fire map uses.

export const routeKilometres = (distanceMeters) => (distanceMeters / 1000).toFixed(1)

// Whole minutes, never zero: a trip that rounds to nothing still takes a minute.
export const routeMinutes = (travelSeconds) => Math.max(1, Math.round(travelSeconds / 60))

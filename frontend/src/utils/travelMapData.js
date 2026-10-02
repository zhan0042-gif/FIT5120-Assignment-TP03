import { travelDestinationGroups } from './travelReadinessPresentation.js'

export function hasMapCoordinates(item) {
  return Number.isFinite(item?.latitude) && Number.isFinite(item?.longitude)
    && Math.abs(item.latitude) <= 90 && Math.abs(item.longitude) <= 180
}

export function buildTravelMapData(result) {
  if (result?.status !== 'available') return { destinations: [], disruptions: [] }

  const groups = travelDestinationGroups(result)

  const destinations = groups.filter((destination) =>
    hasMapCoordinates(destination) && Number.isFinite(destination.search_radius_km)
      && destination.search_radius_km > 0,
  )

  const seen = new Set()
  const disruptions = []
  for (const destination of groups) {
    for (const disruption of destination.disruptions ?? []) {
      if (!hasMapCoordinates(disruption)) continue
      const key = `${disruption.disruption_id}:${disruption.latitude}:${disruption.longitude}`
      if (seen.has(key)) continue
      seen.add(key)
      disruptions.push(disruption)
    }
  }

  return { destinations, disruptions }
}

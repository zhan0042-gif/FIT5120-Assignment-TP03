import { travelDestinationGroups } from './travelReadinessPresentation.js'

export function hasMapCoordinates(item) {
  return Number.isFinite(item?.latitude) && Number.isFinite(item?.longitude)
    && Math.abs(item.latitude) <= 90 && Math.abs(item.longitude) <= 180
}

export function buildTravelMapData(result, plan = null) {

  const groups = travelDestinationGroups(result)

  // Saved verified destinations remain mappable when either optional provider
  // is unavailable. Their circles still describe the same 10 km search area.
  const saved = [
    plan?.arrangements?.primary_destination && { ...plan.arrangements.primary_destination, type: 'Primary destination' },
    ...(plan?.arrangements?.backup_arrangements ?? []).map((item) => item.destination && ({ ...item.destination, type: 'Backup destination' })),
  ].filter((item) => item && item.verification_status === 'verified' && hasMapCoordinates(item))
  for (const destination of saved) {
    if (!groups.some((item) => item.destination_id === destination.destination_id && item.type === destination.type)) {
      groups.push({ ...destination, destination_name: destination.display_name || destination.canonical_address || destination.address || 'Saved destination',
        destination_address: destination.canonical_address || destination.address, search_radius_km: 10, disruptions: [] })
    }
  }

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

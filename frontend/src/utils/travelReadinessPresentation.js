function cleanText(value) {
  return typeof value === 'string' ? value.trim() : ''
}

export function destinationAddress(destination) {
  const address = cleanText(destination?.destination_address ?? destination?.canonical_address ?? destination?.address)
  const name = cleanText(destination?.destination_name ?? destination?.display_name)
  const normalized = (value) => value.toLowerCase().replace(/[\s,]+/g, ' ').trim()
  return normalized(address) === normalized(name) ? '' : address
}

export function uncheckedDestinations(plan) {
  const arrangements = plan?.arrangements
  if (!arrangements) return []
  const candidates = [
    ['Primary destination', arrangements.primary_destination],
    ...(arrangements.backup_arrangements ?? []).map((arrangement) =>
      ['Backup destination', arrangement.destination]),
  ]
  return candidates.flatMap(([type, destination]) => {
    if (!destination) return []
    const verified = destination.verification_status === 'verified'
      && Number.isFinite(destination.latitude) && Number.isFinite(destination.longitude)
    if (verified) return []
    return [{
      type,
      destination_id: destination.destination_id,
      destination_name: cleanText(destination.display_name)
        || cleanText(destination.canonical_address)
        || cleanText(destination.address)
        || 'Saved destination',
      destination_address: destination.canonical_address || destination.address,
    }]
  })
}

function impactParts(value) {
  return cleanText(value).split(';').map((part) => part.trim()).filter(Boolean)
}

export function disruptionStatus(disruption) {
  const parts = impactParts(disruption?.impact)
  const directionPart = parts.find((part) => /^direction\s*:/i.test(part))
  const direction = cleanText(disruption?.direction)
    || directionPart?.replace(/^direction\s*:\s*/i, '').trim()
    || ''
  const impact = parts.filter((part) => !/^direction\s*:/i.test(part))
    .map((part) => part.replace(/^impactType\s*:\s*/i, '').trim())
    .filter(Boolean).join('; ')

  if (!impact) return direction ? `Reported direction: ${direction}` : ''
  if (!direction) return impact
  if (/^both directions$/i.test(direction)) return `${impact} in both directions`
  if (/^(north|south|east|west)bound$/i.test(direction)) {
    return `${impact} ${direction.toLowerCase()}`
  }
  return `${impact} (${direction})`
}

export function coreDisruptionDescription(value) {
  const description = cleanText(value)
  const contactStart = /\s+(?:Further details(?:\s+contact|:)|For (?:more|further) (?:information|details)(?:\s+contact|:)|Phone:|Email:|Contact:)/i.exec(description)
  if (!contactStart) return description
  const core = description.slice(0, contactStart.index).trim()
  return core && /[.!?]$/.test(core) ? core : description
}

function cleanText(value) {
  return typeof value === 'string' ? value.trim() : ''
}

const preservedAbbreviations = new Set([
  'VIC', 'NSW', 'QLD', 'SA', 'WA', 'TAS', 'NT', 'ACT',
  'CFA', 'SES', 'RFS', 'VICSES', 'PTV', 'CBD', 'BHP', 'ABC',
])

function isAllCaps(value) {
  return /[A-Z]/.test(value) && !/[a-z]/.test(value)
}

// Only recase fully uppercase fields; keep deliberate mixed casing, state
// abbreviations, single-letter address components and route numbers intact.
export function travelPlaceText(value) {
  const text = cleanText(value)
  if (!isAllCaps(text)) return text
  return text.replace(/[A-Z]+(?:['\u2019][A-Z]+)*\d*/g, (word) => {
    if (preservedAbbreviations.has(word) || word.length === 1 || /\d/.test(word)) return word
    return word.toLowerCase().replace(/\b[a-z]/g, (letter) => letter.toUpperCase())
  })
}

function travelSentenceText(value) {
  const text = cleanText(value)
  if (!isAllCaps(text)) return text
  return text.replace(/[A-Z]+\d*/g, (word) =>
    preservedAbbreviations.has(word) || /\d/.test(word) ? word : word.toLowerCase(),
  ).replace(/(^|[.!?]\s+)([a-z])/g, (_, prefix, letter) => prefix + letter.toUpperCase())
}

// Descriptions are prose, not titles. Preserve mixed-case prose while formatting
// known road references and sentence-casing fully uppercase descriptions.
export function disruptionDetails(disruption) {
  const core = coreDisruptionDescription(disruption?.description)
  let text = travelSentenceText(core)
  const road = cleanText(disruption?.road_name)
  if (road) {
    const escaped = road.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    text = text.replace(new RegExp(`\\b${escaped}\\b`, 'gi'), () => travelPlaceText(road))
  }
  return text
}

// Build popup content with textContent so user names and provider text remain
// plain text. Labels and values have separate semantic and visual roles.
export function travelLocationPopup(type, name, address, dom = document) {
  const content = dom.createElement('div')
  content.className = 'travel-popup'
  const heading = dom.createElement('div')
  const label = dom.createElement('strong')
  label.textContent = name ? `${type} - ` : type
  heading.append(label)
  if (name) {
    const value = dom.createElement('span')
    value.textContent = cleanText(name)
    heading.append(value)
  }
  content.append(heading)
  if (cleanText(address)) {
    const line = dom.createElement('div')
    line.className = 'travel-popup-address notranslate'
    line.translate = false
    line.textContent = travelPlaceText(address)
    content.append(line)
  }
  return content
}

export function travelDisruptionPopup(disruption, dom = document) {
  const content = travelLocationPopup('Reported road disruption', null, null, dom)
  const fields = [
    ['Road', travelPlaceText(disruption.road_name)],
    ['Type', travelPlaceText(disruption.event_subtype || disruption.event_type)],
    ['Distance from destination', Number.isFinite(disruption.distance_km) ? `${disruption.distance_km.toFixed(1)} km` : ''],
    ['Conditions', disruptionStatus(disruption)],
    ['Details', disruptionDetails(disruption)],
  ]
  for (const [label, value] of fields) {
    if (!value) continue
    const group = dom.createElement('div')
    group.className = 'travel-popup-field'
    const heading = dom.createElement('strong')
    heading.textContent = label
    const detail = dom.createElement('div')
    detail.textContent = value
    group.append(heading, detail)
    content.append(group)
  }
  return content
}

export function destinationAddress(destination) {
  const address = cleanText(destination?.destination_address ?? destination?.canonical_address ?? destination?.address)
  const name = cleanText(destination?.destination_name ?? destination?.display_name)
  const normalized = (value) => value.toLowerCase().replace(/[\s,]+/g, ' ').trim()
  return normalized(address) === normalized(name) ? '' : travelPlaceText(address)
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
    || directionPart?.replace(/^direction\s*:\s*/i, '').trim() || ''
  const impact = parts.filter((part) => !/^direction\s*:/i.test(part))
    .map((part) => part.replace(/^impactType\s*:\s*/i, '').trim())
    .filter(Boolean).join('; ')
  if (/^no blockage$/i.test(impact)) return 'No blockage reported. Proceed with caution.'
  const type = cleanText(disruption?.event_subtype || disruption?.event_type)
  const summary = travelSentenceText(coreDisruptionDescription(impact))
    || (/road damage/i.test(type) ? 'Road damage' : '')
  if (!summary) return direction ? `Conditions reported ${direction.toLowerCase()}.` : ''
  const wording = /^(changed conditions|road damage)$/i.test(summary)
    ? `${summary} reported` : summary.replace(/[.!?]+$/, '')
  if (!direction) return `${wording}.`
  if (/^both directions$/i.test(direction)) return `${wording} in both directions.`
  if (/^(north|south|east|west)bound$/i.test(direction)) return `${wording} ${direction.toLowerCase()}.`
  return `${wording} (${travelPlaceText(direction)}).`
}

export function coreDisruptionDescription(value) {
  const description = cleanText(value)
  const contactStart = /\b(?:Further details\b|For (?:more|further) (?:information|details)\b|(?:Phone|Telephone|Tel|Email|E-mail|Contact(?:\s+organisation)?)\s*:|Contact\s+(?:organisation\b|[A-Z])|[\w.+-]+@[\w.-]+\.[a-z]{2,}|(?:\+61\s*|\(?0[2-478]\)?\s*)\d[\d ()-]{6,}\d|(?:1300|1800)[\d -]{6,})/i.exec(description)
  return (contactStart ? description.slice(0, contactStart.index) : description).trim()
}

function normalizedKeyText(value) {
  return cleanText(value).toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim()
}

// Preserve distinct incidents on the same road using core wording, exact
// coordinates and direction. Sparse records fall back to the provider ID.
export function dedupeDestinationDisruptions(disruptions = [], destinationContext = '') {
  const latest = new Map()
  for (const [index, disruption] of disruptions.entries()) {
    const road = normalizedKeyText(disruption.road_name)
    const type = [disruption.event_type, disruption.event_subtype].map(normalizedKeyText)
    const description = normalizedKeyText(coreDisruptionDescription(disruption.description))
    const located = Number.isFinite(disruption.latitude) && Number.isFinite(disruption.longitude)
    const identity = road && type.some(Boolean) && (description || located)
      ? [road, ...type, description, located ? [disruption.latitude, disruption.longitude] : null,
        normalizedKeyText(disruption.direction)
          || normalizedKeyText(impactParts(disruption.impact).find((part) => /^direction\s*:/i.test(part))?.replace(/^direction\s*:\s*/i, ''))]
      : ['id', disruption.disruption_id ?? index]
    const key = JSON.stringify([destinationContext, identity])
    const timestamp = Date.parse(disruption.last_updated)
    const updated = Number.isFinite(timestamp) ? timestamp : -Infinity
    if (!latest.has(key) || updated > latest.get(key).updated) latest.set(key, { disruption, updated })
  }
  return [...latest.values()].sort((a, b) => b.updated - a.updated).map(({ disruption }) => disruption)
}

export function travelDestinationGroups(result) {
  if (result?.status !== 'available') return []
  const groups = [
    result.primary_destination && { ...result.primary_destination, type: 'Primary destination' },
    ...(result.backup_destinations ?? []).map((destination) => ({ ...destination, type: 'Backup destination' })),
  ].filter(Boolean)
  return groups.map((destination, index) => {
    const disruptions = dedupeDestinationDisruptions(destination.disruptions, `${destination.type}:${destination.destination_id ?? index}`)
    return { ...destination, disruptions, active_disruption_count: disruptions.length }
  })
}

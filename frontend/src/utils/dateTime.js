const australianDateTime = new Intl.DateTimeFormat('en-AU', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
  timeZone: 'Australia/Melbourne',
})

export function formatAustralianDateTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value || 'Time unavailable'
  return australianDateTime.format(date)
}

const australianDate = new Intl.DateTimeFormat('en-AU', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  timeZone: 'UTC',
})

export function formatAustralianDate(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value || 'Date unavailable'
  return australianDate.format(date)
}

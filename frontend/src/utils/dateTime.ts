const australianDateTime = new Intl.DateTimeFormat('en-AU', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
  timeZone: 'Australia/Melbourne',
})

export function formatAustralianDateTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value || 'Time unavailable'
  return australianDateTime.format(date)
}

// A card's date records when someone checked it against its source page. It is
// never refreshed automatically: the date only means something if a person set it.
// This only tells the reader when that check has become old.
export const STALE_AFTER_MONTHS = 6

function parseIsoDate(isoDate) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate ?? '')
  if (!match) return null
  const [year, month, day] = match.slice(1).map(Number)
  const date = new Date(year, month - 1, day)
  // Reject dates the Date constructor silently rolls over (for example 2026-02-31).
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) return null
  return { year, month: month - 1, day }
}

// Calendar months, clamped to the last day of the target month (31 Aug + 6 months
// is 28 Feb, not 3 Mar).
function addMonths({ year, month, day }, months) {
  const target = new Date(year, month + months, 1)
  const lastDay = new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate()
  return new Date(target.getFullYear(), target.getMonth(), Math.min(day, lastDay))
}

export function isStale(isoDate, now = new Date()) {
  const checked = parseIsoDate(isoDate)
  // An unreadable date cannot show the card was checked, so it is not treated as fresh.
  if (!checked) return true
  const staleAfter = addMonths(checked, STALE_AFTER_MONTHS)
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  return today > staleAfter
}

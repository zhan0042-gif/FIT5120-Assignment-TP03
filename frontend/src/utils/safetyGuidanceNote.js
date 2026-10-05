// Why bushfire-prone-area guidance may be missing. The backend reports only that
// location conditions were not applied, so the panel decides what to tell the user
// from whether the household already has a usable location.
export function locationNote({ applied, locationVerified }) {
  if (applied) return null
  return locationVerified ? 'unavailable' : 'verify'
}

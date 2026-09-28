import { VoiceActionError } from './targets.js'

export function describeAction({ kind, target, value }) {
  switch (kind) {
    case 'select':
      return `Set ${target.label} to ${value}`
    case 'text':
      return `Fill in ${target.label} with “${value}”`
    case 'checkbox':
      return `${value ? 'Tick' : 'Untick'} ${target.label}`
    case 'button':
      return `Press ${target.label}`
    case 'page':
      return `Go to ${target.label}`
    case 'address':
      return `Enter “${value}” for ${target.label}`
    default:
      return target.label.charAt(0).toUpperCase() + target.label.slice(1)
  }
}

// Acts only on a target that is on the page right now, looked up by id: the user
// may have moved on, or renamed the row, while the judge was answering.
export async function executeAction(action, liveTargets) {
  const target = liveTargets.find((item) => item.id === action.target.id)
  if (!target) return { ok: false, message: 'That’s no longer on this page.' }
  if (target.disabled) return { ok: false, message: 'That isn’t available right now.' }
  if (target.kind === 'select' && !target.options.includes(action.value)) {
    return { ok: false, message: 'That option isn’t available.' }
  }
  try {
    await target.run(action.value)
  } catch (error) {
    return {
      ok: false,
      message: error instanceof VoiceActionError ? error.message : 'That could not be done.',
    }
  }
  return { ok: true, message: `✓ ${describeAction({ ...action, target })}` }
}

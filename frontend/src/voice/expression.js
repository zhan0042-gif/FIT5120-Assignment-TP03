// Which face the koala wears. A pure function of what the voice store knows; no browser
// APIs, so every rule below is unit tested. The koala only shows state: nothing here, and
// nothing in the model's reading of the speaker, changes what the app does.

export const FACES = ['neutral', 'listening', 'thinking', 'happy', 'concerned', 'serious', 'sorry']
export const EMOTIONS = ['calm', 'worried', 'urgent', 'frustrated', 'playful']

const REACTION = { worried: 'concerned', urgent: 'serious', frustrated: 'sorry', playful: 'happy' }

// Opening a page, scrolling and jumping to a part of a page are the only requests the koala
// smiles at. It never smiles at weather, fire, travel, simulation, plan or safety answers.
const CHEERFUL = new Set([
  'open_overview',
  'open_safety_insights',
  'open_plan',
  'open_fire_map',
  'open_scenarios',
  'open_travel_readiness',
  'open_home',
  'go_back',
  'scroll_down',
  'scroll_up',
  'scroll_to_top',
  'scroll_to_bottom',
])

export const isCheerfulAction = (action) =>
  typeof action === 'string' && (CHEERFUL.has(action) || action.startsWith('section_'))

// The face for how the speaker sounds, or null for none. `playful` is only honoured where a
// smile is fitting, so a joking tone on a safety question cannot make the koala smile.
export function reactionFace(emotion, action) {
  if (emotion === 'playful' && !isCheerfulAction(action)) return null
  return REACTION[emotion] ?? null
}

// How a finished request should leave the koala: sorry if it could not help, happy only for
// a cheerful action, otherwise unchanged.
export function outcomeFor({ action, failed }) {
  if (failed) return 'sorry'
  return isCheerfulAction(action) ? 'happy' : null
}

export function conversationFace(status) {
  if (status === 'connecting' || status === 'checking') return 'thinking'
  if (status === 'listening') return 'listening'
  if (status === 'error') return 'sorry'
  return 'neutral'
}

// Highest priority first: an emergency, a request that could not be helped, the speaker's
// feeling, a cheerful outcome, then the state of the conversation.
export function resolveFace({ status, emergencyPinned, outcome, reaction }) {
  if (emergencyPinned) return 'serious'
  if (outcome === 'sorry') return 'sorry'
  if (reaction) return reaction
  if (outcome === 'happy') return 'happy'
  return conversationFace(status)
}

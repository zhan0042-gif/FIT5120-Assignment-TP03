// Fixed text. It lives here, not in the content file, so an unreviewed or invalid
// content file can never hide the emergency notice. Check the wording against an
// official source when this changes.
export const SAFETY_NOTICE = 'This is not for emergencies. If you are in danger, call 000.'

export const EMPTY_MESSAGE = 'No guidance is available to show right now.'

// The backend rejects a question longer than this; keep the two in step.
export const MAX_QUESTION_LENGTH = 300

// Fixed replies to a typed question. A model never writes these.
export const NO_MATCH_MESSAGE =
  "I don't have a reviewed answer for that. I can't predict what a fire will do or decide for you when to leave. Try one of the suggested questions."
export const EMERGENCY_MESSAGE = 'If you are in danger, call 000 now. This tool cannot help in an emergency.'
export const UNAVAILABLE_MESSAGE =
  'Typing a question is not available right now. Please choose one of the suggested questions.'

// Shown beside the typed question box: the text leaves the site, so say so.
export const PRIVACY_NOTE =
  'Typed questions are sent to an AI service to find a matching reviewed answer. Please do not include names or addresses.'

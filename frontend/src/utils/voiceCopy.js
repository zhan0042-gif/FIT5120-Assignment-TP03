// Fixed text for the voice assistant. It lives here, not in a model prompt, so the
// wording a person hears for "I could not do that" never depends on a model.

// Spoken when the action service fails, is rate limited, or a handler throws.
export const VOICE_UNAVAILABLE = "I couldn't do that just now. The buttons on the page still work."

// Spoken when no action matched, the request was too unclear, or nothing was heard.
export const VOICE_NOT_UNDERSTOOD =
  "I couldn't tell what you'd like me to do. You can ask me to open a page, read the weather, the fire danger or the fire history, or ask a bushfire safety question."

export const VOICE_NOTHING_TO_REPEAT = 'There is nothing to repeat yet.'

// Shown beside the microphone button: the audio leaves the site, so say so.
export const VOICE_PRIVACY_NOTE =
  'Voice sends your microphone audio to OpenAI so it can understand and answer you. Please do not say names or addresses.'

// Shown when the assistant said a number that was not in what the app sent it.
export const VOICE_CHECK_FIGURES =
  'Please check the figures on screen. What was said aloud may differ from them.'

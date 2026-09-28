// Chrome's Web Speech API behind the small interface the voice store needs. Chrome
// sends the audio to Google's servers; see docs/security/privacy-requirements.md.

// Neither is a failure: silence, and our own stop().
const QUIET_ERRORS = new Set(['no-speech', 'aborted'])

function recognitionClass(scope) {
  return scope.SpeechRecognition ?? scope.webkitSpeechRecognition ?? null
}

export function speechRecognitionAvailable(scope = globalThis) {
  return recognitionClass(scope) !== null
}

export function createWebSpeechStt(scope = globalThis) {
  const Recognition = recognitionClass(scope)
  let recognition = null
  let wanted = false

  return {
    start({ onInterim, onFinal, onError }) {
      wanted = true
      recognition = new Recognition()
      recognition.lang = 'en-AU'
      recognition.continuous = true
      recognition.interimResults = true

      recognition.onresult = (event) => {
        for (let index = event.resultIndex; index < event.results.length; index += 1) {
          const piece = event.results[index]
          const text = piece[0].transcript.trim()
          if (!text) continue
          if (piece.isFinal) onFinal(text)
          else onInterim(text)
        }
      }

      recognition.onerror = (event) => {
        if (QUIET_ERRORS.has(event.error)) return
        wanted = false
        onError(event.error)
      }

      // Chrome ends "continuous" recognition by itself after a pause; carry on
      // until the session is really over.
      recognition.onend = () => {
        if (!wanted) return
        try {
          recognition.start()
        } catch {
          wanted = false
          onError('restart-failed')
        }
      }

      recognition.start()
    },

    stop() {
      wanted = false
      recognition?.stop()
    },
  }
}

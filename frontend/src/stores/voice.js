import { defineStore } from 'pinia'
import { ref } from 'vue'
import { ApiError, api } from '../api/client.js'
import { MAX_QUESTION_LENGTH } from '../utils/safetyGuidanceCopy.js'
import { VOICE_CHECK_FIGURES, VOICE_NOT_UNDERSTOOD, VOICE_UNAVAILABLE } from '../utils/voiceCopy.js'
import { createHandlers, pageLabel } from '../voice/actions.js'
import { liveTransport } from '../voice/liveConnection.js'
import { unexpectedNumbers } from '../voice/numberCheck.js'
import { useFireMapStore } from './fireMap.js'
import { useHouseholdStore } from './household.js'
import { useLocalContextStore } from './localContext.js'
import { useSafetyGuidanceStore } from './safetyGuidance.js'
import { useTravelDisruptionsStore } from './travelDisruptions.js'

// GPT-Live has no maximum-duration or idle setting, so the browser ends the session.
export const IDLE_TIMEOUT_MS = 60_000
// If GPT-Live never reports `session.started` the microphone is live but nothing would
// end the session, so give up after this long.
export const CONNECT_TIMEOUT_MS = 15_000
export const MAX_SESSION_MS = 10 * 60_000
// A number can arrive split across transcript fragments, so check once speech pauses.
export const NUMBER_CHECK_DELAY_MS = 1500
// GPT-Live can signal a delegation before the transcript of what was said has come in
// (the transcription runs separately), so a delegation waits for the words to settle:
// this long with nothing new, and never longer than the maximum.
export const TRANSCRIPT_SETTLE_MS = 400
export const TRANSCRIPT_MAX_WAIT_MS = 3000

function describeStartError(error) {
  if (error?.name === 'MicrophoneDenied') return 'Microphone access was blocked. You can still use the chat.'
  if (error?.name === 'NotFoundError') return 'No microphone was found. You can still use the chat.'
  if (error instanceof ApiError && error.status === 429) {
    return 'Too many voice sessions were started. Please wait a minute and try again.'
  }
  if (error instanceof ApiError && error.status === 503) {
    return 'Voice is not available right now. You can still use the chat.'
  }
  return 'Voice could not start. You can still use the chat.'
}

export const useVoiceStore = defineStore('voice', () => {
  const householdStore = useHouseholdStore()
  const localContextStore = useLocalContextStore()
  const fireMapStore = useFireMapStore()
  const travelStore = useTravelDisruptionsStore()
  const safetyStore = useSafetyGuidanceStore()

  // idle | connecting | listening | checking | closing | error
  const status = ref('idle')
  const error = ref(null)
  const notice = ref(null)

  // None of this is shown, so none of it is reactive. It all belongs to one session.
  let connection = null
  let activeRouter = null
  let handlers = {}
  let active = false
  let utterance = ''
  // True once a delegation has taken what was heard. While false, speech heard so far
  // has not been handed to the server, so an assistant reply of its own (a clarifying
  // question, a greeting) means that speech belongs to a finished turn.
  let delegatedSinceHeard = false
  let spoken = ''
  let sentTexts = []
  let latestDelegation = null
  let lastLabel = ''
  let lastText = ''
  let commentaryCount = 0
  let idleTimer = null
  let maxTimer = null
  let checkTimer = null
  let connectTimer = null
  // A delegation that is waiting for its transcript to settle: { resolve, quietTimer, capTimer }.
  let transcriptWait = null

  function clearTimers() {
    clearTimeout(idleTimer)
    clearTimeout(maxTimer)
    clearTimeout(checkTimer)
    clearTimeout(connectTimer)
    idleTimer = null
    maxTimer = null
    checkTimer = null
    connectTimer = null
  }

  function finishTranscriptWait() {
    const wait = transcriptWait
    if (!wait) return
    transcriptWait = null
    clearTimeout(wait.quietTimer)
    clearTimeout(wait.capTimer)
    wait.resolve()
  }

  // Resolves when no new words have arrived for TRANSCRIPT_SETTLE_MS (once there are
  // some), or when the maximum wait is up, or when the session ends.
  function waitForTranscript() {
    finishTranscriptWait() // a newer delegation supersedes an older one still waiting
    return new Promise((resolve) => {
      transcriptWait = {
        resolve,
        quietTimer: null,
        capTimer: setTimeout(finishTranscriptWait, TRANSCRIPT_MAX_WAIT_MS),
      }
      if (utterance.trim()) transcriptWait.quietTimer = setTimeout(finishTranscriptWait, TRANSCRIPT_SETTLE_MS)
    })
  }

  function resetSession() {
    finishTranscriptWait()
    clearTimers()
    connection = null
    active = false
    utterance = ''
    delegatedSinceHeard = false
    spoken = ''
    sentTexts = []
    latestDelegation = null
    lastLabel = ''
    lastText = ''
  }

  function touch() {
    if (!active) return
    clearTimeout(idleTimer)
    idleTimer = setTimeout(stop, IDLE_TIMEOUT_MS)
  }

  function scheduleNumberCheck() {
    clearTimeout(checkTimer)
    checkTimer = setTimeout(() => {
      const extra = unexpectedNumbers(sentTexts, spoken)
      notice.value = extra.length ? VOICE_CHECK_FIGURES : null
      spoken = ''
    }, NUMBER_CHECK_DELAY_MS)
  }

  function sendCommentary(delegationId, content) {
    if (!connection) return
    sentTexts.push(content)
    spoken = ''
    commentaryCount += 1
    connection.send({
      type: 'session.commentary.append',
      event_id: `result_${commentaryCount}`,
      delegation_id: delegationId,
      content,
    })
  }

  async function runDelegation(id) {
    latestDelegation = id
    notice.value = null
    status.value = 'checking'

    const say = (content) => {
      // A newer delegation, or a closed session, makes this result stale.
      if (latestDelegation !== id || !connection) return
      sendCommentary(id, content)
      status.value = 'listening'
    }

    try {
      await waitForTranscript()
      // Superseded or the session ended while waiting: leave the words for the newer request.
      if (latestDelegation !== id || !active) return
      const text = utterance.trim().slice(-MAX_QUESTION_LENGTH)
      utterance = ''
      delegatedSinceHeard = true
      if (!text) {
        say(VOICE_NOT_UNDERSTOOD)
        return
      }
      const householdId = await householdStore.ensureHousehold()
      const decision = await api.decideVoiceAction(householdId, {
        utterance: text,
        page: pageLabel(activeRouter.currentRoute.value.name),
        lastReadout: lastLabel,
      })
      if (latestDelegation !== id) return
      const handler = decision.action === 'none' ? null : handlers[decision.action]
      if (!handler) {
        say(VOICE_NOT_UNDERSTOOD)
        return
      }
      const result = await handler({ utterance: text })
      if (latestDelegation !== id) return
      if (result.label) {
        lastLabel = result.label
        lastText = result.spoken
      }
      say(result.spoken)
    } catch {
      say(VOICE_UNAVAILABLE)
    }
  }

  function handleEvent(event) {
    switch (event?.type) {
      case 'session.started':
        clearTimeout(connectTimer)
        connectTimer = null
        status.value = 'listening'
        maxTimer = setTimeout(stop, MAX_SESSION_MS)
        touch()
        break
      case 'session.input_transcript.delta':
        utterance += event.delta ?? ''
        if (transcriptWait) {
          // The words of a request already signalled: keep waiting until they settle.
          clearTimeout(transcriptWait.quietTimer)
          transcriptWait.quietTimer = setTimeout(finishTranscriptWait, TRANSCRIPT_SETTLE_MS)
        } else {
          delegatedSinceHeard = false
        }
        touch()
        break
      case 'session.output_transcript.delta':
        // The assistant is answering on its own, so what was heard is a finished turn:
        // do not let it run into the next request.
        if (!delegatedSinceHeard && utterance && !transcriptWait) utterance = ''
        spoken += event.delta ?? ''
        touch()
        scheduleNumberCheck()
        break
      case 'session.delegation.created':
        if (event.delegation?.id) {
          touch()
          void runDelegation(event.delegation.id)
        }
        break
      default:
        break
    }
  }

  function handleClosed() {
    resetSession()
    if (status.value !== 'error') status.value = 'idle'
  }

  async function start({ router }) {
    if (status.value !== 'idle' && status.value !== 'error') return
    status.value = 'connecting'
    error.value = null
    notice.value = null
    activeRouter = router
    handlers = createHandlers({
      router,
      householdStore,
      localContextStore,
      fireMapStore,
      travelStore,
      safetyStore,
      getLastText: () => lastText,
    })
    active = true
    try {
      const householdId = await householdStore.ensureHousehold()
      connection = await liveTransport.open({
        requestAnswer: async (sdp) => (await api.createLiveSession(householdId, sdp)).transport.sdp,
        onEvent: handleEvent,
        onClosed: handleClosed,
      })
      // `session.started` normally clears this well within the time allowed.
      if (status.value === 'connecting') connectTimer = setTimeout(stop, CONNECT_TIMEOUT_MS)
    } catch (failure) {
      resetSession()
      status.value = 'error'
      error.value = describeStartError(failure)
    }
  }

  function stop() {
    if (!connection) {
      resetSession()
      if (status.value !== 'error') status.value = 'idle'
      return
    }
    clearTimers()
    status.value = 'closing'
    connection.close()
  }

  return { status, error, notice, start, stop }
})

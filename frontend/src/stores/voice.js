import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, newId } from '../api/client.js'
import { describeAction, executeAction } from '../voice/executor.js'
import { decideCommand, decideConfirmation, decideSuggestion } from '../voice/policy.js'
import { NONE_OF_THESE, buildBatch } from '../voice/questions.js'
import { snapshotContext, snapshotTargets } from '../voice/registry.js'
import { createWebSpeechStt, speechRecognitionAvailable } from '../voice/stt.js'

const MAX_TRANSCRIPT = 500
const MAX_FAILURES = 2
const MAX_SUGGESTIONS = 9
const SILENCE_MS = 30000
const SUGGESTION_WAIT_MS = 3000
const SUGGESTION_POLL_MS = 100
const STOP_PHRASES = new Set(['stop', 'cancel', 'stop listening'])

const RECOGNITION_MESSAGES = {
  'not-allowed': 'Microphone blocked — allow it in your browser settings.',
  'service-not-allowed': 'Microphone blocked — allow it in your browser settings.',
  'audio-capture': 'No microphone was found.',
  network: 'Voice recognition lost its connection. Try again.',
}

// Matched in the browser before any request, so stopping works even when the
// judge is down.
export function isStopPhrase(transcript) {
  return STOP_PHRASES.has(transcript.trim().toLowerCase().replace(/[.!?,]+$/, ''))
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

export const useVoiceStore = defineStore('voice', () => {
  // idle | listening | judging | confirming | dictating | choosing
  const status = ref('idle')
  const interim = ref('')
  const heard = ref('')
  const message = ref('')
  const prompt = ref('')
  const suggestions = ref([])

  let stt = null
  // Every session and every ending bumps this, so a reply that arrives late
  // for a session already over is ignored.
  let session = 0
  let silenceTimer = null
  let settings = { silenceMs: SILENCE_MS, suggestionWaitMs: SUGGESTION_WAIT_MS }
  // What the next utterance answers: a command, a yes/no, a dictated value, or
  // a numbered suggestion.
  let phase = 'normal'
  // The action awaiting yes while confirming; the target while dictating or choosing.
  let held = null
  let reasked = false
  let failures = 0
  let busy = false
  let queued = null

  function isSupported() {
    return speechRecognitionAvailable()
  }

  function toggle() {
    if (status.value === 'idle') startSession()
    else endSession()
  }

  function startSession(options = {}) {
    if (status.value !== 'idle') return
    settings = {
      silenceMs: options.silenceMs ?? SILENCE_MS,
      suggestionWaitMs: options.suggestionWaitMs ?? SUGGESTION_WAIT_MS,
    }
    session += 1
    failures = 0
    busy = false
    queued = null
    heard.value = ''
    interim.value = ''
    clearHeld()
    setPhase('normal')
    message.value = 'Listening…'
    stt = (options.createStt ?? createWebSpeechStt)()
    stt.start({ onInterim, onFinal, onError })
    armSilence()
  }

  // Ending always discards a held action: nothing waits across sessions.
  function endSession(finalMessage = 'Stopped listening.') {
    session += 1
    clearTimeout(silenceTimer)
    const ending = stt
    stt = null
    ending?.stop()
    busy = false
    queued = null
    interim.value = ''
    clearHeld()
    phase = 'normal'
    status.value = 'idle'
    message.value = finalMessage
  }

  function setPhase(next) {
    phase = next
    status.value = next === 'normal' ? 'listening' : next
  }

  function clearHeld() {
    held = null
    reasked = false
    prompt.value = ''
    suggestions.value = []
  }

  function armSilence() {
    clearTimeout(silenceTimer)
    silenceTimer = setTimeout(
      () => endSession('Stopped listening after 30 seconds of silence.'),
      settings.silenceMs,
    )
  }

  function onInterim(text) {
    interim.value = text
    armSilence()
  }

  function onError(code) {
    endSession(RECOGNITION_MESSAGES[code] ?? 'Voice recognition stopped unexpectedly.')
  }

  function onFinal(text) {
    if (status.value === 'idle') return Promise.resolve()
    interim.value = ''
    heard.value = text
    armSilence()
    if (isStopPhrase(text)) {
      logTurn({
        turnId: newId('vt'), mode: phase, transcript: text,
        decision: 'stop', outcome: 'none', startedAt: Date.now(),
      })
      endSession('Stopped.')
      return Promise.resolve()
    }
    // One turn at a time. Only the newest waiting utterance is kept.
    if (busy) {
      queued = text
      return Promise.resolve()
    }
    return process(text)
  }

  async function process(transcript) {
    const mySession = session
    busy = true
    try {
      if (phase === 'dictating') await takeDictation(transcript, mySession)
      else await judgeTurn(transcript, mySession)
    } finally {
      if (mySession === session) busy = false
    }
    if (mySession === session && queued !== null) {
      const next = queued
      queued = null
      await process(next)
    }
  }

  async function judgeTurn(transcript, mySession) {
    const turn = {
      turnId: newId('vt'), mode: phase, transcript,
      answers: [], catalogue: [], judgeMs: null, startedAt: Date.now(),
    }
    if (transcript.length > MAX_TRANSCRIPT) {
      message.value = 'That was too long. Try a shorter command.'
      logTurn({ ...turn, decision: 'reject', outcome: 'none' })
      return
    }

    const batch = buildBatch({
      transcript,
      targets: snapshotTargets(),
      context: snapshotContext(),
      mode: phase,
      choosing: suggestions.value,
    })
    status.value = 'judging'
    let answers
    try {
      ({ answers } = await api.judgeVoiceCommand({ state: batch.state, questions: batch.questions }))
    } catch {
      if (mySession !== session) return
      failures += 1
      logTurn({ ...turn, decision: 'unavailable', outcome: 'none' })
      if (failures >= MAX_FAILURES) {
        endSession('Voice commands are unavailable right now.')
        return
      }
      clearHeld()
      setPhase('normal')
      message.value = 'Voice commands are unavailable right now.'
      return
    }
    if (mySession !== session) return

    failures = 0
    Object.assign(turn, {
      answers, catalogue: batch.catalogue, judgeMs: Date.now() - turn.startedAt,
    })
    if (turn.mode === 'confirming') await settleConfirmation(turn, mySession)
    else if (turn.mode === 'choosing') settleChoice(turn)
    else await settleCommand(turn, mySession)
  }

  async function settleCommand(turn, mySession) {
    const decision = decideCommand(turn.answers, turn.catalogue)
    switch (decision.type) {
      case 'stop':
        logTurn({ ...turn, decision: 'stop', outcome: 'none' })
        endSession('Stopped.')
        return
      case 'reject':
        setPhase('normal')
        message.value = 'I didn’t catch that.'
        logTurn({ ...turn, decision: 'reject', outcome: 'none' })
        return
      case 'confirm':
        held = decision.action
        reasked = false
        setPhase('confirming')
        message.value = ''
        prompt.value = `${describeAction(decision.action)}? Say yes or no.`
        logTurn({ ...turn, decision: 'confirm', action: decision.action, outcome: 'pending' })
        return
      case 'dictate': {
        const { target } = decision
        held = target
        setPhase('dictating')
        message.value = ''
        prompt.value = target.kind === 'address'
          ? `Say the address for ${target.label}.`
          : `What should I enter for ${target.label}?`
        logTurn({
          ...turn, decision: 'dictate',
          action: { kind: target.kind, target, value: null }, outcome: 'pending',
        })
        return
      }
      default:
        await perform(decision.action, turn, 'execute', mySession)
    }
  }

  async function perform(action, turn, decision, mySession) {
    const result = await executeAction(action, snapshotTargets())
    logTurn({ ...turn, decision, action, outcome: result.ok ? 'ok' : 'fail' })
    if (mySession !== session) return
    clearHeld()
    setPhase('normal')
    message.value = result.message
  }

  async function settleConfirmation(turn, mySession) {
    const decision = decideConfirmation(turn.answers)
    const action = held
    if (decision.type === 'stop') {
      logTurn({ ...turn, decision: 'stop', action, outcome: 'none' })
      endSession('Stopped.')
      return
    }
    if (decision.type === 'execute') {
      await perform(action, turn, 'execute', mySession)
      return
    }
    if (decision.type === 'unclear' && !reasked) {
      reasked = true
      setPhase('confirming')
      prompt.value = `Please say yes or no. ${describeAction(action)}?`
      logTurn({ ...turn, decision: 'unclear', action, outcome: 'pending' })
      return
    }
    logTurn({ ...turn, decision: decision.type, action, outcome: 'none' })
    clearHeld()
    setPhase('normal')
    message.value = decision.type === 'cancel'
      ? 'Cancelled. Nothing was changed.'
      : 'I still didn’t catch that, so nothing was changed.'
  }

  function settleChoice(turn) {
    const decision = decideSuggestion(turn.answers)
    const target = held
    const logged = (value = null) => ({ kind: 'address', target, value })
    if (decision.type === 'stop') {
      logTurn({ ...turn, decision: 'stop', action: logged(), outcome: 'none' })
      endSession('Stopped.')
      return
    }
    if (decision.type === 'choose') {
      const chosen = suggestions.value[decision.index]
      const live = snapshotTargets().find((item) => item.id === target.id)
      // Only the very list the user was shown: the field may have changed since.
      const ok = chosen !== undefined && live?.suggestions?.()[decision.index] === chosen
      if (ok) live.choose(decision.index)
      logTurn({ ...turn, decision: 'choose', action: logged(chosen ?? null), outcome: ok ? 'ok' : 'fail' })
      clearHeld()
      setPhase('normal')
      message.value = ok
        ? `✓ Chose ${chosen}`
        : 'Those suggestions changed, so the address is kept as entered and is not verified.'
      return
    }
    if (decision.type === 'unclear' && !reasked) {
      reasked = true
      setPhase('choosing')
      prompt.value = 'Please say a number from the list, or none.'
      logTurn({ ...turn, decision: 'unclear', action: logged(), outcome: 'pending' })
      return
    }
    logTurn({ ...turn, decision: decision.type, action: logged(), outcome: 'none' })
    clearHeld()
    setPhase('normal')
    message.value = 'The address is kept as entered. It is not verified.'
  }

  async function takeDictation(transcript, mySession) {
    const turn = {
      turnId: newId('vt'), mode: 'dictating', transcript,
      answers: [], catalogue: [], judgeMs: null, startedAt: Date.now(),
    }
    const target = held
    const action = { kind: target.kind, target, value: transcript }
    if (target.kind !== 'address') {
      await perform(action, turn, 'dictated', mySession)
      return
    }

    // The address goes in exactly as heard; the component's own lookup runs.
    const result = await executeAction(action, snapshotTargets())
    if (!result.ok) {
      logTurn({ ...turn, decision: 'dictated', action, outcome: 'fail' })
      if (mySession !== session) return
      clearHeld()
      setPhase('normal')
      message.value = result.message
      return
    }
    clearHeld()
    status.value = 'judging'
    const found = await waitForSuggestions(target.id, mySession)
    if (mySession !== session) return
    if (!found.length) {
      logTurn({ ...turn, decision: 'dictated', action, outcome: 'ok' })
      setPhase('normal')
      message.value = 'No matching addresses were found. The address is kept as entered and is not verified.'
      return
    }
    held = target
    reasked = false
    suggestions.value = found.slice(0, MAX_SUGGESTIONS)
    setPhase('choosing')
    message.value = ''
    prompt.value = 'Say a number from the list, or none.'
    logTurn({ ...turn, decision: 'dictated', action, outcome: 'pending' })
  }

  async function waitForSuggestions(targetId, mySession) {
    const deadline = Date.now() + settings.suggestionWaitMs
    while (Date.now() < deadline) {
      await sleep(SUGGESTION_POLL_MS)
      if (mySession !== session) return []
      const live = snapshotTargets().find((item) => item.id === targetId)
      const found = live?.suggestions?.() ?? []
      if (found.length) return found
    }
    return []
  }

  // Logged as the target id, never the spoken phrase: phrases can hold names.
  function commandTargetId(phrase, catalogue) {
    if (phrase === NONE_OF_THESE) return NONE_OF_THESE
    return catalogue.find((entry) => entry.phrase === phrase)?.target.id ?? null
  }

  function logTurn({
    turnId, mode, transcript, answers = [], catalogue = [],
    decision, action = null, outcome, judgeMs = null, startedAt,
  }) {
    const context = snapshotContext()
    const value = action?.value
    const record = {
      turn_id: turnId,
      page: context.page,
      step: context.step,
      mode,
      transcript: transcript.slice(0, MAX_TRANSCRIPT),
      answers: answers.map((answer) => ({
        id: answer.id,
        answer: answer.id === 'command' ? commandTargetId(answer.answer, catalogue) : answer.answer,
        probability: answer.probability,
      })),
      decision,
      action: action && {
        kind: action.kind,
        target: action.target.id,
        value: value === null || value === undefined ? null : String(value).slice(0, MAX_TRANSCRIPT),
      },
      outcome,
      latency_ms: { judge: judgeMs, turn: Math.max(0, Date.now() - startedAt) },
    }
    // Fire and forget: a missed log line is never the user's problem.
    Promise.resolve()
      .then(() => api.logVoiceTurn(record))
      .catch(() => {})
  }

  return {
    status,
    interim,
    heard,
    message,
    prompt,
    suggestions,
    isSupported,
    toggle,
    startSession,
    endSession,
  }
})

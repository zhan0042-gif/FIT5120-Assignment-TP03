import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '../api/client.js'
import { MAX_QUESTION_LENGTH } from '../utils/safetyGuidanceCopy.js'

const LOAD_ERROR = 'Safety guidance could not be loaded. The rest of your overview is unaffected.'

export const useSafetyGuidanceStore = defineStore('safetyGuidance', () => {
  const entries = ref([])
  const suggestedIds = ref([])
  const locationConditionsApplied = ref(false)
  // The conversation lives here for the visit only. It is never sent to the server.
  const messages = ref([])
  const status = ref('idle')
  const error = ref(null)
  const asking = ref(false)
  let revision = 0
  let nextMessageId = 1

  const entriesById = computed(() =>
    Object.fromEntries(entries.value.map((entry) => [entry.id, entry])),
  )
  // Suggested questions, in the server's order, ignoring any id that is not an entry.
  const suggested = computed(() =>
    suggestedIds.value.map((id) => entriesById.value[id]).filter(Boolean),
  )

  // Every entry that is not a suggested question, in file order, so each one can be
  // asked from a button and nothing is reachable only by reading a long list.
  const moreQuestions = computed(() => {
    const offered = new Set(suggestedIds.value)
    return entries.value.filter((entry) => !offered.has(entry.id))
  })

  function clearContent() {
    entries.value = []
    suggestedIds.value = []
    locationConditionsApplied.value = false
    messages.value = []
    error.value = null
  }

  async function load(householdId) {
    const requestRevision = ++revision
    clearContent()
    if (!householdId) {
      status.value = 'idle'
      return
    }
    status.value = 'loading'
    try {
      const response = await api.getSafetyGuidance(householdId)
      if (requestRevision !== revision) return
      entries.value = response.entries ?? []
      suggestedIds.value = response.suggested_ids ?? []
      locationConditionsApplied.value = Boolean(response.location_conditions_applied)
      status.value = 'success'
    } catch {
      if (requestRevision !== revision) return
      status.value = 'error'
      error.value = LOAD_ERROR
    }
  }

  // A first-time visitor has no household yet; the caller supplies how to get one
  // (for example the household store's ensureHousehold) so the panel never loads
  // with a null id and stays blank.
  async function loadFor(resolveHouseholdId) {
    const startRevision = revision
    let householdId
    try {
      householdId = await resolveHouseholdId()
    } catch {
      if (startRevision !== revision) return
      clearContent()
      status.value = 'error'
      error.value = LOAD_ERROR
      return
    }
    if (startRevision !== revision) return
    await load(householdId)
  }

  // Show a reviewed answer. Nothing is requested: the entry is already here.
  function ask(entryId) {
    const entry = entriesById.value[entryId]
    if (!entry) return false
    messages.value.push({ id: nextMessageId++, role: 'user', text: entry.question })
    messages.value.push({ id: nextMessageId++, role: 'assistant', entryId: entry.id })
    return true
  }

  const FIXED_KINDS = new Set(['no_match', 'emergency', 'unavailable'])

  function addFixedMessage(kind) {
    messages.value.push({ id: nextMessageId++, role: 'assistant', kind })
  }

  // Send a typed question. The server only says which reviewed entries answer it;
  // the text shown is the reviewed text already held here.
  async function askTyped(householdId, text) {
    const question = (text ?? '').trim()
    if (!householdId || !question || question.length > MAX_QUESTION_LENGTH || asking.value) return false
    asking.value = true
    const startRevision = revision
    messages.value.push({ id: nextMessageId++, role: 'user', text: question })
    try {
      const answer = await api.askSafetyGuidance(householdId, question)
      if (startRevision !== revision) return false
      if (answer.status === 'matched') {
        const shown = (answer.entry_ids ?? []).map((id) => entriesById.value[id]).filter(Boolean)
        if (shown.length) {
          for (const entry of shown) {
            messages.value.push({ id: nextMessageId++, role: 'assistant', entryId: entry.id })
          }
        } else {
          addFixedMessage('no_match')
        }
      } else {
        addFixedMessage(FIXED_KINDS.has(answer.status) ? answer.status : 'unavailable')
      }
    } catch {
      if (startRevision === revision) addFixedMessage('unavailable')
      return startRevision === revision
    } finally {
      asking.value = false
    }
    return true
  }

  function reset() {
    revision += 1
    clearContent()
    asking.value = false
    status.value = 'idle'
  }

  return {
    entries,
    suggestedIds,
    locationConditionsApplied,
    messages,
    status,
    error,
    asking,
    entriesById,
    suggested,
    moreQuestions,
    load,
    loadFor,
    ask,
    askTyped,
    reset,
  }
})

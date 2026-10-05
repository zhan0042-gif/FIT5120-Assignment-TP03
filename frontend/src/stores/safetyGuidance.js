import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '../api/client.js'

const LOAD_ERROR = 'Safety guidance could not be loaded. The rest of your overview is unaffected.'

export const useSafetyGuidanceStore = defineStore('safetyGuidance', () => {
  const entries = ref([])
  const suggestedIds = ref([])
  const locationConditionsApplied = ref(false)
  // The conversation lives here for the visit only. It is never sent to the server.
  const messages = ref([])
  const status = ref('idle')
  const error = ref(null)
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

  function reset() {
    revision += 1
    clearContent()
    status.value = 'idle'
  }

  return {
    entries,
    suggestedIds,
    locationConditionsApplied,
    messages,
    status,
    error,
    entriesById,
    suggested,
    moreQuestions,
    load,
    loadFor,
    ask,
    reset,
  }
})

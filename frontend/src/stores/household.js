import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  ApiError,
  api,
  clearStoredHouseholdId,
  loadStoredHouseholdId,
  storeHouseholdId,
} from '../api/client'
import { createEmptyHouseholdPlan } from '../domain/householdPlan'

function isMissingHousehold(error) {
  return (
    error instanceof ApiError &&
    error.status === 404 &&
    error.message.includes('was not found')
  )
}

function isMissingPlan(error) {
  return error instanceof ApiError && error.status === 404
}

export const useHouseholdStore = defineStore('household', () => {
  const householdId = ref(loadStoredHouseholdId())
  const plan = ref(null)
  const planStatus = ref('idle')
  const planError = ref(null)

  const completion = ref(null)
  const completionStatus = ref('idle')

  const saveStatus = ref('idle')
  const saveError = ref(null)
  let householdRequest = null

  async function createAndStoreHousehold() {
    const created = await api.createHousehold()
    householdId.value = created.household_id
    storeHouseholdId(created.household_id)
    return created.household_id
  }

  async function ensureHousehold() {
    if (householdId.value) return householdId.value
    if (!householdRequest) {
      householdRequest = createAndStoreHousehold().finally(() => {
        householdRequest = null
      })
    }
    return householdRequest
  }

  async function replaceMissingHousehold() {
    householdId.value = null
    clearStoredHouseholdId()
    return ensureHousehold()
  }

  function setNewPlanState() {
    plan.value = createEmptyHouseholdPlan()
    completion.value = null
    completionStatus.value = 'idle'
    planStatus.value = 'success'
  }

  async function loadPlan() {
    planStatus.value = 'loading'
    planError.value = null
    try {
      let id = await ensureHousehold()
      try {
        plan.value = await api.getHouseholdPlan(id)
      } catch (error) {
        if (isMissingHousehold(error)) {
          id = await replaceMissingHousehold()
          setNewPlanState()
          return
        }
        if (isMissingPlan(error)) {
          setNewPlanState()
          return
        }
        throw error
      }
      planStatus.value = 'success'
      await loadCompletion()
    } catch (error) {
      planStatus.value = 'error'
      planError.value =
        error instanceof Error ? error.message : 'Failed to load the household plan.'
    }
  }

  async function loadCompletion() {
    completionStatus.value = 'loading'
    try {
      const id = await ensureHousehold()
      completion.value = await api.getCompletion(id)
      completionStatus.value = 'success'
    } catch (error) {
      if (isMissingHousehold(error)) {
        await replaceMissingHousehold()
        setNewPlanState()
        return
      }
      if (isMissingPlan(error)) {
        completion.value = null
        completionStatus.value = 'idle'
        return
      }
      completionStatus.value = 'error'
    }
  }

  async function savePlan(next) {
    saveStatus.value = 'loading'
    saveError.value = null
    try {
      let id = await ensureHousehold()
      try {
        plan.value = await api.saveHouseholdPlan(id, next)
      } catch (error) {
        if (!isMissingHousehold(error)) throw error
        id = await replaceMissingHousehold()
        plan.value = await api.saveHouseholdPlan(id, next)
      }
      saveStatus.value = 'success'
      await loadCompletion()
    } catch (error) {
      saveStatus.value = 'error'
      saveError.value = error instanceof Error ? error.message : 'Failed to save the household plan.'
    }
  }

  return {
    householdId,
    plan,
    planStatus,
    planError,
    completion,
    completionStatus,
    saveStatus,
    saveError,
    ensureHousehold,
    loadPlan,
    savePlan,
  }
})

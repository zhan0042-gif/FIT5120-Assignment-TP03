import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client'
import type { HouseholdPlan, PlanCompletion } from '../types/household'
import type { AsyncStatus } from '../types/async'

export const useHouseholdStore = defineStore('household', () => {
  const plan = ref<HouseholdPlan | null>(null)
  const planStatus = ref<AsyncStatus>('idle')
  const planError = ref<string | null>(null)

  const completion = ref<PlanCompletion | null>(null)
  const completionStatus = ref<AsyncStatus>('idle')

  const saveStatus = ref<AsyncStatus>('idle')
  const saveError = ref<string | null>(null)

  async function loadPlan() {
    planStatus.value = 'loading'
    planError.value = null
    try {
      plan.value = await api.getHouseholdPlan()
      planStatus.value = 'success'
      await loadCompletion()
    } catch (err) {
      planStatus.value = 'error'
      planError.value = err instanceof Error ? err.message : 'Failed to load the household plan.'
    }
  }

  async function loadCompletion() {
    completionStatus.value = 'loading'
    try {
      completion.value = await api.getCompletion()
      completionStatus.value = 'success'
    } catch {
      completionStatus.value = 'error'
    }
  }

  async function savePlan(next: HouseholdPlan) {
    saveStatus.value = 'loading'
    saveError.value = null
    try {
      plan.value = await api.saveHouseholdPlan(next)
      saveStatus.value = 'success'
      await loadCompletion()
    } catch (err) {
      saveStatus.value = 'error'
      saveError.value = err instanceof Error ? err.message : 'Failed to save the household plan.'
    }
  }

  return { plan, planStatus, planError, completion, completionStatus, saveStatus, saveError, loadPlan, savePlan }
})

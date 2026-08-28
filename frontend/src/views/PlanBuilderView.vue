<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useHouseholdStore } from '../stores/household'
import { useLocalContextStore } from '../stores/localContext'
import LoadingState from '../components/common/LoadingState.vue'
import ErrorState from '../components/common/ErrorState.vue'
import LocalContextCard from '../components/localContext/LocalContextCard.vue'
import PreparationSupportBanner from '../components/localContext/PreparationSupportBanner.vue'
import HouseholdMembersForm from '../components/household/HouseholdMembersForm.vue'
import TransportForm from '../components/household/TransportForm.vue'
import ArrangementsForm from '../components/household/ArrangementsForm.vue'
import ResponsibilitiesForm from '../components/household/ResponsibilitiesForm.vue'
import CompletionOverview from '../components/completion/CompletionOverview.vue'
import type { HouseholdPlan } from '../types/household'

const householdStore = useHouseholdStore()
const localContextStore = useLocalContextStore()

const draft = ref<HouseholdPlan | null>(null)

function resetDraft() {
  // structuredClone chokes on Vue's reactive proxies; JSON round-trip is safe
  // because HouseholdPlan is plain, JSON-serialisable data.
  draft.value = householdStore.plan ? JSON.parse(JSON.stringify(householdStore.plan)) : null
}

onMounted(async () => {
  if (householdStore.planStatus === 'idle') await householdStore.loadPlan()
  resetDraft()
  if (localContextStore.contextStatus === 'idle') {
    localContextStore.init()
  }
})

watch(
  () => householdStore.plan,
  () => {
    if (!draft.value) resetDraft()
  },
)

const hasUnsavedChanges = computed(() => {
  if (!draft.value || !householdStore.plan) return false
  return JSON.stringify(draft.value) !== JSON.stringify(householdStore.plan)
})

const validationErrors = computed(() => {
  if (!draft.value) return []
  const errors: string[] = []
  for (const r of draft.value.responsibilities) {
    if (r.backup_member_id && r.backup_member_id === r.primary_member_id) {
      errors.push(`"${r.task_name || 'A responsibility'}" has the same person set as primary and backup.`)
    }
  }
  return errors
})

async function save() {
  if (!draft.value || validationErrors.value.length > 0) return
  await householdStore.savePlan(draft.value)
  await localContextStore.loadPreparationSupport()
}
</script>

<template>
  <div class="plan-builder">
    <p class="eyebrow">Plan builder</p>
    <h1 class="headline">Build the plan</h1>
    <p class="subhead">Everything here feeds the scenario tester — the more complete it is, the more useful a stress test becomes.</p>

    <PreparationSupportBanner />
    <LocalContextCard />

    <LoadingState v-if="householdStore.planStatus === 'loading'" message="Loading your household plan…" />
    <ErrorState
      v-else-if="householdStore.planStatus === 'error'"
      :message="householdStore.planError ?? undefined"
      @retry="householdStore.loadPlan"
    />

    <template v-else-if="draft">
      <HouseholdMembersForm v-model:members="draft.members" v-model:animals="draft.animals" />
      <TransportForm v-model="draft.transports" :members="draft.members" />
      <ArrangementsForm v-model="draft.arrangements" :transports="draft.transports" />
      <ResponsibilitiesForm v-model="draft.responsibilities" :members="draft.members" />
      <CompletionOverview :completion="householdStore.completion" :loading="householdStore.completionStatus === 'loading'" />

      <div class="save-bar">
        <div>
          <p v-if="validationErrors.length" class="field-error">{{ validationErrors[0] }}</p>
          <p v-else-if="householdStore.saveStatus === 'error'" class="field-error">{{ householdStore.saveError }}</p>
          <p v-else-if="hasUnsavedChanges" class="hint">You have unsaved changes.</p>
          <p v-else class="hint">All changes saved.</p>
        </div>
        <button
          class="btn btn-accent"
          type="button"
          :disabled="!hasUnsavedChanges || validationErrors.length > 0 || householdStore.saveStatus === 'loading'"
          @click="save"
        >
          {{ householdStore.saveStatus === 'loading' ? 'Saving…' : 'Save plan' }}
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.plan-builder {
  max-width: 780px;
}

.headline {
  font-size: 1.9rem;
  margin: 0.4rem 0 0.5rem;
}

.subhead {
  color: var(--color-text-muted);
  margin-bottom: 1.75rem;
}

.save-bar {
  position: sticky;
  bottom: 1rem;
  margin-top: 1.5rem;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 1rem 1.25rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  box-shadow: 0 4px 14px rgba(20, 23, 28, 0.12);
}

.hint {
  font-size: 0.8rem;
  color: var(--color-text-muted);
}
</style>

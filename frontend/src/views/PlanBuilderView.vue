<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useHouseholdStore } from '../stores/household'
import LoadingState from '../components/common/LoadingState.vue'
import ErrorState from '../components/common/ErrorState.vue'
import HouseholdMembersForm from '../components/household/HouseholdMembersForm.vue'
import TransportForm from '../components/household/TransportForm.vue'
import ArrangementsForm from '../components/household/ArrangementsForm.vue'
import ResponsibilitiesForm from '../components/household/ResponsibilitiesForm.vue'
import PlanChecks from '../components/completion/PlanChecks.vue'

const householdStore = useHouseholdStore()
const route = useRoute()

const draft = ref(null)

function resetDraft() {
  // Child forms edit this detached aggregate. Restoring the server plan after
  // load/save makes the dirty comparison clean without treating hydration as an
  // edit. JSON cloning is safe because HouseholdPlan is JSON-serialisable data.
  draft.value = householdStore.plan ? JSON.parse(JSON.stringify(householdStore.plan)) : null
}

onMounted(async () => {
  if (householdStore.planStatus === 'idle') await householdStore.loadPlan()
  resetDraft()
  await nextTick()
  const target = document.getElementById(`plan-${route.query.section}`)
  if (target) {
    target.scrollIntoView({ behavior: 'smooth', block: 'start' })
    target.focus({ preventScroll: true })
  }
})

watch(
  () => householdStore.plan,
  () => {
    if (!draft.value) resetDraft()
  },
)

const hasUnsavedChanges = computed(() => {
  // A failed save leaves `householdStore.plan` unchanged, so the user's draft
  // remains dirty and can be retried without losing edits.
  if (!draft.value || !householdStore.plan) return false
  return JSON.stringify(draft.value) !== JSON.stringify(householdStore.plan)
})

const validationErrors = computed(() => {
  if (!draft.value) return []
  const errors = []
  for (const animal of draft.value.animals) {
    if (!Number.isInteger(animal.quantity) || animal.quantity < 1) {
      errors.push('Animal quantity must be a whole number of at least 1.')
    }
    if (animal.animal_type === 'other' && !animal.animal_type_other?.trim()) {
      errors.push('Please describe the animal type when Other is selected.')
    }
  }
  for (const transport of draft.value.transports) {
    if (transport.transport_type === 'other' && !transport.transport_type_other?.trim()) {
      errors.push('Please describe the transport type when Other is selected.')
    }
  }
  for (const r of draft.value.responsibilities) {
    if (r.backup_member_id && r.backup_member_id === r.primary_member_id) {
      errors.push(`"${r.task_name || 'A responsibility'}" has the same person set as primary and backup.`)
    }
  }
  return errors
})

async function save() {
  // The backend accepts one structurally valid aggregate even when completion
  // sections are unfinished; completion and checks evaluate saved state later.
  if (!draft.value || validationErrors.value.length > 0) return
  await householdStore.savePlan(draft.value)
  if (householdStore.saveStatus === 'success') resetDraft()
}
</script>

<template>
  <div class="plan-builder">
    <div class="plan-scroll">
      <h1 class="headline">Build your household preparedness plan</h1>
      <p class="subhead">Add household members, animals, transport, destinations, and responsibilities. You can save your plan and return to update it later.</p>

      <LoadingState v-if="householdStore.planStatus === 'loading'" message="Loading your household plan…" />
      <ErrorState
        v-else-if="householdStore.planStatus === 'error'"
        message="Could not load your household plan."
        @retry="householdStore.loadPlan"
      />

      <template v-else-if="draft">
        <HouseholdMembersForm v-model:members="draft.members" v-model:animals="draft.animals" />
        <TransportForm
          id="plan-transport"
          tabindex="-1"
          v-model:transports="draft.transports"
          v-model:has-private-transport="draft.has_private_transport"
          :members="draft.members"
        />
        <ArrangementsForm id="plan-destinations" v-model="draft.arrangements" :transports="draft.transports" tabindex="-1" />
        <ResponsibilitiesForm id="plan-responsibilities" v-model="draft.responsibilities" :members="draft.members" tabindex="-1" />
        <PlanChecks :completion="householdStore.completion" :loading="householdStore.completionStatus === 'loading'" />
      </template>
    </div>

    <div v-if="draft" class="save-bar">
      <div>
        <p v-if="validationErrors.length" class="field-error">{{ validationErrors[0] }}</p>
        <p v-else-if="householdStore.saveStatus === 'error'" class="field-error">Your plan could not be saved. Please try again.</p>
        <p v-else-if="hasUnsavedChanges" class="save-message">Unsaved changes</p>
        <p v-else class="save-message status-text status-success">✓ All changes saved.</p>
      </div>
      <button
        class="btn"
        :class="hasUnsavedChanges ? 'btn-accent' : 'btn-ghost saved-button'"
        type="button"
        :disabled="!hasUnsavedChanges || validationErrors.length > 0 || householdStore.saveStatus === 'loading'"
        @click="save"
      >
        {{ householdStore.saveStatus === 'loading' ? 'Saving…' : hasUnsavedChanges ? 'Save plan' : 'Saved' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.plan-builder {
  width: 100%;
  min-width: 0;
}

.plan-scroll {
  min-width: 0;
}

.headline {
  font-size: clamp(2rem, 4vw, 2.25rem);
  margin: 0.4rem 0 0.5rem;
}

.subhead {
  color: var(--color-text-muted);
  margin-bottom: 1.75rem;
}

.save-bar {
  /* Save belongs to the end of the plan in normal flow; it does not overlay forms. */
  margin-top: 1rem;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 0.75rem 1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  box-shadow: var(--shadow-card);
}

.hint {
  font-size: 0.875rem;
  color: var(--color-text-muted);
}

.save-message {
  font-size: 0.9rem;
  font-weight: 600;
}

.saved-button:disabled {
  background: var(--color-bg-card-muted);
  border-color: var(--color-border);
  color: var(--color-text-muted);
  opacity: 1;
}

@media (max-width: 520px) {
  .save-bar {
    align-items: stretch;
    flex-direction: column;
  }

  .save-bar .btn {
    width: 100%;
  }
}
</style>

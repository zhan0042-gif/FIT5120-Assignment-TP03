<script setup>
import { computed, onMounted, ref, watch } from 'vue'
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

// Stepping is presentation only. The draft, the dirty comparison, the validation
// and the save call below are untouched by it, and Save stays outside the steps
// so an incomplete plan is saveable from any of them.
const STEPS = [
  { id: 'people', label: 'People', heading: 'Who lives here?', subhead: 'Add the people and animals who leave with you.' },
  { id: 'transport', label: 'Transport', heading: 'What can you leave in?', subhead: 'Every vehicle, and who is able to drive it.' },
  { id: 'destinations', label: 'Destinations', heading: 'Where would you go?', subhead: 'One place you would head for, and one if that is closed.' },
  { id: 'responsibilities', label: 'Responsibilities', heading: 'Who does what?', subhead: 'The jobs that have to happen, and who covers each.' },
  { id: 'review', label: 'Review', heading: 'Your plan so far', subhead: 'Save it now. You can come back and fill the gaps.' },
]

const stepIndex = ref(0)
const currentStep = computed(() => STEPS[stepIndex.value])

function goToStep(index) {
  stepIndex.value = Math.min(STEPS.length - 1, Math.max(0, index))
}

function resetDraft() {
  // Child forms edit this detached aggregate. Restoring the server plan after
  // load/save makes the dirty comparison clean without treating hydration as an
  // edit. JSON cloning is safe because HouseholdPlan is JSON-serialisable data.
  draft.value = householdStore.plan ? JSON.parse(JSON.stringify(householdStore.plan)) : null
}

onMounted(async () => {
  if (householdStore.planStatus === 'idle') await householdStore.loadPlan()
  resetDraft()
  // The Overview page deep-links here with ?section=<id>; that now selects the
  // matching step instead of scrolling to it.
  const requested = STEPS.findIndex((step) => step.id === route.query.section)
  if (requested !== -1) goToStep(requested)
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
  <div class="plan-builder surface-paper">
    <div class="plan-scroll">
      <nav class="stepper" aria-label="Plan sections">
        <button
          v-for="(step, index) in STEPS"
          :key="step.id"
          type="button"
          class="step-chip"
          :class="{ 'is-current': index === stepIndex, 'is-done': index < stepIndex }"
          @click="goToStep(index)"
        >
          <span class="step-number">{{ index + 1 }}</span>
          <span class="step-label">{{ step.label }}</span>
        </button>
        <span class="step-progress">Step {{ stepIndex + 1 }} of {{ STEPS.length }}</span>
      </nav>

      <h1 class="headline">{{ currentStep.heading }}</h1>
      <p class="subhead">{{ currentStep.subhead }}</p>

      <LoadingState v-if="householdStore.planStatus === 'loading'" message="Loading your household plan…" />
      <ErrorState
        v-else-if="householdStore.planStatus === 'error'"
        message="Could not load your household plan."
        @retry="householdStore.loadPlan"
      />

      <template v-else-if="draft">
        <div v-show="stepIndex === 0">
          <HouseholdMembersForm v-model:members="draft.members" v-model:animals="draft.animals" />
        </div>
        <div v-show="stepIndex === 1">
          <TransportForm
            id="plan-transport"
            tabindex="-1"
            v-model:transports="draft.transports"
            v-model:has-private-transport="draft.has_private_transport"
            :members="draft.members"
          />
        </div>
        <div v-show="stepIndex === 2">
          <ArrangementsForm id="plan-destinations" v-model="draft.arrangements" :transports="draft.transports" tabindex="-1" />
        </div>
        <div v-show="stepIndex === 3">
          <ResponsibilitiesForm id="plan-responsibilities" v-model="draft.responsibilities" :members="draft.members" tabindex="-1" />
        </div>
        <div v-show="stepIndex === 4">
          <PlanChecks :completion="householdStore.completion" :loading="householdStore.completionStatus === 'loading'" />
        </div>

        <div class="step-nav">
          <button type="button" class="btn btn-ghost" :disabled="stepIndex === 0" @click="goToStep(stepIndex - 1)">Back</button>
          <button v-if="stepIndex < STEPS.length - 1" type="button" class="btn btn-accent" @click="goToStep(stepIndex + 1)">Continue</button>
          <router-link v-else class="btn btn-accent" to="/scenarios">Test my plan</router-link>
        </div>
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
  border-radius: 24px;
  padding: 1.75rem;
}

.stepper {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1.75rem;
}

.step-chip {
  align-items: center;
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  cursor: pointer;
  display: flex;
  font-family: inherit;
  gap: 0.6rem;
  min-height: 2.75rem;
  padding: 0 1.1rem 0 0.75rem;
}

.step-chip .step-number {
  align-items: center;
  background: var(--color-bg-card-muted);
  border-radius: var(--radius-pill);
  color: var(--color-text-muted);
  display: inline-flex;
  font-size: 0.8125rem;
  font-weight: 700;
  height: 1.5rem;
  justify-content: center;
  width: 1.5rem;
}

.step-chip .step-label {
  color: var(--color-text-muted);
  font-size: 0.9375rem;
  font-weight: 500;
  white-space: nowrap;
}

.step-chip.is-done .step-number {
  background: var(--color-success);
  color: #fff;
}

.step-chip.is-done .step-label {
  color: var(--color-text);
}

.step-chip.is-current {
  background: var(--color-text);
  border-color: var(--color-text);
}

.step-chip.is-current .step-number {
  background: var(--color-accent);
  color: var(--color-text-inverse);
}

.step-chip.is-current .step-label {
  color: var(--color-bg-content);
  font-weight: 700;
}

.step-progress {
  color: var(--color-text-muted);
  font-size: 0.875rem;
  font-weight: 500;
  margin-left: auto;
}

.step-nav {
  display: flex;
  gap: 0.75rem;
  justify-content: space-between;
  margin-top: 2rem;
}

.step-nav .btn {
  align-items: center;
  display: inline-flex;
  text-decoration: none;
}

@media (max-width: 700px) {
  .step-progress {
    margin-left: 0;
    width: 100%;
  }
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

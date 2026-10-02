<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useHouseholdStore } from '../stores/household'
import LoadingState from '../components/common/LoadingState.vue'
import ErrorState from '../components/common/ErrorState.vue'
import HouseholdMembersForm from '../components/household/HouseholdMembersForm.vue'
import TransportForm from '../components/household/TransportForm.vue'
import ArrangementsForm from '../components/household/ArrangementsForm.vue'
import ResponsibilitiesForm from '../components/household/ResponsibilitiesForm.vue'
import PlanChecks from '../components/completion/PlanChecks.vue'
import { saveAndReview } from '../utils/planReviewNavigation'

const householdStore = useHouseholdStore()
const route = useRoute()
const router = useRouter()

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

const saveDisabled = computed(() =>
  !hasUnsavedChanges.value || validationErrors.value.length > 0 || householdStore.saveStatus === 'loading',
)
const saveLabel = computed(() =>
  householdStore.saveStatus === 'loading' ? 'Saving…' : hasUnsavedChanges.value ? 'Save plan' : 'Saved',
)

async function save() {
  // The backend accepts one structurally valid aggregate even when completion
  // sections are unfinished; completion and checks evaluate saved state later.
  if (!draft.value || validationErrors.value.length > 0 || householdStore.saveStatus === 'loading') return false
  await householdStore.savePlan(draft.value)
  if (householdStore.saveStatus !== 'success') return false
  resetDraft()
  return true
}

async function reviewPlan() {
  await saveAndReview({
    needsSave: hasUnsavedChanges.value || !householdStore.planExists,
    save,
    navigate: (path) => router.push(path),
  })
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

      <div class="step-header">
        <div class="step-heading">
          <h1 class="headline">{{ currentStep.heading }}</h1>
          <p class="subhead">{{ currentStep.subhead }}</p>
        </div>
        <div v-if="draft && stepIndex < STEPS.length - 1" class="top-save">
          <button class="btn" :class="hasUnsavedChanges ? 'btn-accent' : 'btn-ghost saved-button'" type="button" :disabled="saveDisabled" @click="save">
            {{ saveLabel }}
          </button>
          <span v-if="validationErrors.length" class="field-error">{{ validationErrors[0] }}</span>
          <span v-else-if="householdStore.saveStatus === 'error'" class="field-error">Your plan could not be saved. Please try again.</span>
          <span v-else-if="hasUnsavedChanges" class="save-message">Unsaved changes</span>
          <span v-else class="save-message status-text status-success">✓ All changes saved.</span>
        </div>
      </div>

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
      </template>
    </div>

    <div v-if="draft" class="save-bar">
      <button v-show="householdStore.planStatus !== 'loading' && householdStore.planStatus !== 'error'" type="button" class="btn btn-ghost" :disabled="stepIndex === 0" @click="goToStep(stepIndex - 1)">Back</button>
      <div class="plan-actions">
        <div class="save-controls">
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
            :disabled="saveDisabled"
            @click="save"
          >
            {{ saveLabel }}
          </button>
        </div>
        <button v-if="stepIndex < STEPS.length - 1" v-show="householdStore.planStatus !== 'loading' && householdStore.planStatus !== 'error'" type="button" class="btn btn-accent next-action" @click="goToStep(stepIndex + 1)">Continue</button>
        <button v-else v-show="householdStore.planStatus !== 'loading' && householdStore.planStatus !== 'error'" type="button" class="btn btn-accent next-action" :disabled="validationErrors.length > 0 || householdStore.saveStatus === 'loading'" @click="reviewPlan">Save &amp; Review Plan</button>
      </div>
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

@media (max-width: 700px) {
  .step-progress {
    margin-left: 0;
    width: 100%;
  }
}

.plan-scroll {
  min-width: 0;
}

.step-header {
  align-items: flex-start;
  display: flex;
  gap: 1.5rem;
  justify-content: space-between;
  margin-bottom: 1.75rem;
}

.step-heading { min-width: 0; }

.headline {
  font-size: clamp(2rem, 4vw, 2.25rem);
  margin: 0.4rem 0 0.5rem;
}

.subhead {
  color: var(--color-text-muted);
}

.top-save {
  align-items: flex-end;
  display: flex;
  flex: 0 0 auto;
  flex-direction: column;
  gap: 0.4rem;
  max-width: 15rem;
  text-align: right;
}

.top-save .btn { flex: 0 0 auto; }

@media (max-width: 700px) {
  .step-header { flex-direction: column; gap: 0.75rem; }
  .top-save { align-items: flex-start; max-width: 100%; text-align: left; }
}

.save-bar {
  /* Save belongs to the end of the plan in normal flow; it does not overlay forms. */
  margin-top: 2rem;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 0.75rem 1rem;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: 1rem;
  box-shadow: var(--shadow-card);
}

.save-bar > .btn { justify-self: start; }
.plan-actions { display: flex; align-items: center; justify-content: flex-end; gap: 1rem; min-width: 0; }
.plan-actions > .next-action { flex: 0 0 auto; }
.save-controls { display: flex; align-items: center; gap: 1rem; min-width: 0; }
.save-controls > div { min-width: 0; overflow-wrap: anywhere; }
.save-controls > .btn { flex: 0 0 auto; }

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

@media (max-width: 700px) {
  .save-bar { display: flex; flex-wrap: wrap; }
  .plan-actions { flex: 1 1 22rem; flex-wrap: wrap; gap: 0.75rem; }
  .save-controls { flex: 1 1 14rem; flex-wrap: wrap; justify-content: flex-end; gap: 0.5rem 1rem; }
}
</style>

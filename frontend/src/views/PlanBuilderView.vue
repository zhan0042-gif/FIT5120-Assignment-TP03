<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { useHouseholdStore } from '../stores/household'
import ErrorState from '../components/common/ErrorState.vue'
import LoadingState from '../components/common/LoadingState.vue'
import ProgressBar from '../components/wizard/ProgressBar.vue'
import ReviewScreen from '../components/wizard/ReviewScreen.vue'
import SectionSummary from '../components/wizard/SectionSummary.vue'
import WizardShell from '../components/wizard/WizardShell.vue'
import { SECTIONS } from '../wizard/flow'
import { firstIncompleteSection, nextSectionKey, resolveSectionParam } from '../wizard/navigation'
import { describeSection } from '../wizard/summaries'
import { useWizard } from '../wizard/useWizard'
import { transportAt } from '../wizard/wizardDraft'
import { saveAndReview } from '../utils/planReviewNavigation'

const householdStore = useHouseholdStore()
const route = useRoute()
const router = useRouter()

const draft = ref(null)
const wizard = useWizard(draft)
const returnToReview = ref(false)
const saveMessage = ref(null)

function resetDraft() {
  // The wizard edits this detached aggregate. Restoring the server plan after a
  // load or save makes the unsaved comparison clean. JSON cloning is safe because
  // HouseholdPlan is JSON-serialisable data.
  draft.value = householdStore.plan ? JSON.parse(JSON.stringify(householdStore.plan)) : null
}

function chooseStartingStep() {
  const requested = resolveSectionParam(route.query.section)
  if (requested === 'review') return wizard.goTo('review')
  if (requested) return wizard.goToSection(requested)
  if (!householdStore.planExists) return wizard.goToSection(SECTIONS[0].id)
  const incomplete = firstIncompleteSection(householdStore.completion)
  if (incomplete) return wizard.goToSection(incomplete)
  return wizard.goTo(householdStore.completion ? 'review' : wizard.steps.value[0]?.key ?? 'review')
}

onMounted(async () => {
  window.addEventListener('beforeunload', warnBeforeUnload)
  if (householdStore.planStatus === 'idle') await householdStore.loadPlan()
  resetDraft()
  chooseStartingStep()
})

onBeforeUnmount(() => window.removeEventListener('beforeunload', warnBeforeUnload))

watch(
  () => householdStore.plan,
  () => {
    // A plan that arrives after mount (a retry after an error, or a load that
    // finished late) still opens at the right place.
    if (draft.value) return
    resetDraft()
    if (draft.value) chooseStartingStep()
  },
)

const hasUnsavedChanges = computed(() => {
  // A failed save leaves `householdStore.plan` unchanged, so the draft stays
  // dirty and can be retried without losing answers.
  if (!draft.value || !householdStore.plan) return false
  return JSON.stringify(draft.value) !== JSON.stringify(householdStore.plan)
})

function warnBeforeUnload(event) {
  if (!hasUnsavedChanges.value) return
  event.preventDefault()
  event.returnValue = ''
}

onBeforeRouteLeave(() => {
  if (!hasUnsavedChanges.value) return true
  return window.confirm('You have answers that are not saved yet. Leave this page anyway?')
})

const saving = computed(() => householdStore.saveStatus === 'loading')
const currentSection = computed(() => SECTIONS.find((section) => section.id === wizard.current.value?.section) ?? null)
const editableSections = computed(() => [...new Set(wizard.steps.value.filter((step) => step.kind === 'summary').map((step) => step.section))])
const sectionNeedsAttention = computed(() => {
  const status = householdStore.completion?.sections?.find((item) => item.section === currentSection.value?.id)?.status
  return status !== 'complete'
})

async function save() {
  if (!draft.value || saving.value) return false
  await householdStore.savePlan(draft.value)
  if (householdStore.saveStatus !== 'success') {
    saveMessage.value = householdStore.saveError || 'Your plan could not be saved. Please try again.'
    return false
  }
  saveMessage.value = null
  resetDraft()
  return true
}

async function saveSection() {
  const sectionId = wizard.current.value?.section
  if (!(await save())) return
  if (returnToReview.value) {
    returnToReview.value = false
    wizard.goTo('review')
    return
  }
  wizard.goTo(nextSectionKey(wizard.steps.value, sectionId))
}

function editSection(sectionId) {
  returnToReview.value = true
  saveMessage.value = null
  wizard.goToSection(sectionId)
}

function addVehicle() {
  // Starts the next vehicle's questions in the transport section; the backup
  // section afterwards then offers that vehicle.
  const next = draft.value.transports.length
  draft.value.has_private_transport = true
  transportAt(draft.value, next)
  wizard.goTo(`vehicle:${next}:type`)
}

function selectAddress(key, suggestion) {
  const step = wizard.current.value
  if (step?.key === key) step.select?.(draft.value, suggestion)
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
  <div class="plan-wizard">
    <ProgressBar
      :completion="householdStore.completion"
      :current-section="currentSection?.id ?? null"
      :loading="householdStore.completionStatus === 'loading'"
    />

    <div class="stage">
      <LoadingState v-if="householdStore.planStatus === 'loading' || householdStore.planStatus === 'idle'" message="Loading your household plan…" />
      <ErrorState
        v-else-if="householdStore.planStatus === 'error'"
        message="Could not load your household plan."
        @retry="householdStore.loadPlan"
      />

      <template v-else-if="draft && wizard.current.value">
        <p v-if="currentSection && wizard.current.value.kind !== 'review'" class="where">
          {{ currentSection.title }} · {{ SECTIONS.indexOf(currentSection) + 1 }} of {{ SECTIONS.length }}
        </p>

        <SectionSummary
          v-if="wizard.current.value.kind === 'summary'"
          :section="currentSection"
          :text="describeSection(draft, currentSection.id)"
          :needs-attention="sectionNeedsAttention && !hasUnsavedChanges"
          :saving="saving"
          :error="saveMessage"
          :is-edit="returnToReview"
          @save="saveSection"
          @back="wizard.back()"
        />

        <ReviewScreen
          v-else-if="wizard.current.value.kind === 'review'"
          :plan="draft"
          :completion="householdStore.completion"
          :completion-loading="householdStore.completionStatus === 'loading'"
          :editable="editableSections"
          :saving="saving"
          :error="saveMessage"
          @edit="editSection"
          @finish="reviewPlan"
        />

        <WizardShell
          v-else
          :key="wizard.current.value.key"
          :step="wizard.current.value"
          :plan="draft"
          :error="wizard.error.value"
          :can-go-back="wizard.currentIndex.value > 0"
          @submit="wizard.submit"
          @skip="wizard.skip"
          @back="wizard.back()"
          @remove="wizard.removeCurrent"
          @select="selectAddress"
          @add-vehicle="addVehicle"
        />
      </template>
    </div>
  </div>
</template>

<style scoped>
.plan-wizard { display: grid; gap: 1.75rem; margin: 0 auto; max-width: 44rem; width: 100%; }
.stage { background: var(--color-bg-card); border: var(--border-width) solid var(--color-border-strong); border-radius: 28px; box-shadow: var(--shadow-card); min-width: 0; padding: clamp(1.25rem, 4vw, 2.25rem); }
.where { color: var(--color-text-muted); font-size: 0.875rem; font-weight: 700; margin-bottom: 0.75rem; }
</style>

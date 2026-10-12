<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { useHouseholdStore } from '../stores/household'
import ErrorState from '../components/common/ErrorState.vue'
import LoadingState from '../components/common/LoadingState.vue'
import ProgressBar from '../components/wizard/ProgressBar.vue'
import ReviewScreen from '../components/wizard/ReviewScreen.vue'
import ScreenShell from '../components/wizard/ScreenShell.vue'
import DaytimeScreen from '../components/wizard/screens/DaytimeScreen.vue'
import HouseholdScreen from '../components/wizard/screens/HouseholdScreen.vue'
import JobsScreen from '../components/wizard/screens/JobsScreen.vue'
import PlacesScreen from '../components/wizard/screens/PlacesScreen.vue'
import VehiclesScreen from '../components/wizard/screens/VehiclesScreen.vue'
import { addJob, addMember } from '../wizard/formActions'
import { SCREENS, firstIncompleteScreen, nextScreen, previousScreen, resolveScreenParam } from '../wizard/screens'
import { finalisePlan, finalisedClone, validateScreen } from '../wizard/validation'
import { primaryDestination } from '../wizard/wizardDraft'
import { saveAndReview } from '../utils/planReviewNavigation'

const householdStore = useHouseholdStore()
const route = useRoute()
const router = useRouter()

const SCREEN_COMPONENTS = {
  household: HouseholdScreen,
  daytime: DaytimeScreen,
  vehicles: VehiclesScreen,
  places: PlacesScreen,
  jobs: JobsScreen,
}

const draft = ref(null)
const screenId = ref('review')
const returnToReview = ref(false)
const saveMessage = ref(null)
const errors = ref([])

function resetDraft() {
  // The wizard edits this detached aggregate. Restoring the server plan after a
  // load or save makes the unsaved comparison clean. JSON cloning is safe because
  // HouseholdPlan is JSON-serialisable data.
  draft.value = householdStore.plan ? JSON.parse(JSON.stringify(householdStore.plan)) : null
}

// A screen opens with its first card showing. These blank cards are dropped
// again by finalisePlan, so opening a screen is never an unsaved change.
function ensureFirstCards(plan, id) {
  if (id === 'household' && !plan.members.length) addMember(plan)
  if (id === 'places') primaryDestination(plan)
  if (id === 'jobs' && plan.members.length && !plan.responsibilities.length) addJob(plan)
}

function goTo(id) {
  errors.value = []
  if (id !== 'review' && draft.value) ensureFirstCards(draft.value, id)
  screenId.value = id
}

function chooseStartingStep() {
  const requested = resolveScreenParam(route.query.section)
  if (requested) return goTo(requested)
  if (!householdStore.planExists) return goTo(SCREENS[0].id)
  const incomplete = firstIncompleteScreen(householdStore.completion)
  if (incomplete) return goTo(incomplete)
  return goTo(householdStore.completion ? 'review' : SCREENS[0].id)
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
  // dirty and can be retried without losing answers. Blank cards do not count.
  if (!draft.value || !householdStore.plan) return false
  return JSON.stringify(finalisedClone(draft.value)) !== JSON.stringify(finalisedClone(householdStore.plan))
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
const currentScreen = computed(() => SCREENS.find((screen) => screen.id === screenId.value) ?? null)
const screenIndex = computed(() => SCREENS.findIndex((screen) => screen.id === screenId.value))
const errorMap = computed(() => Object.fromEntries(errors.value.map((item) => [item.field, item.message])))

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

async function saveScreen() {
  const id = screenId.value
  finalisePlan(draft.value)
  errors.value = validateScreen(draft.value, id)
  if (errors.value.length) {
    await nextTick()
    document.getElementById(errors.value[0].field)?.focus()
    return
  }
  if (!(await save())) return
  if (returnToReview.value) {
    returnToReview.value = false
    goTo('review')
    return
  }
  goTo(nextScreen(id))
}

function skip() {
  goTo(nextScreen(screenId.value))
}

function back() {
  if (returnToReview.value) {
    returnToReview.value = false
    goTo('review')
    return
  }
  goTo(previousScreen(screenId.value) ?? screenId.value)
}

function editScreen(id) {
  returnToReview.value = true
  saveMessage.value = null
  goTo(id)
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
      :current-screen="currentScreen?.id ?? null"
      :loading="householdStore.completionStatus === 'loading'"
    />

    <div class="stage">
      <LoadingState v-if="householdStore.planStatus === 'loading' || householdStore.planStatus === 'idle'" message="Loading your household plan…" />
      <ErrorState
        v-else-if="householdStore.planStatus === 'error'"
        message="Could not load your household plan."
        @retry="householdStore.loadPlan"
      />

      <template v-else-if="draft">
        <ReviewScreen
          v-if="screenId === 'review'"
          :plan="draft"
          :completion="householdStore.completion"
          :completion-loading="householdStore.completionStatus === 'loading'"
          :saving="saving"
          :error="saveMessage"
          @edit="editScreen"
          @finish="reviewPlan"
        />

        <ScreenShell
          v-else-if="currentScreen"
          :key="currentScreen.id"
          :screen="currentScreen"
          :position="screenIndex + 1"
          :total="SCREENS.length"
          :errors="errors"
          :save-error="saveMessage"
          :saving="saving"
          :is-edit="returnToReview"
          :can-go-back="returnToReview || screenIndex > 0"
          @save="saveScreen"
          @skip="skip"
          @back="back"
        >
          <component :is="SCREEN_COMPONENTS[currentScreen.id]" :plan="draft" :errors="errorMap" />
        </ScreenShell>
      </template>
    </div>
  </div>
</template>

<style scoped>
.plan-wizard { display: grid; gap: 1.75rem; margin: 0 auto; max-width: 44rem; width: 100%; }
.stage { background: var(--color-bg-card); border: var(--border-width) solid var(--color-border-strong); border-radius: 28px; box-shadow: var(--shadow-card); min-width: 0; padding: clamp(1.25rem, 4vw, 2.25rem); }
</style>

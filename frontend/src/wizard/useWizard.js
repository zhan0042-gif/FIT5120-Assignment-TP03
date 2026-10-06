import { computed, ref } from 'vue'
import { buildSteps } from './flow.js'
import { firstKeyOfSection, indexOfKey, keyAfterWrite, nextKey, previousKey } from './navigation.js'

function isEmptyAnswer(value) {
  if (value === null || value === undefined) return true
  if (typeof value === 'string') return value.trim() === ''
  if (Array.isArray(value)) return value.length === 0
  return false
}

export function useWizard(plan) {
  const currentKey = ref('review')
  const error = ref(null)

  const steps = computed(() => (plan.value ? buildSteps(plan.value) : []))
  const currentIndex = computed(() => Math.max(0, indexOfKey(steps.value, currentKey.value)))
  const current = computed(() => steps.value[currentIndex.value] ?? null)

  function goTo(key) {
    error.value = null
    currentKey.value = key
  }

  function goToSection(sectionId) {
    goTo(firstKeyOfSection(steps.value, sectionId))
  }

  function skip(forKey = currentKey.value) {
    if (current.value?.key !== forKey) return
    goTo(nextKey(steps.value, current.value.key))
  }

  function back() {
    if (!current.value) return
    goTo(previousKey(steps.value, current.value.key))
  }

  // `forKey` is the step the person was looking at when they acted. A second,
  // late activation of the same control targets a step that is no longer
  // current and must do nothing.
  function submit(forKey, value) {
    const step = current.value
    if (!step || step.key !== forKey) return false
    if (!step.write) {
      skip(forKey)
      return true
    }
    // Nothing typed into an empty optional field is just a skip. A required
    // description is validated instead, so Next explains what is missing.
    if (step.optional !== false && isEmptyAnswer(value) && isEmptyAnswer(step.read?.(plan.value))) {
      skip(forKey)
      return true
    }
    const message = step.validate?.(value, plan.value) ?? null
    error.value = message
    if (message) return false

    const index = currentIndex.value
    step.write(plan.value, value)
    goTo(keyAfterWrite(steps.value, step.key, index))
    return true
  }

  return { steps, current, currentIndex, currentKey, error, goTo, goToSection, skip, back, submit }
}

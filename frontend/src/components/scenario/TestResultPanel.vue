<script setup>
import { useRouter } from 'vue-router'
import { useVoiceCommands } from '../../voice/registry.js'
import { buttonTarget } from '../../voice/targets.js'
import { formatAustralianDateTime } from '../../utils/dateTime'
const props = defineProps({ result: { type: Object, required: true } })
const labels = { backup_transport: 'Backup transport', backup_driver: 'Eligible backup driver', backup_person: 'Different backup person', backup_destination: 'Backup destination' }
// Backend enums and reasons stay unchanged; this component maps them to concise,
// accessible user-facing labels and status styling.
const successReasons = {
  destination_unavailable: 'Your plan includes a backup destination that is different from the primary destination.',
  vehicle_unavailable: 'Your plan includes another recorded transport option and an eligible driver.',
  person_unavailable: 'Your important responsibilities have a different backup person.',
}
const planSectionTargets = {
  transport: 'transport',
  backup_transport: 'transport',
  primary_destination: 'destinations',
  backup_destination: 'destinations',
  responsibilities: 'responsibilities',
}
function editPlanTarget(result) {
  const section = planSectionTargets[result.first_problem?.section]
  return section ? { path: '/plan', query: { section } } : '/plan'
}
function failureReason(result) {
  if (result.scenario_id === 'person_unavailable') {
    return 'At least one responsibility does not have a different backup person assigned.'
  }
  return result.result_reason
}

const router = useRouter()

useVoiceCommands(() => (props.result.overall_status !== 'pass'
  ? [buttonTarget({ id: 'edit-my-plan', label: 'Edit my plan', press: () => router.push(editPlanTarget(props.result)) })]
  : []))
</script>
<template>
  <div class="result">
    <div class="result-heading" :class="result.overall_status === 'pass' ? 'is-success' : 'is-warning'">
      <span class="result-icon" aria-hidden="true">{{ result.overall_status === 'pass' ? '✓' : '!' }}</span>
      <h2>{{ result.overall_status === 'pass' ? 'Plan works for this scenario' : 'Plan needs attention' }}</h2>
    </div>
    <p class="reason">{{ result.overall_status === 'pass' ? (successReasons[result.scenario_id] ?? result.result_reason) : failureReason(result) }}</p>
    <div v-if="result.first_problem" class="problem"><p>{{ result.first_problem.message }}</p></div>
    <ul class="checks">
      <li v-for="check in result.checks" :key="check.check">
        <span>{{ labels[check.check] ?? 'Plan check' }}</span>
        <strong class="status-text" :class="check.status === 'pass' ? 'status-success' : check.status === 'fail' ? 'status-warning' : 'status-neutral'">
          <span aria-hidden="true">{{ check.status === 'pass' ? '✓' : check.status === 'fail' ? '!' : '–' }}</span>
          {{ check.status === 'pass' ? 'Available' : check.status === 'fail' ? 'Needs attention' : 'Not checked' }}
        </strong>
      </li>
    </ul>
    <p class="hint">Tested {{ formatAustralianDateTime(result.tested_at) }}</p>
    <router-link v-if="result.overall_status !== 'pass'" class="btn btn-accent action" :to="editPlanTarget(result)">Edit my plan</router-link>
  </div>
</template>
<style scoped>
.result-heading { align-items: center; border-radius: var(--radius); display: flex; gap: 0.65rem; padding: 0.75rem 0.9rem; }
.result-heading.is-success { background: var(--color-success-soft); color: var(--color-success); }
.result-heading.is-warning { background: var(--color-warning-soft); color: var(--color-warning); }
.result-icon { align-items: center; border: 2px solid currentColor; border-radius: 50%; display: inline-flex; flex: 0 0 auto; font-weight: 700; height: 1.5rem; justify-content: center; width: 1.5rem; }
h2 { font-size: 1.35rem; }.reason { color: var(--color-text-muted); margin-top: 0.75rem; }
.problem { background: var(--color-danger-soft); border-left: 4px solid var(--color-danger); border-radius: var(--radius); padding: 0.75rem 1rem; margin: 1rem 0; }
.checks { list-style: none; margin: 1rem 0; padding: 0; }.checks li { display: flex; justify-content: space-between; gap: 1rem; padding: 0.7rem 0; border-bottom: 1px solid var(--color-border); }
.hint { color: var(--color-text-muted); font-size: 0.875rem; }.action { display: inline-flex; margin-top: 1rem; text-decoration: none; }
</style>

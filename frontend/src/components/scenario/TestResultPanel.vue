<script setup>
import { formatAustralianDateTime } from '../../utils/dateTime'
const props = defineProps({ result: { type: Object, required: true } })
const labels = { backup_transport: 'Backup transport', backup_driver: 'Eligible backup driver', backup_person: 'Different backup person', backup_destination: 'Backup destination' }
const successReasons = {
  destination_unavailable: 'Your plan includes a backup destination that is different from the primary destination.',
  vehicle_unavailable: 'Your plan includes another recorded transport option and an eligible driver.',
  person_unavailable: 'Your important responsibilities have a different backup person.',
}
function failureReason(result) {
  if (result.scenario_id === 'person_unavailable') {
    return 'At least one responsibility does not have a different backup person assigned.'
  }
  return result.result_reason
}
</script>
<template>
  <div class="result">
    <h2>{{ result.overall_status === 'pass' ? 'Plan works for this scenario' : 'Needs attention' }}</h2>
    <p class="reason">{{ result.overall_status === 'pass' ? (successReasons[result.scenario_id] ?? result.result_reason) : failureReason(result) }}</p>
    <div v-if="result.first_problem" class="problem"><p>{{ result.first_problem.message }}</p></div>
    <ul class="checks">
      <li v-for="check in result.checks" :key="check.check"><span>{{ labels[check.check] ?? 'Plan check' }}</span><strong :class="check.status">{{ check.status === 'pass' ? 'Available' : check.status === 'fail' ? 'Needs attention' : 'Not checked' }}</strong></li>
    </ul>
    <p class="hint">Tested {{ formatAustralianDateTime(result.tested_at) }}</p>
    <router-link v-if="result.overall_status !== 'pass'" class="btn btn-primary action" to="/plan">Edit my plan</router-link>
  </div>
</template>
<style scoped>
h2 { font-size: 1.35rem; }.reason { color: var(--color-text-muted); margin-top: 0.5rem; }
.problem { background: var(--color-danger-soft); border-left: 4px solid var(--color-danger); border-radius: var(--radius); padding: 0.75rem 1rem; margin: 1rem 0; }
.checks { list-style: none; margin: 1rem 0; padding: 0; }.checks li { display: flex; justify-content: space-between; gap: 1rem; padding: 0.7rem 0; border-bottom: 1px solid var(--color-border); }
.pass { color: var(--color-success); }.fail { color: var(--color-danger); }.not_checked, .hint { color: var(--color-text-muted); }.hint { font-size: 0.875rem; }.action { display: inline-flex; margin-top: 1rem; text-decoration: none; }
</style>

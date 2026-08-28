<script setup lang="ts">
import type { TestResult } from '../../types/scenario'
import StatusBadge from '../common/StatusBadge.vue'
import { formatAustralianDateTime } from '../../utils/dateTime'

defineProps<{ result: TestResult }>()

const CHECK_LABELS: Record<string, string> = {
  backup_transport: 'Backup transport',
  backup_driver: 'Backup driver',
  backup_person: 'Backup person',
  backup_destination: 'Backup destination',
}

function checkLabel(check: string) {
  return CHECK_LABELS[check] ?? 'Plan check'
}
</script>

<template>
  <div class="result">
    <div class="result-header">
      <StatusBadge :status="result.overall_status" />
      <span class="hint">Tested {{ formatAustralianDateTime(result.tested_at) }}</span>
    </div>

    <p class="hint">{{ result.result_reason }}</p>

    <div v-if="result.first_problem" class="first-problem">
      <p class="eyebrow">First problem found</p>
      <p>{{ result.first_problem.message }}</p>
    </div>

    <ul class="checks">
      <li v-for="check in result.checks" :key="check.check" class="list-item">
        <span>{{ checkLabel(check.check) }}</span>
        <StatusBadge :status="check.status" />
      </li>
    </ul>
  </div>
</template>

<style scoped>
.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.hint {
  font-size: 0.8rem;
  color: var(--color-text-muted);
}

.first-problem {
  background: var(--color-danger-soft);
  border-left: 4px solid var(--color-danger);
  border-radius: var(--radius);
  padding: 0.75rem 1rem;
  margin-bottom: 1rem;
}

.checks {
  list-style: none;
  margin: 0;
  padding: 0;
}
</style>

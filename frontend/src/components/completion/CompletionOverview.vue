<script setup lang="ts">
import type { PlanCompletion } from '../../types/household'
import LoadingState from '../common/LoadingState.vue'
import StatusBadge from '../common/StatusBadge.vue'

defineProps<{ completion: PlanCompletion | null; loading: boolean }>()

const SECTION_LABELS: Record<string, string> = {
  household_profile: 'Household profile',
  transport: 'Transport',
  backup_transport: 'Backup transport',
  primary_destination: 'Primary destination',
  backup_destination: 'Backup destination',
  responsibilities: 'Responsibilities',
}
</script>

<template>
  <section class="card">
    <div class="card-header">
      <div>
        <h3 class="card-title">Plan completion & immediate checks</h3>
      </div>
      <StatusBadge v-if="completion" :status="completion.overall_status" />
    </div>

    <LoadingState v-if="loading" message="Checking plan completion and immediate checks…" />
    <template v-else-if="completion">
      <p class="section-label">Plan completion</p>
      <ul class="section-list">
        <li v-for="section in completion.sections" :key="section.section" class="list-item">
          <span>{{ SECTION_LABELS[section.section] ?? section.section }}</span>
          <StatusBadge :status="section.status" />
        </li>
      </ul>

      <p class="section-label immediate-heading">Immediate checks</p>
      <ul v-if="completion.immediate_checks.length" class="section-list">
        <li v-for="check in completion.immediate_checks" :key="`${check.check}-${check.message}`" class="list-item">
          <span>{{ check.message }}</span>
          <StatusBadge :status="check.status" />
        </li>
      </ul>
      <p v-else class="hint">No obvious arrangement issues were found in the current plan.</p>
    </template>
    <p v-else class="hint">Save your plan to see completion status and immediate checks.</p>
  </section>
</template>

<style scoped>
.section-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.section-label {
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.immediate-heading {
  margin-top: 1.25rem;
}

.hint {
  color: var(--color-text-muted);
  font-size: 0.85rem;
}
</style>

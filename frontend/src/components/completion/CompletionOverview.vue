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
        <p class="eyebrow">Epic 1 · US1.5</p>
        <h3 class="card-title">Plan completion overview</h3>
      </div>
      <StatusBadge v-if="completion" :status="completion.overall_status" />
    </div>

    <LoadingState v-if="loading" message="Checking plan completion…" />
    <ul v-else-if="completion" class="section-list">
      <li v-for="section in completion.sections" :key="section.section" class="list-item">
        <span>{{ SECTION_LABELS[section.section] ?? section.section }}</span>
        <StatusBadge :status="section.status" />
      </li>
    </ul>
    <p v-else class="hint">Save your plan to see a completion overview.</p>
  </section>
</template>

<style scoped>
.section-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.hint {
  color: var(--color-text-muted);
  font-size: 0.85rem;
}
</style>

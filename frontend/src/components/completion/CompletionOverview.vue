<script setup>
import LoadingState from '../common/LoadingState.vue'
defineProps({ completion: { type: Object, default: null }, loading: { type: Boolean, required: true } })
const labels = { household_profile: 'Household profile', member_locations: 'Member locations', transport: 'Transport', backup_transport: 'Backup transport', primary_destination: 'Primary destination', backup_destination: 'Backup destination', responsibilities: 'Responsibilities' }
</script>
<template>
  <section class="card completion-card">
    <h2 class="card-title">Plan completion</h2>
    <LoadingState v-if="loading" message="Checking plan completion..." />
    <template v-else-if="completion">
      <p class="summary"><strong>{{ completion.sections.filter((item) => item.status === 'complete').length }} of {{ completion.sections.length }} sections complete</strong></p>
      <ul class="sections">
        <li v-for="section in completion.sections" :key="section.section">
          <span class="indicator" :class="{ complete: section.status === 'complete' }" aria-hidden="true">{{ section.status === 'complete' ? '✓' : '' }}</span>
          <span>{{ labels[section.section] ?? section.section }}</span>
          <span class="status">{{ section.status === 'complete' ? 'Complete' : 'Needs attention' }}</span>
        </li>
      </ul>
    </template>
    <p v-else class="hint">Save your plan to see its completion status.</p>
    <router-link class="btn btn-accent edit-link" to="/plan">Edit my plan</router-link>
  </section>
</template>
<style scoped>
.summary { margin: 1rem 0 0.5rem; }
.sections { list-style: none; margin: 0; padding: 0; }
.sections li { display: grid; grid-template-columns: 1.35rem minmax(0, 1fr) auto; align-items: center; gap: 0.6rem; padding: 0.55rem 0; border-bottom: 1px solid var(--color-border); }
.indicator { border: 2px solid var(--color-border-strong); border-radius: 50%; display: inline-grid; place-items: center; width: 1.15rem; height: 1.15rem; font-size: 0.75rem; }
.indicator.complete { background: var(--color-success); border-color: var(--color-success); color: var(--color-text-inverse); }
.status { color: var(--color-text-muted); font-size: 0.9rem; }
.hint { color: var(--color-text-muted); margin-top: 1rem; }
.edit-link { display: inline-flex; margin-top: 1rem; text-decoration: none; }
</style>

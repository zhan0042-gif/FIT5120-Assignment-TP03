<script setup>
import LoadingState from '../common/LoadingState.vue'
defineProps({ completion: { type: Object, default: null }, loading: { type: Boolean, required: true } })
</script>

<template>
  <section class="card">
    <h3 class="card-title">Plan checks</h3>
    <LoadingState v-if="loading" message="Checking your saved plan..." />
    <template v-else-if="completion">
      <ul v-if="completion.immediate_checks.length" class="checks">
        <li v-for="check in completion.immediate_checks" :key="`${check.check}-${check.message}`">{{ check.message }}</li>
      </ul>
      <p v-else class="hint">No immediate issues found in the saved plan.</p>
    </template>
    <p v-else class="hint">Save your plan to see immediate checks.</p>
  </section>
</template>

<style scoped>
.card-title { margin-bottom: 0.75rem; }
.checks { margin: 0; padding-left: 1.25rem; }
.checks li + li { margin-top: 0.45rem; }
.hint { color: var(--color-text-muted); font-size: 0.9rem; }
</style>

<script setup>
defineProps({ scenarios: { type: Array, required: true }, selectedId: { type: String, default: null } })
const emit = defineEmits(['select'])
const copy = {
  vehicle_unavailable: { title: 'Primary transport unavailable', description: 'Check whether another recorded transport option and an eligible driver are available.', disabled: 'Add a primary transport to your plan before running this test.' },
  person_unavailable: { title: 'Primary responsible person unavailable', description: 'Check whether important responsibilities have a different backup person.', disabled: 'Add a primary responsible person to a responsibility before running this test.' },
  destination_unavailable: { title: 'Primary destination unavailable', description: 'Check whether another recorded destination is available.', disabled: 'Add a primary destination to your plan before running this test.' },
}
</script>
<template>
  <ul class="scenario-list">
    <li v-for="scenario in scenarios" :key="scenario.scenario_id">
      <button type="button" class="scenario-item" :class="{ 'is-selected': scenario.scenario_id === selectedId }" :disabled="!scenario.enabled" @click="emit('select', scenario.scenario_id)">
        <span class="title">{{ copy[scenario.scenario_id]?.title ?? scenario.title }}</span>
        <span class="description">{{ scenario.enabled ? (copy[scenario.scenario_id]?.description ?? scenario.description) : (copy[scenario.scenario_id]?.disabled ?? scenario.disabled_reason) }}</span>
      </button>
    </li>
  </ul>
</template>
<style scoped>
.scenario-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.5rem; }
.scenario-item { width: 100%; text-align: left; border: 1px solid var(--color-border); border-radius: var(--radius); background: #fff; padding: 0.9rem 1rem; cursor: pointer; display: flex; flex-direction: column; gap: 0.3rem; }
.scenario-item:disabled { cursor: not-allowed; opacity: 0.65; }
.title { font-weight: 600; }.description { color: var(--color-text-muted); font-size: 0.9rem; line-height: 1.45; }
.scenario-item.is-selected { border-color: var(--color-accent); background: var(--color-accent-soft); }.scenario-item.is-selected .description { color: var(--color-text); }
</style>

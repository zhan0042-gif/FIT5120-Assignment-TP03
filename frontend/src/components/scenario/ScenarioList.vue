<script setup lang="ts">
import type { Scenario, ScenarioId } from '../../types/scenario'

defineProps<{ scenarios: Scenario[]; selectedId: string | null }>()
const emit = defineEmits<{ select: [id: ScenarioId] }>()
</script>

<template>
  <ul class="scenario-list">
    <li v-for="scenario in scenarios" :key="scenario.scenario_id">
      <button
        type="button"
        class="scenario-item"
        :class="{ 'is-selected': scenario.scenario_id === selectedId }"
        :disabled="!scenario.enabled"
        :title="scenario.disabled_reason ?? undefined"
        @click="emit('select', scenario.scenario_id)"
      >
        <span class="title">{{ scenario.title }}</span>
        <span class="description">{{ scenario.disabled_reason ?? scenario.description }}</span>
      </button>
    </li>
  </ul>
</template>

<style scoped>
.scenario-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.scenario-item {
  width: 100%;
  text-align: left;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: #fff;
  padding: 0.75rem 1rem;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.scenario-item .title {
  font-weight: 600;
}

.scenario-item .description {
  font-size: 0.8rem;
  color: var(--color-text-muted);
}

.scenario-item.is-selected {
  border-color: var(--color-accent);
  background: var(--color-accent-soft);
}

.scenario-item.is-selected .description {
  color: var(--color-text);
}
</style>

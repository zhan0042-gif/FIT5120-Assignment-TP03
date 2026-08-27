<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useHouseholdStore } from '../stores/household'
import { useLocalContextStore } from '../stores/localContext'

const householdStore = useHouseholdStore()
const localContextStore = useLocalContextStore()

onMounted(() => {
  if (householdStore.planStatus === 'idle') householdStore.loadPlan()
})

const currentStage = computed(() => {
  if (householdStore.completion?.overall_status === 'complete') return 'test'
  return 'build'
})

const stages = [
  { key: 'build', label: 'Build Plan' },
  { key: 'test', label: 'Test & Strengthen' },
  { key: 'maintain', label: 'Maintain' },
]
</script>

<template>
  <div class="overview">
    <p class="eyebrow">Household plan</p>
    <h1 class="headline">Your bushfire plan, tested — not just written</h1>
    <p class="subhead">
      Firebreak helps households build a practical bushfire plan, test it against unexpected disruptions, and keep
      it current as circumstances change.
    </p>

    <section class="card">
      <div class="card-header">
        <h3 class="card-title">Your preparedness journey</h3>
      </div>
      <div class="journey">
        <div
          v-for="(stage, index) in stages"
          :key="stage.key"
          class="journey-stage"
          :class="{ 'is-current': stage.key === currentStage, 'is-done': stages.findIndex((s) => s.key === currentStage) > index }"
        >
          <span v-if="stage.key === currentStage" class="badge badge-accent journey-tag">Current</span>
          <div class="journey-bar" />
          <span class="journey-label">{{ stage.label }}</span>
        </div>
      </div>
    </section>

    <div class="feature-grid">
      <router-link to="/plan" class="card feature-card">
        <span class="feature-icon">▤</span>
        <h3 class="card-title">Plan builder</h3>
        <p>Build your household profile, primary and backup arrangements, and local bushfire context.</p>
        <span class="badge badge-neutral">Iteration 1</span>
      </router-link>
      <router-link to="/scenarios" class="card feature-card">
        <span class="feature-icon">▲</span>
        <h3 class="card-title">Scenario tester</h3>
        <p>Test your plan against relevant disruptions and see which arrangements still hold up.</p>
        <span class="badge badge-neutral">Iteration 1</span>
      </router-link>
      <router-link to="/review" class="card feature-card">
        <span class="feature-icon">◔</span>
        <h3 class="card-title">Review & reminders</h3>
        <p>Track improvements, re-test your plan, and keep household arrangements current.</p>
        <span class="badge badge-accent">Iteration 3</span>
      </router-link>
    </div>

    <section class="card callout">
      <p class="eyebrow">Why this exists</p>
      <p>Around 40% of surveyed residents in bushfire-prone areas do not have a bushfire plan.</p>
      <p>Research also suggests that providing preparedness information alone does not always lead to preparedness action.</p>
    </section>

    <p v-if="!localContextStore.submittedAddress" class="hint">
      Head to <router-link to="/plan">Plan builder</router-link> to add your address and start building your plan.
    </p>
  </div>
</template>

<style scoped>
.overview {
  max-width: 920px;
}

.headline {
  font-size: 2rem;
  margin: 0.5rem 0 0.75rem;
}

.subhead {
  color: var(--color-text-muted);
  max-width: 620px;
  margin-bottom: 2rem;
}

.journey {
  display: flex;
  gap: 1.5rem;
}

.journey-stage {
  flex: 1;
  position: relative;
}

.journey-tag {
  position: absolute;
  top: -1.6rem;
  left: 0;
}

.journey-bar {
  height: 8px;
  border-radius: 999px;
  background: var(--color-border);
}

.journey-stage.is-current .journey-bar {
  background: var(--color-accent);
}

.journey-stage.is-done .journey-bar {
  background: var(--color-success);
}

.journey-label {
  display: block;
  margin-top: 0.5rem;
  font-size: 0.8rem;
  color: var(--color-text-muted);
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1.25rem;
  margin: 1.75rem 0;
}

.feature-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.5rem;
  text-decoration: none;
  color: inherit;
  margin-top: 0;
}

.feature-icon {
  color: var(--color-accent);
  font-size: 1.1rem;
}

.callout {
  border-left: 4px solid var(--color-accent);
}

.callout p + p {
  margin-top: 0.4rem;
  color: var(--color-text-muted);
}

.hint {
  margin-top: 1.5rem;
  color: var(--color-text-muted);
}
</style>

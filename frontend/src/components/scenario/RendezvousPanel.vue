<script setup>
import { useVoiceCommands } from '../../voice/registry.js'
import { buttonTarget } from '../../voice/targets.js'
import { computed } from 'vue'
import { useHouseholdStore } from '../../stores/household'
import { useRendezvousStore } from '../../stores/rendezvous'

const householdStore = useHouseholdStore()
const rendezvousStore = useRendezvousStore()

const SECTION_LABELS = {
  household_profile: 'Household profile',
  member_locations: 'Member locations',
  transport: 'Transport',
  backup_transport: 'Backup transport',
  primary_destination: 'Primary destination',
  backup_destination: 'Backup destination',
  responsibilities: 'Responsibilities',
}

const ORIGIN_LABELS = { home: 'home', work: 'work', school: 'school', other: 'elsewhere' }

const result = computed(() => rendezvousStore.result)
const isReady = computed(() => result.value?.status === 'ready')

// Bars are scaled to the slowest journey, so the bottleneck reads as full width.
const longestSeconds = computed(() =>
  Math.max(1, ...(result.value?.member_etas ?? []).map((eta) => eta.travel_seconds)),
)

function minutes(seconds) {
  return `${Math.round(seconds / 60)} min`
}

function barWidth(seconds) {
  return `${Math.max(2, Math.round((seconds / longestSeconds.value) * 100))}%`
}

function run() {
  rendezvousStore.runSimulation(householdStore.householdId)
}

function explain() {
  rendezvousStore.requestExplanation(householdStore.householdId)
}

useVoiceCommands(() => {
  const targets = [buttonTarget({
    id: 'run-rendezvous',
    label: result.value ? 'Run again' : 'Run simulation',
    aliases: ['run the simulation'],
    disabled: rendezvousStore.status === 'loading',
    press: run,
  })]
  if (isReady.value && !rendezvousStore.explanation) {
    targets.push(buttonTarget({
      id: 'explain-rendezvous',
      label: 'Explain this result',
      disabled: rendezvousStore.explanationStatus === 'loading',
      press: explain,
    }))
  }
  return targets
})
</script>

<template>
  <section class="card rendezvous">
    <h2>How long until everyone is together?</h2>

    <p v-if="!result" class="subhead">
      Estimates how long each person takes to reach your primary destination from where
      they usually are during the day.
    </p>

    <template v-if="result?.status === 'not_applicable'">
      <p class="subhead">{{ result.unavailable_reason }}</p>
      <ul v-if="result.missing_sections.length" class="missing">
        <li v-for="section in result.missing_sections" :key="section">
          {{ SECTION_LABELS[section] ?? section }}
        </li>
      </ul>
      <p class="actions">
        <router-link class="btn btn-primary btn-sm" to="/plan">Finish my plan</router-link>
      </p>
    </template>

    <p v-else-if="result?.status === 'unavailable'" class="field-error">
      {{ result.unavailable_reason }}
    </p>

    <template v-else-if="isReady">
      <p class="headline-figure">
        Everyone together after
        <strong>{{ minutes(result.everyone_together_seconds) }}</strong>
        at {{ result.destination_name }}
      </p>

      <ul class="etas">
        <li v-for="eta in result.member_etas" :key="eta.member_id">
          <span class="eta-name">{{ eta.display_name || 'Unnamed member' }}</span>
          <span class="eta-origin">from {{ ORIGIN_LABELS[eta.origin_kind] ?? eta.origin_kind }}</span>
          <span class="eta-bar"><span :style="{ width: barWidth(eta.travel_seconds) }" /></span>
          <span class="eta-time">{{ minutes(eta.travel_seconds) }}</span>
        </li>
      </ul>

      <ul v-if="result.warnings.length" class="warnings">
        <li v-for="warning in result.warnings" :key="warning">⚠️ {{ warning }}</li>
      </ul>

      <p v-if="rendezvousStore.explanation" class="explanation">
        <span class="explanation-label">Generated summary</span>
        {{ rendezvousStore.explanation }}
      </p>

      <button
        v-else
        class="btn btn-ghost btn-sm explain-btn"
        type="button"
        :disabled="rendezvousStore.explanationStatus === 'loading'"
        @click="explain"
      >
        {{ rendezvousStore.explanationStatus === 'loading' ? 'Thinking…' : 'Explain this result' }}
      </button>

      <p class="caveat">
        An estimate against traffic at the time it was run, not a guarantee.
      </p>
    </template>

    <p v-if="rendezvousStore.error" class="field-error">{{ rendezvousStore.error }}</p>

    <button
      class="btn btn-accent"
      type="button"
      :disabled="rendezvousStore.status === 'loading'"
      @click="run"
    >
      {{ rendezvousStore.status === 'loading' ? 'Simulating…' : result ? 'Run again' : 'Run simulation' }}
    </button>
  </section>
</template>

<style scoped>
.rendezvous { margin-top: 1.5rem; }
.headline-figure { font-size: 1.15rem; margin: 0.5rem 0 1rem; }
.etas { list-style: none; margin: 0 0 1rem; padding: 0; }
.etas li {
  display: grid;
  grid-template-columns: minmax(4rem, 8rem) minmax(4rem, 6rem) minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.6rem;
  padding: 0.4rem 0;
}
.eta-name { font-weight: 600; }
.eta-origin { color: var(--color-text-muted); font-size: 0.85rem; }
.eta-bar { background: var(--color-bg-card-muted); border-radius: 999px; height: 0.6rem; min-width: 2rem; }
.eta-bar > span { background: var(--color-accent); border-radius: 999px; display: block; height: 100%; }
.eta-time { font-variant-numeric: tabular-nums; font-weight: 600; }
.warnings, .missing { list-style: none; margin: 0 0 1rem; padding: 0; }
.warnings li, .missing li { padding: 0.3rem 0; }
.actions { margin: 0 0 1rem; }
.caveat { color: var(--color-text-muted); font-size: 0.85rem; }
.explanation {
  background: var(--color-bg-card-muted);
  border-radius: var(--radius);
  padding: 0.75rem 0.9rem;
  margin: 0 0 1rem;
}
.explanation-label {
  color: var(--color-text-muted);
  display: block;
  font-size: 0.75rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.explain-btn { margin-bottom: 1rem; }

@media (max-width: 520px) {
  .etas li { grid-template-columns: minmax(0, 1fr) auto; }
  .eta-origin, .eta-bar { display: none; }
}
</style>

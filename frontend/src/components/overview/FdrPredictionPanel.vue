<script setup>
import { computed, ref } from 'vue'

import { useFdrPredictionStore } from '../../stores/fdrPrediction'


const fdrStore = useFdrPredictionStore()

const districts = [
  'Central',
  'East Gippsland',
  'Mallee',
  'North Central',
  'North East',
  'Northern Country',
  'South West',
  'South and West Gippsland',
  'Wimmera',
]

const district = ref('Central')
const date = ref('')

const probabilityText = computed(() => {
  const probability = fdrStore.result?.elevated_probability

  if (typeof probability !== 'number') {
    return 'Not available'
  }

  return `${(probability * 100).toFixed(1)}%`
})

async function submitPrediction() {
  await fdrStore.predict(
    district.value,
    date.value,
  )
}
</script>

<template>
  <section class="card fdr-panel" data-voice-section="fire-danger-patterns">
    <div class="panel-header">
      <div>
        <h2>Historical Fire Danger Pattern</h2>

        <p>
          Compare a Victorian fire district and time of year with historical
          Fire Danger Rating patterns.
        </p>
      </div>
    </div>

    <div class="form-grid">
      <label>
        <span>Fire district</span>

        <select v-model="district">
          <option
            v-for="item in districts"
            :key="item"
            :value="item"
          >
            {{ item }}
          </option>
        </select>
      </label>

      <label>
        <span>Date</span>

        <input
          v-model="date"
          type="date"
        />
      </label>
    </div>

    <button
      class="btn btn-accent"
      type="button"
      :disabled="
        !district ||
        !date ||
        fdrStore.status === 'loading'
      "
      @click="submitPrediction"
    >
      {{
        fdrStore.status === 'loading'
          ? 'Checking...'
          : 'Check historical pattern'
      }}
    </button>

    <p
      v-if="fdrStore.status === 'error'"
      class="field-error"
      role="alert"
    >
      {{ fdrStore.error }}
    </p>

    <div
      v-if="
        fdrStore.status === 'success' &&
        fdrStore.result
      "
      class="prediction-result"
      aria-live="polite"
    >
      <h3>
        Historical pattern:
        {{ fdrStore.result.prediction_label }}
      </h3>

      <dl>
        <div>
          <dt>District</dt>
          <dd>{{ fdrStore.result.district }}</dd>
        </div>

        <div>
          <dt>Date</dt>
          <dd>{{ fdrStore.result.date }}</dd>
        </div>

        <div>
          <dt>Elevated pattern score</dt>
          <dd>{{ probabilityText }}</dd>
        </div>
      </dl>

      <div class="meaning-note">
        <h4>What does this mean?</h4>

        <p>
          <strong>Moderate:</strong>
          More similar to historical days rated Moderate.
        </p>

        <p>
          <strong>Elevated:</strong>
          More similar to historical days rated High, Extreme or Catastrophic.
        </p>
      </div>

      <p class="disclaimer">
        This score reflects historical seasonal patterns. It is not a forecast
        of future fire danger or an official Fire Danger Rating forecast, and
        should not be used for emergency decisions.
      </p>
    </div>
  </section>
</template>

<style scoped>
.fdr-panel {
  margin-top: 1.25rem;
}

.panel-header {
  margin-bottom: 1rem;
}

.panel-header h2 {
  font-size: 1.35rem;
}

.panel-header p {
  color: var(--color-text-muted);
  margin-top: 0.4rem;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  margin-bottom: 1rem;
}

label {
  display: grid;
  gap: 0.4rem;
}

label span {
  color: var(--color-text);
  font-weight: 600;
}

select,
input {
  background: var(--color-bg-card);
  border: 2px solid var(--color-border-strong);
  border-radius: 12px;
  color: var(--color-text);
  padding: 0.7rem;
  width: 100%;
}

select option {
  background: var(--color-bg-card);
  color: var(--color-text);
}

.prediction-result {
  background: var(--color-bg-card-muted);
  border: 2px solid var(--color-border);
  border-radius: var(--radius);
  color: var(--color-text);
  margin-top: 1.25rem;
  padding: 1rem;
}

.prediction-result h3 {
  color: var(--color-text);
  margin-bottom: 0.85rem;
}

.prediction-result dl {
  margin: 0;
}

.prediction-result dl div {
  display: grid;
  grid-template-columns: minmax(12rem, 0.4fr) minmax(0, 1fr);
  gap: 1rem;
  padding: 0.45rem 0;
}

.prediction-result dt {
  color: var(--color-text-muted);
}

.prediction-result dd {
  color: var(--color-text);
  margin: 0;
}

.meaning-note {
  border-top: 1px solid var(--color-border);
  margin-top: 1rem;
  padding-top: 1rem;
}

.meaning-note h4 {
  color: var(--color-text);
  margin-bottom: 0.65rem;
}

.meaning-note p {
  color: var(--color-text-muted);
  margin: 0.4rem 0;
}

.meaning-note strong {
  color: var(--color-text);
}

.disclaimer {
  border-top: 1px solid var(--color-border);
  color: var(--color-text-muted);
  font-size: 0.9rem;
  margin-top: 1rem;
  padding-top: 1rem;
}

.field-error {
  margin-top: 0.75rem;
}

@media (max-width: 700px) {
  .form-grid {
    grid-template-columns: 1fr;
  }

  .prediction-result dl div {
    grid-template-columns: 1fr;
    gap: 0.15rem;
  }
}
</style>

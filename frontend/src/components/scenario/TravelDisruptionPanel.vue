<script setup>
import { computed } from 'vue'
import { useHouseholdStore } from '../../stores/household'
import { useTravelDisruptionsStore } from '../../stores/travelDisruptions'
import LoadingState from '../common/LoadingState.vue'
import ErrorState from '../common/ErrorState.vue'
import EmptyState from '../common/EmptyState.vue'
import {
  disruptionDetails,
  travelPlaceText,
  destinationAddress,
  disruptionStatus,
  travelDestinationGroups,
  uncheckedDestinations,
} from '../../utils/travelReadinessPresentation'

const householdStore = useHouseholdStore()
const disruptionStore = useTravelDisruptionsStore()

const result = computed(() => disruptionStore.result)
const unchecked = computed(() => uncheckedDestinations(householdStore.plan))

const destinationGroups = computed(() => travelDestinationGroups(result.value))

function loadDisruptions() {
  return disruptionStore.load(
    householdStore.householdId,
    10,
  )
}

function formatDateTime(value) {
  if (!value) return 'Not provided'

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return 'Not provided'
  }

  return new Intl.DateTimeFormat('en-AU', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

</script>

<template>
  <section class="card disruption-panel">
    <div class="panel-heading">
      <h2>Reported disruptions</h2>

      <button
        class="btn btn-accent btn-sm"
        type="button"
        :disabled="disruptionStore.status === 'loading'"
        @click="loadDisruptions"
      >
        {{
          disruptionStore.status === 'loading'
            ? 'Checking...'
            : disruptionStore.status === 'success'
              ? 'Check again'
              : 'Check disruptions'
        }}
      </button>
    </div>

    <LoadingState
      v-if="disruptionStore.status === 'loading'"
      message="Checking current road disruptions..."
    />

    <ErrorState
      v-else-if="disruptionStore.status === 'error'"
      :message="
        disruptionStore.error ||
        'Road-disruption information could not be loaded.'
      "
      @retry="loadDisruptions"
    />

    <EmptyState
      v-else-if="disruptionStore.status === 'idle'"
      title="Check travel conditions"
      message="Use current Victorian road-disruption information to see whether disruptions are reported near your evacuation destinations."
    />

    <EmptyState
      v-else-if="
        result &&
        result.status === 'not_applicable'
      "
      title="Destination information needed"
      :message="
        result.unavailable_reason ||
        'Add and verify an evacuation destination first.'
      "
    />

    <EmptyState
      v-else-if="
        result &&
        result.status === 'unavailable'
      "
      title="Road-disruption information unavailable"
      :message="
        result.unavailable_reason ||
        'Current road-disruption information could not be checked.'
      "
    />

    <div
      v-else-if="
        result &&
        result.status === 'available'
      "
      class="results"
    >
      <div
        v-for="destination in destinationGroups"
        :key="`${destination.type}-${destination.destination_id}`"
        class="destination-block"
      >
        <div class="destination-heading">
          <div>
            <span class="destination-type">
              {{ destination.type }}
            </span>

            <h3>
              {{ destination.destination_name }}
            </h3>
            <p v-if="destinationAddress(destination)" class="destination-address notranslate" translate="no">{{ destinationAddress(destination) }}</p>
          </div>

          <span
            class="count-badge"
            :class="{
              warning: destination.active_disruption_count > 0,
            }"
          >
            {{ destination.active_disruption_count }}
            {{
              destination.active_disruption_count === 1
                ? 'disruption'
                : 'disruptions'
            }}
          </span>
        </div>

        <p
          v-if="destination.active_disruption_count === 0"
          class="no-disruptions"
        >
          No nearby disruptions reported.
        </p>

        <div
          v-else
          class="disruption-list"
        >
          <article
            v-for="disruption in destination.disruptions"
            :key="disruption.disruption_id"
            class="disruption-item"
          >
            <div class="disruption-topline">
              <strong>
                {{
                  travelPlaceText(disruption.event_subtype ||
                  disruption.event_type ||
                  'Road disruption')
                }}
              </strong>

              <span v-if="Number.isFinite(disruption.distance_km)">
                {{ disruption.distance_km.toFixed(1) }} km away
              </span>
            </div>

            <p
              v-if="disruption.road_name"
              class="road-name"
            >
              {{ travelPlaceText(disruption.road_name) }}
            </p>

            <p v-if="disruptionStatus(disruption)" class="impact-status">{{ disruptionStatus(disruption) }}</p>

            <p v-if="disruptionDetails(disruption)" class="description">{{ disruptionDetails(disruption) }}</p>

            <p
              v-if="disruption.last_updated"
              class="updated"
            >
              Updated {{ formatDateTime(disruption.last_updated) }}
            </p>
          </article>
        </div>
      </div>

      <p class="disclaimer">
        {{ result.disclaimer }}
      </p>
    </div>

    <div v-if="unchecked.length && householdStore.planStatus === 'success'" class="unchecked-results">
      <div
        v-for="destination in unchecked"
        :key="`${destination.type}-${destination.destination_id}`"
        class="destination-block"
      >
        <span class="destination-type">{{ destination.type }}</span>
        <h3>{{ destination.destination_name }}</h3>
        <p v-if="destinationAddress(destination)" class="destination-address notranslate" translate="no">{{ destinationAddress(destination) }}</p>
        <p class="unchecked-message">Road disruption information cannot be checked because this destination does not have verified coordinates.</p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.disruption-panel {
  min-width: 0;
}

.panel-heading {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
  flex-wrap: wrap;
}

.panel-heading h2 {
  margin: 0;
  font-size: 1.25rem;
}

.results {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-top: 1.25rem;
}

.unchecked-results { display: flex; flex-direction: column; gap: 1rem; margin-top: 1.25rem; }

.destination-block {
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 1rem;
}

.destination-heading {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}

.destination-heading h3 {
  margin: 0.2rem 0 0;
}

.destination-heading > div { min-width: 0; }

.destination-type {
  color: var(--color-text-muted);
  font-size: 0.8rem;
}

.count-badge {
  white-space: nowrap;
  border-radius: 999px;
  padding: 0.35rem 0.65rem;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  font-size: 0.8rem;
}

.count-badge.warning {
  font-weight: 700;
}

.destination-address,
.updated,
.description {
  color: var(--color-text-muted);
  font-size: 0.85rem;
}

.impact-status { font-weight: 600; }
.unchecked-message { margin-bottom: 0; }

.no-disruptions {
  margin-bottom: 0;
}

.disruption-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 0.75rem;
}

.disruption-item {
  padding: 0.85rem;
  border-radius: 10px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  overflow-wrap: anywhere;
}

.disruption-item p {
  margin: 0.35rem 0 0;
}

.disruption-topline {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.disruption-topline span {
  color: var(--color-text-muted);
  font-size: 0.85rem;
  white-space: nowrap;
}

.road-name {
  font-weight: 600;
}

.disclaimer {
  color: var(--color-text-muted);
  font-size: 0.85rem;
  line-height: 1.5;
  margin-bottom: 0;
}

@media (max-width: 700px) {
  .panel-heading,
  .destination-heading,
  .disruption-topline {
    flex-direction: column;
  }

  .panel-heading .btn {
    width: 100%;
  }
}
</style>

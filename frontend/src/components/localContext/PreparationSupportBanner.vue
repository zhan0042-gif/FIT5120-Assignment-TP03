<script setup>
import { computed } from 'vue'
import { useLocalContextStore } from '../../stores/localContext'
import LoadingState from '../common/LoadingState.vue'
const store = useLocalContextStore()
const labels = { household_profile: 'Household profile', transport: 'Transport', backup_transport: 'Backup transport', primary_destination: 'Primary destination', backup_destination: 'Backup destination', responsibilities: 'Responsibilities' }
const reviewLabels = computed(() => (store.prepSupport?.sections_to_review ?? []).map((key) => labels[key] ?? key))
</script>
<template>
  <section class="card preparation-card" data-voice-section="preparation-status">
    <h2 class="card-title">Preparation status</h2>
    <LoadingState v-if="store.prepStatus === 'loading'" message="Checking current preparation advice..." />
    <template v-else-if="store.prepStatus === 'success' && store.prepSupport?.status === 'up_to_date'">
      <h3>No review needed right now</h3>
      <p>Based on the current official fire danger information, no additional review is recommended.</p>
    </template>
    <template v-else-if="store.prepStatus === 'success' && store.prepSupport?.status === 'review_recommended'">
      <h3>Review recommended</h3>
      <p>{{ store.prepSupport.message }}</p>
      <ul v-if="reviewLabels.length"><li v-for="label in reviewLabels" :key="label">{{ label }}</li></ul>
      <router-link class="btn btn-accent action" to="/plan">Review my plan</router-link>
    </template>
    <template v-else-if="store.prepStatus === 'idle' && !store.canLoadContext(store.location)">
      <h3>Preparation advice needs a verified location</h3>
      <p>Add and verify your household location to check current preparation advice.</p>
    </template>
    <template v-else-if="store.prepStatus === 'idle'">
      <h3>Preparation advice will be refreshed</h3>
      <p>Current advice will be checked against your saved location and latest plan.</p>
    </template>
    <template v-else>
      <h3>Preparation advice currently unavailable</h3>
      <p>Official fire danger information is currently unavailable, so FIREBREAK cannot provide a preparation recommendation right now.</p>
    </template>
  </section>
</template>
<style scoped>
h3 { font-size: 1.05rem; margin: 1rem 0 0.4rem; }
p { color: var(--color-text-muted); }
ul { margin-bottom: 0; padding-left: 1.25rem; }
.action { display: inline-flex; margin-top: 1rem; text-decoration: none; }
</style>

<script setup>
import { useHouseholdStore } from '../stores/household'
const householdStore = useHouseholdStore()
</script>

<template>
  <div class="welcome">
    <h1>Welcome to FIREBREAK</h1>
    <p class="intro">FIREBREAK helps households build a bushfire preparedness plan, view local bushfire information for their address, and check whether backup arrangements are available.</p>
    <template v-if="householdStore.householdId">
      <p>Continue your preparedness plan.</p>
      <div class="actions">
        <router-link class="btn btn-accent btn-large" to="/plan">Continue editing plan</router-link>
        <router-link class="btn btn-ghost btn-large" to="/overview">View overview</router-link>
      </div>
    </template>
    <template v-else>
      <p>No plan yet? Start with your household members, transport, destinations, and responsibilities.</p>
      <router-link class="btn btn-accent btn-large" to="/plan">Start my preparedness plan</router-link>
    </template>
  </div>
</template>

<style scoped>
.welcome { max-width: 780px; margin: clamp(3rem, 10vh, 7rem) auto 0; text-align: center; }
h1 { font-size: clamp(2.25rem, 6vw, 3.5rem); line-height: 1.15; margin-bottom: 1.25rem; }
.intro { color: var(--color-text-muted); font-size: 1.125rem; margin: 0 auto 2rem; max-width: 720px; }
.actions { display: flex; justify-content: center; gap: 0.75rem; margin-top: 1.25rem; }
.btn-large { display: inline-flex; align-items: center; justify-content: center; font-size: 0.95rem; margin-top: 1.25rem; min-height: 3rem; padding-inline: 1.4rem; text-decoration: none; }
.actions .btn-large { margin-top: 0; }
@media (max-width: 520px) { .actions { align-items: stretch; flex-direction: column; } }
</style>

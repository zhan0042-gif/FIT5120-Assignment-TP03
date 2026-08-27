<script setup lang="ts">
import { onMounted } from 'vue'
import { useLocalContextStore } from '../../stores/localContext'

const localContextStore = useLocalContextStore()

onMounted(() => {
  if (!localContextStore.context && localContextStore.submittedAddress) {
    localContextStore.init()
  }
})

const navItems = [
  { to: '/', label: 'Overview' },
  { to: '/plan', label: 'Plan builder' },
  { to: '/scenarios', label: 'Scenario tester' },
  { to: '/review', label: 'Review & reminders' },
]
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-top">
      <div class="logo">
        <span class="logo-dash">—</span>
        <span>FIREBREAK</span>
      </div>

      <nav class="nav">
        <router-link v-for="item in navItems" :key="item.to" :to="item.to" class="nav-item" active-class="is-active" exact-active-class="is-active">
          {{ item.label }}
        </router-link>
      </nav>
    </div>

    <div class="sidebar-bottom">
      <p class="location-address">{{ localContextStore.submittedAddress || 'Location not set' }}</p>
      <p v-if="localContextStore.context" class="location-tag">
        {{ localContextStore.context.bushfire_context.is_bushfire_prone_area ? 'Bushfire-prone area' : 'Not a bushfire-prone area' }}
      </p>
      <p v-else class="location-tag">Add your address in Plan builder</p>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  background: var(--color-bg-sidebar);
  color: var(--color-text-inverse);
  width: 240px;
  flex: 0 0 240px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 100vh;
  padding: 1.75rem 1.25rem;
}

.logo {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-family: var(--font-mono);
  font-weight: 700;
  letter-spacing: 0.06em;
  font-size: 0.95rem;
  margin-bottom: 2rem;
}

.logo-dash {
  color: var(--color-accent);
}

.nav {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.nav-item {
  display: block;
  padding: 0.65rem 0.75rem;
  border-radius: var(--radius);
  text-decoration: none;
  color: var(--color-text-inverse-muted);
  font-size: 0.85rem;
}

.nav-item:hover {
  background: var(--color-bg-sidebar-hover);
  color: var(--color-text-inverse);
}

.nav-item.is-active {
  background: var(--color-accent);
  color: #fff;
}

.sidebar-bottom {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: var(--color-text-inverse-muted);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  padding-top: 1rem;
}

.location-address {
  color: var(--color-text-inverse);
  margin-bottom: 0.25rem;
}
</style>

<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useLocalContextStore } from '../../stores/localContext'
import { useUiStore } from '../../stores/ui'

const localContextStore = useLocalContextStore()
const uiStore = useUiStore()
const route = useRoute()

onMounted(() => {
  if (!localContextStore.context && localContextStore.submittedAddress) {
    localContextStore.init()
  }
})

// Close the mobile drawer whenever the user navigates to a new page.
watch(
  () => route.fullPath,
  () => uiStore.closeMobileMenu(),
)

const navItems = [
  { to: '/', label: 'Overview', icon: '◆' },
  { to: '/plan', label: 'Plan builder', icon: '▤' },
  { to: '/scenarios', label: 'Scenario tester', icon: '▲' },
  { to: '/review', label: 'Review & reminders', icon: '◔' },
]
</script>

<template>
  <div v-if="uiStore.mobileMenuOpen" class="sidebar-backdrop" @click="uiStore.closeMobileMenu"></div>

  <aside class="sidebar" :class="{ 'is-collapsed': uiStore.sidebarCollapsed, 'is-open': uiStore.mobileMenuOpen }">
    <div class="sidebar-top">
      <div class="sidebar-top-row">
        <div class="logo">
          <span class="logo-dash">—</span>
          <span class="logo-text">FIREBREAK</span>
        </div>
        <button
          class="icon-btn collapse-btn"
          type="button"
          :aria-label="uiStore.sidebarCollapsed ? 'Expand menu' : 'Collapse menu'"
          @click="uiStore.toggleCollapsed"
        >
          {{ uiStore.sidebarCollapsed ? '»' : '«' }}
        </button>
        <button class="icon-btn close-btn" type="button" aria-label="Close menu" @click="uiStore.closeMobileMenu">✕</button>
      </div>

      <nav class="nav">
        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="nav-item"
          active-class="is-active"
          exact-active-class="is-active"
          :title="item.label"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          <span class="nav-label">{{ item.label }}</span>
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
  transition: width 0.2s ease;
  overflow: hidden;
}

.sidebar-top-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-bottom: 2rem;
}

.logo {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-family: var(--font-mono);
  font-weight: 700;
  letter-spacing: 0.06em;
  font-size: 0.95rem;
  flex: 1;
  min-width: 0;
  white-space: nowrap;
}

.logo-dash {
  color: var(--color-accent);
}

.icon-btn {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.18);
  color: var(--color-text-inverse-muted);
  border-radius: var(--radius);
  width: 1.9rem;
  height: 1.9rem;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 0.85rem;
}

.icon-btn:hover {
  color: var(--color-text-inverse);
  border-color: rgba(255, 255, 255, 0.4);
}

.close-btn {
  display: none;
}

.nav {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.65rem 0.75rem;
  border-radius: var(--radius);
  text-decoration: none;
  color: var(--color-text-inverse-muted);
  font-size: 0.85rem;
  white-space: nowrap;
}

.nav-icon {
  flex: 0 0 auto;
  width: 1.1rem;
  text-align: center;
  color: inherit;
}

.nav-label {
  overflow: hidden;
  text-overflow: ellipsis;
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
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Desktop: collapse to an icon rail. */
@media (min-width: 881px) {
  .sidebar.is-collapsed {
    width: 72px;
    flex-basis: 72px;
  }

  .sidebar.is-collapsed .logo-text,
  .sidebar.is-collapsed .nav-label,
  .sidebar.is-collapsed .sidebar-bottom {
    display: none;
  }

  .sidebar.is-collapsed .nav-item {
    justify-content: center;
    padding-inline: 0;
  }

  .sidebar.is-collapsed .sidebar-top-row {
    justify-content: center;
  }
}

/* Mobile: sidebar becomes an off-canvas drawer, opened via the top bar's hamburger button. */
@media (max-width: 880px) {
  .sidebar-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(10, 12, 16, 0.45);
    z-index: 40;
  }

  .sidebar {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    z-index: 50;
    width: 268px;
    flex-basis: 268px;
    transform: translateX(-100%);
    transition: transform 0.25s ease;
    box-shadow: 8px 0 24px rgba(0, 0, 0, 0.25);
  }

  .sidebar.is-open {
    transform: translateX(0);
  }

  /* Desktop collapse state is irrelevant once the sidebar is a drawer. */
  .sidebar.is-collapsed {
    width: 268px;
    flex-basis: 268px;
  }

  .sidebar.is-collapsed .logo-text,
  .sidebar.is-collapsed .nav-label,
  .sidebar.is-collapsed .sidebar-bottom {
    display: block;
  }

  .sidebar.is-collapsed .nav-item {
    justify-content: flex-start;
    padding-inline: 0.75rem;
  }

  .collapse-btn {
    display: none;
  }

  .close-btn {
    display: inline-flex;
  }
}
</style>

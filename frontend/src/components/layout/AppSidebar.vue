<script setup>
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
]
</script>

<template>
  <div v-if="uiStore.mobileMenuOpen" class="sidebar-backdrop" @click="uiStore.closeMobileMenu"></div>

  <aside class="sidebar" :class="{ 'is-collapsed': uiStore.sidebarCollapsed, 'is-open': uiStore.mobileMenuOpen }">
    <div class="sidebar-controls">
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
  height: 100%;
  min-height: 0;
  padding: 1.75rem 1.25rem;
  transition: width 0.2s ease;
  overflow-x: hidden;
  overflow-y: auto;
}

.sidebar-controls {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.4rem;
  flex: 0 0 auto;
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
  margin-top: 1rem;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.65rem 0.75rem;
  border-radius: var(--radius);
  text-decoration: none;
  color: var(--color-text-inverse-muted);
  font-size: 0.875rem;
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
  flex: 0 0 auto;
  margin-top: auto;
  font-family: var(--font-mono);
  font-size: 0.75rem;
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

  .sidebar.is-collapsed .nav-label,
  .sidebar.is-collapsed .sidebar-bottom {
    display: none;
  }

  .sidebar.is-collapsed .nav-item {
    justify-content: center;
    padding-inline: 0;
  }

  .sidebar.is-collapsed .sidebar-controls {
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

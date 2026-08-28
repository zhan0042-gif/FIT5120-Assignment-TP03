<script setup lang="ts">
import AppSidebar from './AppSidebar.vue'
import { useUiStore } from '../../stores/ui'

const uiStore = useUiStore()
</script>

<template>
  <div class="layout">
    <AppSidebar />
    <div class="main">
      <header class="mobile-topbar">
        <button class="menu-btn" type="button" aria-label="Open menu" @click="uiStore.openMobileMenu">☰</button>
        <div class="mobile-logo"><span class="logo-dash">—</span>FIREBREAK</div>
      </header>
      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  min-height: 100vh;
}

.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.mobile-topbar {
  display: none;
}

.content {
  flex: 1;
  min-width: 0;
  padding: 2.5rem 3rem;
}

@media (max-width: 880px) {
  .mobile-topbar {
    display: flex;
    align-items: center;
    gap: 0.85rem;
    padding: 0.85rem 1.25rem;
    background: var(--color-bg-sidebar);
    color: var(--color-text-inverse);
    position: sticky;
    top: 0;
    z-index: 30;
  }

  .menu-btn {
    background: transparent;
    border: 1px solid rgba(255, 255, 255, 0.25);
    color: inherit;
    border-radius: var(--radius);
    padding: 0.35rem 0.65rem;
    font-size: 1rem;
    line-height: 1;
    cursor: pointer;
  }

  .mobile-logo {
    font-family: var(--font-mono);
    font-weight: 700;
    letter-spacing: 0.06em;
    font-size: 0.9rem;
  }

  .logo-dash {
    color: var(--color-accent);
    margin-right: 0.35rem;
  }

  .content {
    padding: 1.5rem;
  }
}
</style>

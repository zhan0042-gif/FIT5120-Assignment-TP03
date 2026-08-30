<script setup lang="ts">
import AppSidebar from './AppSidebar.vue'
import { useUiStore } from '../../stores/ui'

const uiStore = useUiStore()
</script>

<template>
  <div class="layout">
    <AppSidebar />
    <div class="main">
      <header class="app-header">
        <button class="menu-btn" type="button" aria-label="Open menu" @click="uiStore.openMobileMenu">☰</button>
        <div class="app-brand">FIREBREAK</div>
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
  width: 100%;
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
}

.main {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.app-header {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  min-width: 0;
  padding: 1rem 3rem;
  background: var(--color-bg-card);
  border-bottom: 1px solid var(--color-border);
}

.app-brand {
  font-size: 1.75rem;
  font-weight: 700;
  letter-spacing: 0.035em;
  line-height: 1.15;
}

.menu-btn {
  display: none;
}

.content {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 2.5rem 3rem;
}

@media (max-width: 880px) {
  .app-header {
    gap: 0.85rem;
    padding: 0.8rem clamp(1rem, 4vw, 1.5rem);
    background: var(--color-bg-sidebar);
    color: var(--color-text-inverse);
  }

  .menu-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: 1px solid rgba(255, 255, 255, 0.25);
    color: inherit;
    border-radius: var(--radius);
    padding: 0.35rem 0.65rem;
    font-size: 1rem;
    line-height: 1;
    cursor: pointer;
  }

  .app-brand {
    font-size: 1.5rem;
  }

  .content {
    padding: clamp(1rem, 4vw, 1.5rem);
  }
}
</style>

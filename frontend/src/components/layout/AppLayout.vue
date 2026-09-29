<script setup>
import { ref } from 'vue'
import { setTheme } from '../../theme'

const theme = ref(document.documentElement.dataset.theme === 'light' ? 'light' : 'dark')

function toggleTheme() {
  theme.value = setTheme(theme.value === 'dark' ? 'light' : 'dark')
}
</script>

<template>
  <div class="layout">
    <header class="app-header">
      <div class="header-left">
        <router-link class="app-brand" to="/">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3c0 4-5 5-5 9a5 5 0 0 0 10 0c0-2-1-3-2-4"></path><path d="M12 21v-4"></path></svg>
          <span>FIREBREAK</span>
        </router-link>
        <div class="theme-control">
          <span>Theme</span>
          <button class="theme-toggle" type="button" :aria-label="`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`" @click="toggleTheme">
            {{ theme === 'dark' ? 'Light' : 'Dark' }}
          </button>
        </div>
      </div>
      <nav class="top-nav" aria-label="Primary navigation">
        <!-- Team-approved task order: edit, review status, then test the saved plan. -->
        <router-link to="/plan">My Plan</router-link>
        <router-link to="/overview">Overview</router-link>
        <router-link to="/map">Fire Map</router-link>
        <router-link to="/scenarios">Test My Plan</router-link>
      </nav>
    </header>
    <main class="content"><router-view /></main>
  </div>
</template>

<style scoped>
.layout { display: grid; grid-template-rows: auto minmax(0, 1fr); width: 100%; height: 100vh; height: 100dvh; overflow: hidden; }
.app-header { position: relative; z-index: 2; display: flex; align-items: center; justify-content: space-between; gap: 2rem; min-width: 0; padding: 1rem 3rem; background: var(--color-bg-content); border-bottom: 1px solid var(--color-border); }
.header-left { display: flex; align-items: center; flex: 0 0 auto; gap: clamp(0.75rem, 2vw, 1.5rem); min-width: 0; }
.app-brand { align-items: center; color: var(--color-accent); display: flex; font-size: 1.375rem; font-weight: 700; gap: 0.7rem; letter-spacing: 0.06em; line-height: 1.15; text-decoration: none; }
.app-brand span { color: var(--color-text); }
.theme-control { align-items: center; color: var(--color-text-muted); display: flex; font-size: 0.8125rem; gap: 0.4rem; white-space: nowrap; }
.top-nav { display: flex; align-items: center; flex: 0 1 auto; gap: clamp(0.75rem, 2.5vw, 2rem); margin-left: auto; min-width: 0; overflow-x: auto; }
.top-nav a { border-radius: var(--radius-pill); color: var(--color-text-muted); font-size: 0.9375rem; font-weight: 500; padding: 0.5rem 1rem; text-decoration: none; white-space: nowrap; }
.top-nav a:hover, .top-nav a:focus-visible { color: var(--color-text); }
.top-nav a.router-link-active { background: var(--color-accent-soft); color: var(--color-accent); font-weight: 700; }
.theme-toggle { flex: 0 0 auto; border: 1px solid var(--color-border-strong); border-radius: var(--radius-pill); background: var(--color-bg-card); color: var(--color-text); cursor: pointer; font-size: 0.8125rem; font-weight: 600; padding: 0.45rem 0.8rem; white-space: nowrap; }
.theme-toggle:hover { background: var(--color-bg-card-muted); }
.theme-toggle:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
.content { position: relative; z-index: 1; min-width: 0; min-height: 0; overflow-x: hidden; overflow-y: auto; padding: 2.5rem 3rem; }
@media (max-width: 880px) {
  .app-header { gap: 1rem; padding: 0.8rem clamp(1rem, 4vw, 1.5rem); }
  .app-brand { font-size: 1.1875rem; }
  .content { padding: clamp(1rem, 4vw, 1.5rem); }
}
@media (max-width: 600px) {
  .app-header { display: grid; grid-template-columns: minmax(0, 1fr); gap: 0.5rem; }
  .top-nav { grid-row: 2; gap: 1rem; margin-left: 0; width: 100%; }
  .top-nav a { font-size: 0.9rem; }
}
</style>

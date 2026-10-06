<script setup>
import { ref } from 'vue'

const main = ref(null)

function focusMain() {
  main.value?.focus()
}
</script>

<template>
  <div class="layout">
    <a class="skip-link" href="#main-content" @click.prevent="focusMain">Skip to main content</a>
    <header class="app-header">
      <div class="header-left">
        <router-link class="app-brand" to="/">
          <span class="brand-mark" aria-hidden="true"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3c0 4-5 5-5 9a5 5 0 0 0 10 0c0-2-1-3-2-4"></path><path d="M12 21v-4"></path></svg></span>
          <span class="brand-name">FIREBREAK</span>
        </router-link>
      </div>
      <nav class="top-nav" aria-label="Primary navigation">
        <!-- Edit, review, explore maps and travel conditions, then test the saved plan. -->
        <router-link to="/plan">My Plan</router-link>
        <router-link to="/overview">Overview</router-link>
        <router-link to="/safety-insights">Safety Insights</router-link>
        <router-link to="/map">Fire Map</router-link>
        <router-link to="/travel-readiness">Travel Readiness</router-link>
        <router-link to="/scenarios">Test My Plan</router-link>
      </nav>
    </header>
    <main id="main-content" ref="main" class="content" tabindex="-1"><router-view /></main>
  </div>
</template>

<style scoped>
.layout { position: relative; display: grid; grid-template-rows: auto minmax(0, 1fr); width: 100%; height: 100vh; height: 100dvh; overflow: hidden; }
.app-header { position: relative; z-index: 2; display: flex; align-items: center; justify-content: space-between; gap: 1.5rem; min-width: 0; margin: 1rem 3rem 0.5rem; padding: 0.6rem 0.75rem 0.6rem 1.1rem; background: var(--color-bg-card); border: var(--border-width) solid var(--color-border-strong); border-radius: var(--radius-lg); box-shadow: var(--shadow-card); }
.header-left { display: flex; align-items: center; flex: 0 0 auto; gap: clamp(0.75rem, 2vw, 1.5rem); min-width: 0; }
.app-brand { align-items: center; color: var(--color-text); display: flex; font-family: var(--font-display); font-size: 1.375rem; font-weight: 700; gap: 0.7rem; letter-spacing: 0.04em; line-height: 1.15; text-decoration: none; }
.brand-mark { align-items: center; background: var(--clay-pink); border: 2.5px solid var(--color-border-strong); border-radius: 12px; color: #2d3748; display: inline-flex; height: 2.5rem; justify-content: center; width: 2.5rem; }
.top-nav { display: flex; align-items: center; flex: 0 1 auto; gap: 0.35rem; margin-left: auto; min-width: 0; overflow-x: auto; padding: 0.25rem; }
.top-nav a { align-items: center; border: 2.5px solid transparent; border-radius: var(--radius); color: var(--color-text-muted); display: inline-flex; font-size: 0.9375rem; font-weight: 700; min-height: 2.75rem; padding: 0.4rem 1rem; text-decoration: none; white-space: nowrap; }
.top-nav a:hover, .top-nav a:focus-visible { background: var(--color-bg-card-muted); color: var(--color-text); }
.top-nav a.router-link-active { background: var(--clay-mint); border-color: var(--color-border-strong); color: #1a2433; font-weight: 800; }
.skip-link { background: var(--color-accent); border: 2.5px solid var(--color-border-strong); border-radius: var(--radius); color: var(--color-on-accent); font-weight: 800; left: 1rem; padding: 0.6rem 1rem; position: absolute; top: 0; transform: translateY(-120%); z-index: 10; }
.skip-link:focus-visible { transform: translateY(0.5rem); }
.content:focus { outline: none; }
.content { position: relative; z-index: 1; min-width: 0; min-height: 0; overflow-x: hidden; overflow-y: auto; padding: 2rem 3rem 2.5rem; }
@media (max-width: 880px) {
  .app-header { gap: 1rem; margin: 0.75rem clamp(0.75rem, 3vw, 1.25rem) 0.5rem; padding: 0.55rem 0.7rem; }
  .app-brand { font-size: 1.1875rem; }
  .content { padding: clamp(1rem, 4vw, 1.5rem); }
}
@media (max-width: 600px) {
  .app-header { display: grid; grid-template-columns: minmax(0, 1fr); gap: 0.5rem; }
  .top-nav { grid-row: 2; gap: 0.25rem; margin-left: 0; width: 100%; -webkit-mask-image: linear-gradient(to right, #000 calc(100% - 2rem), transparent); mask-image: linear-gradient(to right, #000 calc(100% - 2rem), transparent); padding-right: 2rem; }
  .top-nav a { font-size: 0.9rem; padding-inline: 0.85rem; }
}
</style>

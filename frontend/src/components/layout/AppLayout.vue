<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import VoiceButton from '../voice/VoiceButton.vue'
import { useVoiceCommands, useVoiceContext } from '../../voice/registry.js'
import { commandTarget, pageTarget } from '../../voice/targets.js'

const router = useRouter()
const route = useRoute()
// The page scrolls inside <main>, not the window: the layout fixes its height
// and hides window overflow.
const content = ref(null)

const PAGES = [
  ['page-home', 'Home', '/'],
  ['page-plan', 'My Plan', '/plan'],
  ['page-overview', 'Overview', '/overview'],
  ['page-map', 'Fire Map', '/map'],
  ['page-scenarios', 'Test My Plan', '/scenarios'],
]

function scrollByScreens(screens) {
  const main = content.value
  main?.scrollBy({ top: main.clientHeight * screens, behavior: 'smooth' })
}

function scrollToEnd(end) {
  const main = content.value
  main?.scrollTo({ top: end === 'top' ? 0 : main.scrollHeight, behavior: 'smooth' })
}

useVoiceContext(() => ({ page: typeof route.name === 'string' ? route.name : null }))

// Registered first, so these survive if a page offers more than the judge accepts.
useVoiceCommands(() => [
  ...PAGES.map(([id, label, path]) => pageTarget({ id, label, go: () => router.push(path) })),
  commandTarget({ id: 'go-back', label: 'go back', run: () => router.back() }),
  commandTarget({ id: 'scroll-down', label: 'scroll down', run: () => scrollByScreens(0.8) }),
  commandTarget({ id: 'scroll-up', label: 'scroll up', run: () => scrollByScreens(-0.8) }),
  commandTarget({ id: 'scroll-top', label: 'scroll to the top', run: () => scrollToEnd('top') }),
  commandTarget({ id: 'scroll-bottom', label: 'scroll to the bottom', run: () => scrollToEnd('bottom') }),
])
</script>

<template>
  <div class="layout">
    <header class="app-header">
      <router-link class="app-brand" to="/">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3c0 4-5 5-5 9a5 5 0 0 0 10 0c0-2-1-3-2-4"></path><path d="M12 21v-4"></path></svg>
        <span>FIREBREAK</span>
      </router-link>
      <nav class="top-nav" aria-label="Primary navigation">
        <!-- Team-approved task order: edit, review status, then test the saved plan. -->
        <router-link to="/plan">My Plan</router-link>
        <router-link to="/overview">Overview</router-link>
        <router-link to="/map">Fire Map</router-link>
        <router-link to="/scenarios">Test My Plan</router-link>
      </nav>
    </header>
    <main ref="content" class="content"><router-view /></main>
    <VoiceButton />
  </div>
</template>

<style scoped>
.layout { display: grid; grid-template-rows: auto minmax(0, 1fr); width: 100%; height: 100vh; height: 100dvh; overflow: hidden; }
.app-header { position: relative; z-index: 2; display: flex; align-items: center; justify-content: space-between; gap: 2rem; min-width: 0; padding: 1rem 3rem; background: var(--color-bg-content); border-bottom: 1px solid var(--color-border); }
.app-brand { align-items: center; color: var(--color-accent); display: flex; font-size: 1.375rem; font-weight: 700; gap: 0.7rem; letter-spacing: 0.06em; line-height: 1.15; text-decoration: none; }
.app-brand span { color: var(--color-text); }
.top-nav { display: flex; align-items: center; gap: clamp(0.75rem, 2.5vw, 2rem); }
.top-nav a { border-radius: var(--radius-pill); color: var(--color-text-muted); font-size: 0.9375rem; font-weight: 500; padding: 0.5rem 1rem; text-decoration: none; white-space: nowrap; }
.top-nav a:hover, .top-nav a:focus-visible { color: var(--color-text); }
.top-nav a.router-link-active { background: var(--color-accent-soft); color: var(--color-accent); font-weight: 700; }
.content { position: relative; z-index: 1; min-width: 0; min-height: 0; overflow-x: hidden; overflow-y: auto; padding: 2.5rem 3rem; }
@media (max-width: 880px) {
  .app-header { gap: 1rem; padding: 0.8rem clamp(1rem, 4vw, 1.5rem); }
  .app-brand { font-size: 1.1875rem; }
  .content { padding: clamp(1rem, 4vw, 1.5rem); }
}
@media (max-width: 600px) {
  .app-header { align-items: flex-start; flex-direction: column; }
  .top-nav { gap: 1rem; width: 100%; overflow-x: auto; }
  .top-nav a { font-size: 0.9rem; }
}
</style>

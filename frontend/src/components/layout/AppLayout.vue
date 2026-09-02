<template>
  <div class="layout">
    <header class="app-header">
      <router-link class="app-brand" to="/">FIREBREAK</router-link>
      <nav class="top-nav" aria-label="Primary navigation">
        <!-- Team-approved task order: edit, review status, then test the saved plan. -->
        <router-link to="/plan">My Plan</router-link>
        <router-link to="/overview">Overview</router-link>
        <router-link to="/scenarios">Test My Plan</router-link>
      </nav>
    </header>
    <main class="content"><router-view /></main>
  </div>
</template>

<style scoped>
.layout { display: grid; grid-template-rows: auto minmax(0, 1fr); width: 100%; height: 100vh; height: 100dvh; overflow: hidden; }
.app-header { display: flex; align-items: center; justify-content: space-between; gap: 2rem; min-width: 0; padding: 1rem 3rem; background: var(--color-bg-card); border-bottom: 1px solid var(--color-border); }
.app-brand { color: var(--color-text); font-size: 1.75rem; font-weight: 700; letter-spacing: 0.035em; line-height: 1.15; text-decoration: none; }
.top-nav { display: flex; align-items: center; gap: clamp(0.75rem, 2.5vw, 2rem); }
.top-nav a { border-bottom: 2px solid transparent; color: var(--color-text-muted); font-size: 1rem; font-weight: 600; padding: 0.45rem 0; text-decoration: none; white-space: nowrap; }
.top-nav a:hover, .top-nav a:focus-visible, .top-nav a.router-link-active { color: var(--color-accent); }
.top-nav a.router-link-active { border-bottom-color: var(--color-accent); }
.content { min-width: 0; min-height: 0; overflow-x: hidden; overflow-y: auto; padding: 2.5rem 3rem; }
@media (max-width: 880px) {
  .app-header { gap: 1rem; padding: 0.8rem clamp(1rem, 4vw, 1.5rem); }
  .app-brand { font-size: 1.5rem; }
  .content { padding: clamp(1rem, 4vw, 1.5rem); }
}
@media (max-width: 600px) {
  .app-header { align-items: flex-start; flex-direction: column; }
  .top-nav { gap: 1rem; width: 100%; overflow-x: auto; }
  .top-nav a { font-size: 0.9rem; }
}
</style>

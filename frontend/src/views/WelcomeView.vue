<script setup>
import { useHouseholdStore } from '../stores/household'
const householdStore = useHouseholdStore()
</script>

<template>
  <div class="welcome">
    <div class="hero">
      <div class="hero-copy">
        <span class="eyebrow-pill">For Victorian households</span>
        <h1>Find the gap in your bushfire plan.</h1>
        <p class="lede">One car. One driver. No second destination. Most plans have a gap, and most households never see it.</p>
        <div class="actions">
          <template v-if="householdStore.householdId">
            <router-link class="btn btn-accent btn-large" to="/plan">Continue my plan</router-link>
            <router-link class="btn btn-ghost btn-large" to="/map">See where I am</router-link>
          </template>
          <router-link v-else class="btn btn-accent btn-large" to="/plan">Start my plan</router-link>
        </div>
      </div>

      <section class="journey" aria-labelledby="journey-heading">
        <h2 id="journey-heading">How to use FIREBREAK</h2>
        <ol>
          <li><strong>Build your plan</strong><span>Add your household, transport, evacuation destinations and responsibilities.</span></li>
          <li><strong>Review your plan</strong><span>Check your saved plan and local preparedness information.</span></li>
          <li><strong>Explore your local fire history</strong><span>View historical bushfire activity near your household.</span></li>
          <li><strong>Test your plan</strong><span>Check possible weaknesses, travel readiness and current road disruptions.</span></li>
        </ol>
      </section>
    </div>

    <div class="beats">
      <div class="beat"><strong>Built from your plan</strong><span>People, animals, vehicles, drivers, destinations.</span></div>
      <div class="beat"><strong>Checked against official data</strong><span>Bushfire prone areas, CFA district, BOM fire danger.</span></div>
      <div class="beat"><strong>No account needed</strong><span>Start now, come back to it later.</span></div>
    </div>
  </div>
</template>

<style scoped>
.welcome { display: flex; flex-direction: column; gap: 3rem; margin: 0 auto; max-width: 1180px; padding-top: clamp(1.5rem, 5vh, 3.5rem); width: 100%; }
.hero { align-items: center; display: grid; gap: 3.5rem; grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr); }
.hero-copy { display: flex; flex-direction: column; gap: 1.5rem; }
.eyebrow-pill { align-self: flex-start; background: var(--color-accent-soft); border: 1px solid var(--color-accent); border-radius: var(--radius-pill); color: var(--color-accent); font-size: 0.8125rem; font-weight: 500; padding: 0.4rem 1rem; }
h1 { font-size: clamp(2.6rem, 5.4vw, 4.4rem); font-weight: 700; letter-spacing: -0.03em; line-height: 1.03; text-wrap: pretty; }
.lede { color: var(--color-text-muted); font-size: 1.1875rem; line-height: 1.55; max-width: 30rem; }
.actions { display: flex; flex-wrap: wrap; gap: 0.85rem; margin-top: 0.5rem; }
.btn-large { align-items: center; display: inline-flex; font-size: 1.0625rem; justify-content: center; min-height: 3.4rem; padding-inline: 2rem; text-decoration: none; }
.beats { border-top: 1px solid var(--color-border); display: grid; gap: 1.75rem; grid-template-columns: repeat(3, minmax(0, 1fr)); padding-top: 2rem; }
.beat { display: flex; flex-direction: column; gap: 0.4rem; }
.beat strong { color: var(--color-accent); font-size: 0.9375rem; }
.beat span { color: var(--color-text-muted); font-size: 0.9375rem; line-height: 1.5; }
.journey { background: var(--color-bg-card); border: 1px solid var(--color-border); border-radius: 24px; min-width: 0; padding: 1.5rem; }
.journey h2 { font-size: 1.25rem; margin-bottom: 1.25rem; }
.journey ol { counter-reset: journey; display: grid; gap: 1.1rem; list-style: none; margin: 0; padding: 0; }
.journey li { display: flex; flex-direction: column; gap: 0.25rem; min-width: 0; }
.journey li::before { color: var(--color-accent); content: counter(journey, decimal-leading-zero); counter-increment: journey; font-family: var(--font-mono); font-size: 0.8rem; font-weight: 700; }
.journey li span { color: var(--color-text-muted); font-size: 0.9rem; line-height: 1.5; }
@media (max-width: 900px) { .hero { grid-template-columns: 1fr; gap: 1.5rem; } .beats { grid-template-columns: 1fr; gap: 1.25rem; } .journey ol { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 520px) { .actions { flex-direction: column; align-items: stretch; } }
@media (max-width: 520px) { .journey { padding: 1rem; } .journey ol { column-gap: 0.75rem; row-gap: 0.85rem; } .journey li span { display: none; } .journey li strong { font-size: 0.875rem; line-height: 1.3; } }
</style>

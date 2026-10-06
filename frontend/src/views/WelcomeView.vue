<script setup>
import { useHouseholdStore } from '../stores/household'
const householdStore = useHouseholdStore()
</script>

<template>
  <div class="welcome">
    <div class="hero">
      <div class="hero-copy">
        <span class="eyebrow-pill"><span class="pill-dot" aria-hidden="true"></span>For Victorian households</span>
        <h1>Find the <span class="hl">gap</span> in your bushfire plan.</h1>
        <p class="lede">One car. One driver. No second destination. Most plans have a gap, and most households never see it.</p>
        <div class="actions">
          <template v-if="householdStore.householdId">
            <router-link class="btn btn-accent btn-large" to="/plan">Continue my plan</router-link>
            <router-link class="btn btn-primary btn-large" to="/map">See where I am</router-link>
          </template>
          <router-link v-else class="btn btn-accent btn-large" to="/plan">Start my plan</router-link>
        </div>
      </div>

      <section class="journey" aria-labelledby="journey-heading">
        <h2 id="journey-heading">How to use FIREBREAK</h2>
        <ol>
          <li><router-link to="/plan"><strong>Build your plan</strong></router-link><span>Answer one question at a time: who is in your household, how you would leave, where you would go and who does what. Skip anything and finish later.</span></li>
          <li><router-link to="/map"><strong>Learn about your area</strong></router-link><span>See past bushfire records near your home, historical fire danger patterns, and safety guidance reviewed against CFA's pages.</span></li>
          <li><router-link to="/travel-readiness"><strong>Check your routes</strong></router-link><span>View road routes to your saved destinations and any road disruptions reported near them.</span></li>
          <li><router-link to="/scenarios"><strong>Test your plan</strong></router-link><span>Try "what if" cases, such as your car being unavailable, and see whether you have a backup that works.</span></li>
          <li><router-link to="/scenarios"><strong>See how long until you meet</strong></router-link><span>Find out how long it would take everyone in your household to reach the same place, using road routes from where each person is.</span></li>
        </ol>
      </section>
    </div>

    <div class="beats">
      <div class="beat beat-pink"><strong>Built from your plan</strong><span>People, animals, vehicles, drivers, destinations.</span></div>
      <div class="beat beat-blue"><strong>Checked against official data</strong><span>Bushfire prone areas, CFA district, BOM fire danger.</span></div>
      <div class="beat beat-lavender"><strong>No account needed</strong><span>Start now, come back to it later.</span></div>
    </div>
  </div>
</template>

<style scoped>
.welcome { display: flex; flex-direction: column; gap: 3rem; margin: 0 auto; max-width: 1180px; padding: 0.5rem 0.4rem 1rem 0; width: 100%; }
.hero { align-items: center; display: grid; gap: 3.5rem; grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr); }
.hero-copy { display: flex; flex-direction: column; gap: 1.5rem; }
.eyebrow-pill { align-items: center; align-self: flex-start; background: var(--clay-mint); border: 2.5px solid var(--color-border-strong); border-radius: var(--radius-pill); color: #1a2433; display: inline-flex; font-size: 0.875rem; font-weight: 800; gap: 0.5rem; padding: 0.35rem 1rem; }
.pill-dot { background: #166534; border-radius: 50%; height: 0.55rem; width: 0.55rem; }
h1 { font-size: clamp(2.6rem, 5.4vw, 4.2rem); font-weight: 700; letter-spacing: -0.02em; line-height: 1.08; text-wrap: pretty; }
.hl { background: var(--clay-mint); border-radius: 16px; box-decoration-break: clone; -webkit-box-decoration-break: clone; color: #1a2433; padding: 0 0.22em; }
.lede { color: var(--color-text-muted); font-size: 1.25rem; line-height: 1.55; max-width: 30rem; }
.actions { display: flex; flex-wrap: wrap; gap: 1.1rem; margin-top: 0.5rem; }
.btn-large { align-items: center; display: inline-flex; font-size: 1.0625rem; justify-content: center; min-height: 3.4rem; padding-inline: 2rem; text-decoration: none; }
.beats { display: grid; gap: 1.5rem; grid-template-columns: repeat(3, minmax(0, 1fr)); }
.beat { border: 2.5px solid var(--color-border-strong); border-radius: var(--radius-lg); box-shadow: var(--shadow-btn); color: #2d3748; display: flex; flex-direction: column; gap: 0.4rem; padding: 1.1rem 1.25rem; }
.beat-pink { background: var(--clay-pink); }
.beat-blue { background: var(--clay-blue); }
.beat-lavender { background: var(--clay-lavender); }
.beat strong { color: #1a2433; font-family: var(--font-display); font-size: 1.1rem; }
.beat span { color: #2d3748; font-size: 0.9375rem; line-height: 1.5; }
.journey { background: var(--color-bg-card); border: var(--border-width) solid var(--color-border-strong); border-radius: 28px; box-shadow: var(--shadow-card); min-width: 0; padding: 1.75rem; }
.journey h2 { font-size: 1.4rem; margin-bottom: 1.25rem; }
.journey ol { counter-reset: journey; display: grid; gap: 1.1rem; list-style: none; margin: 0; padding: 0; }
.journey li { column-gap: 0.9rem; display: grid; grid-template-columns: 2.4rem minmax(0, 1fr); min-width: 0; row-gap: 0.15rem; }
.journey li::before { align-items: center; border: 2.5px solid var(--color-border-strong); border-radius: 12px; color: #1a2433; content: counter(journey); counter-increment: journey; display: inline-flex; font-family: var(--font-display); font-size: 1rem; font-weight: 700; grid-row: 1 / span 2; height: 2.4rem; justify-content: center; width: 2.4rem; }
.journey li:nth-child(1)::before { background: var(--clay-pink); }
.journey li:nth-child(2)::before { background: var(--clay-blue); }
.journey li:nth-child(3)::before { background: var(--clay-lavender); }
.journey li:nth-child(4)::before { background: var(--clay-mint); }
.journey li:nth-child(5)::before { background: var(--clay-pink); }
.journey li a { align-self: end; color: inherit; text-decoration: none; }
.journey li a:hover strong { text-decoration: underline; }
.journey li span { color: var(--color-text-muted); font-size: 0.9375rem; grid-column: 2; line-height: 1.5; }
@media (max-width: 900px) { .hero { grid-template-columns: 1fr; gap: 1.75rem; } .beats { grid-template-columns: 1fr; gap: 1.25rem; } }
@media (max-width: 520px) { .actions { flex-direction: column; align-items: stretch; } .journey { padding: 1.1rem; } .journey li span { display: none; } .journey li a { align-self: center; grid-row: 1 / span 2; } .journey li strong { font-size: 0.9375rem; line-height: 1.3; } }
</style>

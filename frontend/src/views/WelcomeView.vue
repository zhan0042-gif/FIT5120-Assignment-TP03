<script setup>
import { computed, onMounted, ref } from 'vue'
import { useHouseholdStore } from '../stores/household'
const householdStore = useHouseholdStore()

const EXAMPLE_GAPS = [
  'Primary transport unavailable',
  'Responsible person unavailable',
  'Destination unavailable',
]

// A missing plan settles completionStatus at 'idle' rather than 'success', so
// deriving "still loading" from store status alone gets stuck forever for that
// household. A local flag that flips once loadPlan()'s promise settles (any
// outcome) avoids reasoning about that combination.
const checkedCompletion = ref(false)

onMounted(async () => {
  if (householdStore.householdId && householdStore.completionStatus === 'idle') {
    await householdStore.loadPlan()
  }
  checkedCompletion.value = true
})

const previewLoading = computed(() => householdStore.householdId && !checkedCompletion.value)
const previewGaps = computed(
  () => householdStore.completion?.immediate_checks.slice(0, 3).map((check) => check.message) ?? [],
)
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
            <router-link class="btn btn-ghost btn-large" to="/overview">See where I am</router-link>
          </template>
          <router-link v-else class="btn btn-accent btn-large" to="/plan">Start my plan</router-link>
        </div>
      </div>

      <aside class="preview-card">
        <template v-if="!householdStore.householdId">
          <span class="preview-label">What a plan check looks like</span>
          <div
            v-for="(gap, index) in EXAMPLE_GAPS"
            :key="gap"
            class="preview-row"
            :class="{ 'is-lead': index === 0 }"
          >
            <span class="preview-name">{{ gap }}</span>
            <span class="preview-rank">{{ index + 1 }}</span>
          </div>
        </template>
        <template v-else-if="previewGaps.length">
          <span class="preview-label">From your latest check</span>
          <div
            v-for="(gap, index) in previewGaps"
            :key="gap"
            class="preview-row"
            :class="{ 'is-lead': index === 0 }"
          >
            <span class="preview-name">{{ gap }}</span>
            <span class="preview-rank">{{ index + 1 }}</span>
          </div>
        </template>
        <template v-else-if="!previewLoading && householdStore.completion">
          <span class="preview-label">From your latest check</span>
          <p class="preview-empty">No immediate gaps found in your last check.</p>
        </template>
        <template v-else-if="!previewLoading">
          <span class="preview-label">Ready when you are</span>
          <p class="preview-empty">Start your plan to see where the gaps are.</p>
        </template>
      </aside>
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
.preview-card { background: var(--color-bg-card); border: 1px solid var(--color-border); border-radius: 24px; display: flex; flex-direction: column; gap: 0.6rem; padding: 1.75rem; }
.preview-label { color: var(--color-warning); font-size: 0.8125rem; font-weight: 500; letter-spacing: 0.06em; margin-bottom: 0.35rem; text-transform: uppercase; }
.preview-row { align-items: center; background: var(--color-bg-card-muted); border-radius: var(--radius-lg); display: flex; gap: 1rem; justify-content: space-between; padding: 1.1rem 1.25rem; }
.preview-row.is-lead { background: var(--color-accent-soft); border: 1px solid var(--color-accent); }
.preview-name { font-size: 1.0625rem; font-weight: 500; }
.preview-row.is-lead .preview-name { font-weight: 700; }
.preview-rank { align-items: center; background: rgba(245, 239, 231, 0.12); border-radius: var(--radius-pill); color: var(--color-text-muted); display: inline-flex; font-size: 0.875rem; font-weight: 700; height: 1.65rem; justify-content: center; width: 1.65rem; }
.preview-row.is-lead .preview-rank { background: var(--color-accent); color: var(--color-text-inverse); }
.preview-empty { color: var(--color-text-muted); font-size: 1rem; margin: 0; }
.beats { border-top: 1px solid var(--color-border); display: grid; gap: 1.75rem; grid-template-columns: repeat(3, minmax(0, 1fr)); padding-top: 2rem; }
.beat { display: flex; flex-direction: column; gap: 0.4rem; }
.beat strong { color: var(--color-accent); font-size: 0.9375rem; }
.beat span { color: var(--color-text-muted); font-size: 0.9375rem; line-height: 1.5; }
@media (max-width: 900px) { .hero { grid-template-columns: 1fr; gap: 2.5rem; } .beats { grid-template-columns: 1fr; gap: 1.25rem; } }
@media (max-width: 520px) { .actions { flex-direction: column; align-items: stretch; } }
</style>

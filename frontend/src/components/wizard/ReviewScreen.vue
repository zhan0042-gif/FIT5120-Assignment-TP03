<script setup>
import { SECTIONS } from '../../wizard/flow'
import { describeSection } from '../../wizard/summaries'
import LoadingState from '../common/LoadingState.vue'
import PlanChecks from '../completion/PlanChecks.vue'

const props = defineProps({
  plan: { type: Object, required: true },
  completion: { type: Object, default: null },
  completionLoading: { type: Boolean, default: false },
  editable: { type: Array, default: () => [] },
  saving: { type: Boolean, default: false },
  error: { type: String, default: null },
})
const emit = defineEmits(['edit', 'finish'])

function statusOf(id) {
  return props.completion?.sections?.find((item) => item.section === id)?.status === 'complete'
}
</script>

<template>
  <section class="review" aria-labelledby="review-title">
    <h2 id="review-title" class="title">Your plan so far</h2>
    <p class="helper">Check each part. Use Edit to change anything.</p>

    <LoadingState v-if="completionLoading && !completion" message="Checking your saved plan…" />
    <ul class="rows">
      <li v-for="section in SECTIONS" :key="section.id" class="row">
        <div class="row-main">
          <h3 class="row-title">{{ section.title }}</h3>
          <p class="row-text">{{ describeSection(plan, section.id) }}</p>
        </div>
        <span class="badge" :class="statusOf(section.id) ? 'badge-success' : 'badge-warning'">
          {{ statusOf(section.id) ? 'Complete' : 'Needs information' }}
        </span>
        <button v-if="editable.includes(section.id)" type="button" class="btn btn-ghost btn-sm" @click="emit('edit', section.id)">Edit</button>
      </li>
    </ul>

    <PlanChecks :completion="completion" :loading="completionLoading" />

    <p v-if="error" class="field-error" role="alert">{{ error }}</p>
    <div class="controls">
      <button type="button" class="btn btn-accent" :disabled="saving" @click="emit('finish')">Save &amp; Review Plan</button>
    </div>
  </section>
</template>

<style scoped>
.review { display: grid; gap: 1rem; }
.title { font-size: clamp(1.6rem, 4vw, 2.25rem); }
.helper { color: var(--color-text-muted); }
.rows { display: grid; gap: 0.75rem; list-style: none; margin: 0; padding: 0; }
.row { align-items: center; background: var(--color-bg-card); border: 2px solid var(--color-border-strong); border-radius: 16px; display: grid; gap: 0.5rem 1rem; grid-template-columns: minmax(0, 1fr) auto auto; padding: 0.9rem 1rem; }
.row-title { font-size: 1.0625rem; }
.row-text { color: var(--color-text-muted); font-size: 0.9375rem; overflow-wrap: anywhere; }
.controls { display: flex; justify-content: flex-end; margin-top: 0.5rem; }
@media (max-width: 600px) { .row { grid-template-columns: minmax(0, 1fr) auto; } .row .btn { grid-column: 1 / -1; justify-self: start; } }
</style>

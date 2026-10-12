<script setup>
import { computed } from 'vue'
import { SCREENS, screenComplete } from '../../wizard/screens'

const props = defineProps({
  completion: { type: Object, default: null },
  currentScreen: { type: String, default: null },
  loading: { type: Boolean, default: false },
})

const statuses = computed(() =>
  SCREENS.map((screen) => ({
    ...screen,
    complete: screenComplete(props.completion, screen.id),
    current: screen.id === props.currentScreen,
  })),
)
const done = computed(() => statuses.value.filter((item) => item.complete).length)
const total = SCREENS.length
const text = computed(() => `${done.value} of ${total} parts complete`)
</script>

<template>
  <div class="progress" :aria-busy="loading">
    <div class="progress-head">
      <strong>{{ text }}</strong>
    </div>
    <div
      class="bar"
      role="progressbar"
      aria-label="Plan completion"
      aria-valuemin="0"
      :aria-valuemax="total"
      :aria-valuenow="done"
      :aria-valuetext="text"
    >
      <span class="fill" :style="{ width: `${(done / total) * 100}%` }"></span>
    </div>
    <ol class="markers">
      <li v-for="item in statuses" :key="item.id" :class="{ 'is-complete': item.complete, 'is-current': item.current }" :aria-current="item.current ? 'step' : undefined">
        <span class="dot" aria-hidden="true">{{ item.complete ? '✓' : '' }}</span>
        <span class="name">{{ item.short }}</span>
        <span class="sr-only">{{ item.complete ? 'Complete' : 'Needs information' }}</span>
      </li>
    </ol>
  </div>
</template>

<style scoped>
.progress { display: grid; gap: 0.6rem; }
.progress-head { font-size: 0.9375rem; }
.bar { background: var(--color-bg-card-muted); border: 2px solid var(--color-border-strong); border-radius: 999px; height: 1rem; overflow: hidden; }
.fill { background: var(--color-accent); display: block; height: 100%; transition: width 0.3s ease; }
.markers { display: grid; gap: 0.35rem; grid-template-columns: repeat(5, minmax(0, 1fr)); list-style: none; margin: 0; padding: 0; }
.markers li { align-items: center; color: var(--color-text-muted); display: flex; flex-direction: column; font-size: 0.75rem; gap: 0.2rem; text-align: center; }
.dot { align-items: center; background: var(--color-bg-card); border: 2px solid var(--color-border-strong); border-radius: 50%; display: inline-flex; font-size: 0.75rem; font-weight: 800; height: 1.3rem; justify-content: center; width: 1.3rem; }
.is-complete .dot { background: var(--color-success); border-color: var(--color-success); color: var(--color-text-inverse); }
.is-current { color: var(--color-text); font-weight: 800; }
.is-current .dot { background: var(--color-accent); border-color: var(--color-border-strong); }
@media (max-width: 600px) { .name { display: none; } }
</style>

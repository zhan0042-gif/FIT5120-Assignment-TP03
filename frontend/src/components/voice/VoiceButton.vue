<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useVoiceStore } from '../../stores/voice'

const voice = useVoiceStore()
const supported = voice.isSupported()
const active = computed(() => voice.status !== 'idle')
const label = computed(() => (active.value ? 'Stop voice control' : 'Start voice control'))

// When a session ends, its last message stays briefly so a reason such as a
// blocked microphone can be read, then the panel closes.
const lingering = ref(false)
let lingerTimer
watch(active, (isActive) => {
  clearTimeout(lingerTimer)
  lingering.value = !isActive && Boolean(voice.message)
  if (lingering.value) lingerTimer = setTimeout(() => { lingering.value = false }, 6000)
})

onBeforeUnmount(() => {
  clearTimeout(lingerTimer)
  if (active.value) voice.endSession()
})
</script>

<template>
  <div class="voice">
    <section v-if="active || lingering" class="voice-panel" aria-live="polite">
      <p v-if="voice.interim" class="voice-interim">{{ voice.interim }}…</p>
      <p v-else-if="active && voice.heard" class="voice-heard">“{{ voice.heard }}”</p>
      <p v-if="voice.status === 'judging'" class="voice-working">Working…</p>
      <p v-if="voice.prompt" class="voice-prompt">{{ voice.prompt }}</p>
      <ol v-if="voice.suggestions.length" class="voice-suggestions">
        <li v-for="suggestion in voice.suggestions" :key="suggestion">{{ suggestion }}</li>
      </ol>
      <p v-if="voice.message" class="voice-message">{{ voice.message }}</p>
    </section>
    <button
      type="button"
      class="voice-button"
      :class="{ 'is-active': active }"
      :disabled="!supported"
      :aria-pressed="active"
      :aria-label="label"
      :title="supported ? label : 'Voice control needs Chrome or Edge'"
      @click="voice.toggle()"
    >
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <rect x="9" y="3" width="6" height="11" rx="3"></rect>
        <path d="M5 11a7 7 0 0 0 14 0"></path>
        <path d="M12 18v3"></path>
      </svg>
    </button>
  </div>
</template>

<style scoped>
/* Raised above the plan builder's save bar so it never covers Save plan. */
.voice { position: fixed; right: 1.5rem; bottom: 6.5rem; z-index: 30; display: flex; flex-direction: column; align-items: flex-end; gap: 0.75rem; pointer-events: none; }
.voice > * { pointer-events: auto; }
.voice-panel { width: min(22rem, calc(100vw - 3rem)); padding: 0.9rem 1rem; border: 1px solid var(--color-border); border-radius: var(--radius-lg); background: var(--color-bg-card); box-shadow: 0 10px 28px rgba(0, 0, 0, 0.16); }
.voice-panel p { margin: 0; }
.voice-panel > * + * { margin-top: 0.5rem; }
.voice-interim, .voice-working { color: var(--color-text-muted); }
.voice-heard { font-style: italic; }
.voice-prompt { font-weight: 600; }
.voice-suggestions { margin-bottom: 0; padding-left: 1.25rem; }
.voice-button { display: grid; place-items: center; width: 3.25rem; height: 3.25rem; border: 1px solid var(--color-border); border-radius: var(--radius-pill); background: var(--color-bg-card); color: var(--color-accent); box-shadow: 0 6px 18px rgba(0, 0, 0, 0.18); cursor: pointer; }
.voice-button.is-active { background: var(--color-accent); border-color: var(--color-accent); color: var(--color-bg-card); }
.voice-button:disabled { cursor: not-allowed; opacity: 0.5; }
.voice-button:focus-visible { outline: 3px solid var(--color-accent-soft); outline-offset: 2px; }
@media print { .voice { display: none; } }
</style>

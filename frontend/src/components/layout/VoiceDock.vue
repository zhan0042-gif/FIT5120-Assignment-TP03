<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useVoiceStore } from '../../stores/voice'

const route = useRoute()
const store = useVoiceStore()

// Most voice actions move the person to another page. The microphone must never be
// live without a visible way to stop it, so while a session is on, every page except
// Safety Insights (whose safety chat has its own control) shows a small stop bar and the
// "check the figures" notice.
const active = computed(() => ['connecting', 'listening', 'checking', 'closing'].includes(store.status))
const visible = computed(() => active.value && route.name !== 'safety-insights')
const stopping = computed(() => store.status === 'connecting' || store.status === 'closing')
</script>

<template>
  <aside v-if="visible" class="voice-dock" aria-label="Voice assistant">
    <p class="dock-status" role="status" aria-live="polite">Voice is on.</p>
    <button class="dock-stop" type="button" :disabled="stopping" @click="store.stop()">Stop voice</button>
    <p v-if="store.notice" class="dock-notice" role="alert">{{ store.notice }}</p>
  </aside>
</template>

<style scoped>
.voice-dock { align-items: center; background: var(--color-bg-card); border: var(--border-width) solid var(--color-border-strong); border-radius: var(--radius-lg); bottom: 1rem; box-shadow: var(--shadow-card); display: flex; flex-wrap: wrap; gap: 0.5rem 0.75rem; max-width: min(28rem, calc(100vw - 2rem)); padding: 0.6rem 0.9rem; position: fixed; right: 1rem; z-index: 5; }
.dock-status { font-size: 0.9375rem; font-weight: 600; margin: 0; }
.dock-stop { background: var(--color-accent); border: 1px solid var(--color-accent); border-radius: 999px; color: var(--color-on-accent); cursor: pointer; font: inherit; font-size: 0.9375rem; font-weight: 600; min-height: 2.75rem; padding: 0.45rem 1.25rem; }
.dock-stop:disabled { cursor: not-allowed; opacity: 0.6; }
.dock-notice { flex-basis: 100%; font-size: 0.9rem; font-weight: 700; margin: 0; }
</style>

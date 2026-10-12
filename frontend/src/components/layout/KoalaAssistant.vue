<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useVoiceStore } from '../../stores/voice'
import { MINIMIZED_KEY, bubbleFor, forcesOpen, isBusy, isLive, labelFor } from '../../voice/koalaControls'
import KoalaFigure from './KoalaFigure.vue'

const router = useRouter()
const store = useVoiceStore()

// Where the microphone API exists (HTTPS or localhost). Elsewhere the koala stays but cannot start voice.
const supported =
  typeof window !== 'undefined' &&
  'RTCPeerConnection' in window &&
  Boolean(globalThis.navigator?.mediaDevices?.getUserMedia)

function readMinimized() {
  try {
    return globalThis.localStorage?.getItem(MINIMIZED_KEY) === '1'
  } catch {
    return false
  }
}

function saveMinimized(value) {
  try {
    globalThis.localStorage?.setItem(MINIMIZED_KEY, value ? '1' : '0')
  } catch {
    // A private window or blocked storage: the choice just is not remembered.
  }
}

const minimized = ref(readMinimized())

const mustStayOpen = computed(() => forcesOpen({ status: store.status, error: store.error, notice: store.notice }))
const showMinimized = computed(() => minimized.value && !mustStayOpen.value)
const live = computed(() => isLive(store.status))
const disabled = computed(() => !supported || isBusy(store.status))
const label = computed(() => labelFor(store.status))
const bubble = computed(() =>
  bubbleFor({ supported, status: store.status, error: store.error, notice: store.notice }),
)

function toggle() {
  if (live.value) store.stop()
  else store.start({ router })
}

function minimize() {
  minimized.value = true
  saveMinimized(true)
}

function restore() {
  minimized.value = false
  saveMinimized(false)
}
</script>

<template>
  <aside class="koala" :class="{ small: showMinimized }" aria-label="Voice assistant">
    <button v-if="showMinimized" class="koala-chip" type="button" aria-label="Show the assistant" @click="restore">
      <KoalaFigure face="neutral" :talking="false" />
    </button>

    <template v-else>
      <div v-if="bubble.text" :key="bubble.role" class="koala-bubble" :class="bubble.role" :role="bubble.role" :aria-live="bubble.role === 'status' ? 'polite' : undefined">
        <span>{{ bubble.text }}</span>
        <button v-if="bubble.role === 'alert'" class="koala-dismiss" type="button" aria-label="Dismiss message" @click="store.dismissMessage()">×</button>
      </div>
      <div class="koala-row">
        <button
          v-if="!mustStayOpen"
          class="koala-min"
          type="button"
          aria-label="Hide the assistant"
          @click="minimize"
        >
          –
        </button>
        <button
          class="koala-button"
          type="button"
          :aria-label="label"
          :aria-pressed="live ? 'true' : 'false'"
          :title="label"
          :disabled="disabled"
          @click="toggle"
        >
          <KoalaFigure :face="store.face" :talking="store.talking" />
        </button>
      </div>
    </template>
  </aside>
</template>

<style scoped>
.koala { align-items: flex-end; bottom: 1rem; display: flex; flex-direction: column; gap: 0.5rem; max-width: min(18rem, calc(100vw - 2rem)); pointer-events: none; position: fixed; right: 1rem; z-index: 6; }
.koala > * { pointer-events: auto; }
.koala-row { align-items: flex-start; display: flex; gap: 0.35rem; }
.koala-button { background: transparent; border: 0; border-radius: 50%; cursor: pointer; height: 7rem; padding: 0; width: 7rem; }
.koala-button:focus-visible, .koala-chip:focus-visible, .koala-min:focus-visible { outline: 3px solid var(--color-accent-ink, #166534); outline-offset: 3px; }
.koala-button:disabled { cursor: not-allowed; opacity: 0.7; }
.koala-chip { background: var(--color-bg-card); border: var(--border-width) solid var(--color-border-strong); border-radius: 50%; box-shadow: var(--shadow-btn-sm); cursor: pointer; height: 2.75rem; padding: 0.15rem; width: 2.75rem; }
.koala-min { background: var(--color-bg-card); border: var(--border-width) solid var(--color-border-strong); border-radius: 50%; color: var(--color-text); cursor: pointer; font: inherit; font-weight: 700; height: 1.75rem; line-height: 1; padding: 0; width: 1.75rem; }
.koala-dismiss { background: transparent; border: 0; color: inherit; cursor: pointer; font: inherit; font-weight: 700; line-height: 1; margin-left: 0.5rem; padding: 0 0.15rem; }
.koala-bubble { align-items: flex-start; display: flex; background: var(--color-bg-card); border: var(--border-width) solid var(--color-border-strong); border-radius: var(--radius); box-shadow: var(--shadow-btn-sm); color: var(--color-text); font-size: 0.9375rem; font-weight: 600; margin: 0; padding: 0.45rem 0.8rem; }
.koala-bubble[role='alert'] { border-color: var(--color-accent-ink, #166534); font-weight: 700; }

@media (max-width: 640px) {
  .koala-button { height: 5rem; width: 5rem; }
}
</style>

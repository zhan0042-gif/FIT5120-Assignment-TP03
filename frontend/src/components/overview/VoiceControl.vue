<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useVoiceStore } from '../../stores/voice'
import { VOICE_PRIVACY_NOTE } from '../../utils/voiceCopy'

const router = useRouter()
const store = useVoiceStore()

// The microphone API only exists on HTTPS or localhost; hide the control elsewhere
// rather than show a button that can never work.
const supported =
  typeof window !== 'undefined' &&
  'RTCPeerConnection' in window &&
  Boolean(globalThis.navigator?.mediaDevices?.getUserMedia)

const live = computed(() => store.status === 'listening' || store.status === 'checking')
const busy = computed(() => store.status === 'connecting' || store.status === 'closing')

const STATUS_TEXT = {
  idle: 'Voice is off.',
  connecting: 'Connecting…',
  listening: 'Listening. Ask me a question.',
  checking: 'Checking…',
  closing: 'Ending voice…',
  error: '',
}

function toggle() {
  if (live.value) store.stop()
  else store.start({ router })
}
</script>

<template>
  <div v-if="supported" class="voice-control">
    <button
      class="voice-button"
      type="button"
      :disabled="busy"
      :aria-pressed="live ? 'true' : 'false'"
      @click="toggle"
    >
      {{ live ? 'Stop voice' : 'Talk to the assistant' }}
    </button>
    <p class="voice-status" role="status" aria-live="polite">{{ store.error || STATUS_TEXT[store.status] }}</p>
    <p v-if="store.notice" class="voice-notice" role="alert">{{ store.notice }}</p>
    <p class="voice-privacy">{{ VOICE_PRIVACY_NOTE }}</p>
  </div>
</template>

<style scoped>
.voice-control { border-top: 1px solid var(--color-border-strong); margin-top: 0.85rem; padding-top: 0.85rem; }
.voice-button { background: transparent; border: 1px solid var(--color-accent); border-radius: 999px; color: var(--color-accent-ink); cursor: pointer; font: inherit; font-size: 0.9375rem; font-weight: 600; min-height: 2.75rem; padding: 0.45rem 1.25rem; }
.voice-button[aria-pressed='true'] { background: var(--color-accent); color: var(--color-on-accent); }
.voice-button:disabled { cursor: not-allowed; opacity: 0.6; }
.voice-status { color: var(--color-text-muted); font-size: 0.9rem; margin: 0.4rem 0 0; }
.voice-notice { font-weight: 700; margin: 0.4rem 0 0; }
.voice-privacy { color: var(--color-text-muted); font-size: 0.8125rem; margin: 0.4rem 0 0; }
</style>

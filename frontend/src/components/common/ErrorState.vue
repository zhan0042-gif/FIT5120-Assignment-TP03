<script setup>
import { useId } from 'vue'
import { useVoiceCommands } from '../../voice/registry.js'
import { buttonTarget } from '../../voice/targets.js'
defineProps({
  message: { type: String, default: 'Something went wrong.' },
})

const emit = defineEmits(['retry'])

const voiceId = useId()
useVoiceCommands(() => [buttonTarget({ id: `retry-${voiceId}`, label: 'Retry', press: () => emit('retry') })])
</script>

<template>
  <div class="state-block is-error">
    <p class="state-title">Unable to load this section</p>
    <p>{{ message }}</p>
    <button class="btn btn-ghost btn-sm" type="button" @click="emit('retry')">Retry</button>
  </div>
</template>

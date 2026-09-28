<script setup>
import { provideVoiceScope } from '../../voice/registry.js'

// Wraps a section that may be hidden while mounted. Voice targets registered
// anywhere inside are offered only while `active` is true.
const props = defineProps({ active: { type: Boolean, required: true } })
provideVoiceScope(() => props.active)
</script>

<template>
  <slot />
</template>

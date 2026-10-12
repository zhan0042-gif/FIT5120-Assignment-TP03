<script setup>
defineProps({
  id: { type: String, required: true },
  label: { type: String, required: true },
  helper: { type: String, default: '' },
  error: { type: String, default: '' },
})
</script>

<template>
  <div class="field">
    <label class="label" :for="id">{{ label }}</label>
    <p v-if="helper" class="helper">{{ helper }}</p>
    <slot />
    <p v-if="error" :id="`${id}-error`" class="field-error">{{ error }}</p>
  </div>
</template>

<style scoped>
.field { display: grid; gap: 0.35rem; }
.label { font-weight: 700; }
.helper { color: var(--color-text-muted); font-size: 0.9375rem; margin: 0; }
</style>

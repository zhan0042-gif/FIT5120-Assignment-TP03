<script setup>
import FormField from './FormField.vue'

defineProps({
  id: { type: String, required: true },
  label: { type: String, required: true },
  helper: { type: String, default: '' },
  error: { type: String, default: '' },
  min: { type: Number, default: 0 },
})
const model = defineModel({ default: 1 })
</script>

<template>
  <FormField :id="id" :label="label" :helper="helper" :error="error">
    <input
      :id="id"
      v-model.number="model"
      class="control"
      type="number"
      inputmode="numeric"
      step="1"
      :min="min"
      :aria-invalid="error ? 'true' : undefined"
      :aria-describedby="error ? `${id}-error` : undefined"
    />
  </FormField>
</template>

<style scoped>
.control { background: var(--color-bg-card); border: 2px solid var(--color-border-strong); border-radius: 12px; color: var(--color-text); font-size: 1.0625rem; max-width: 10rem; min-height: 3rem; padding: 0.6rem 0.8rem; width: 100%; }
</style>

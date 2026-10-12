<script setup>
import FormField from './FormField.vue'

defineProps({
  id: { type: String, required: true },
  label: { type: String, required: true },
  helper: { type: String, default: '' },
  error: { type: String, default: '' },
  options: { type: Array, required: true },
})
const model = defineModel({ type: String, default: '' })
</script>

<template>
  <FormField :id="id" :label="label" :helper="helper" :error="error">
    <select
      :id="id"
      class="control"
      :aria-invalid="error ? 'true' : undefined"
      :aria-describedby="error ? `${id}-error` : undefined"
      @change="model = $event.target.value"
    >
      <option v-for="[value, text] in options" :key="value" :value="value" :selected="value === model">{{ text }}</option>
    </select>
  </FormField>
</template>

<style scoped>
.control { background: var(--color-bg-card); border: 2px solid var(--color-border-strong); border-radius: 12px; color: var(--color-text); font-size: 1.0625rem; min-height: 3rem; padding: 0.6rem 0.8rem; width: 100%; }
</style>

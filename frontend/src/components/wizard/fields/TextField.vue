<script setup>
import FormField from './FormField.vue'

defineProps({
  id: { type: String, required: true },
  label: { type: String, required: true },
  helper: { type: String, default: '' },
  error: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  maxLength: { type: Number, default: 200 },
})
const model = defineModel({ type: String, default: '' })
</script>

<template>
  <FormField :id="id" :label="label" :helper="helper" :error="error">
    <input
      :id="id"
      v-model="model"
      class="control"
      type="text"
      autocomplete="off"
      :placeholder="placeholder"
      :maxlength="maxLength"
      :aria-invalid="error ? 'true' : undefined"
      :aria-describedby="error ? `${id}-error` : undefined"
    />
  </FormField>
</template>

<style scoped>
.control { background: var(--color-bg-card); border: 2px solid var(--color-border-strong); border-radius: 12px; color: var(--color-text); font-size: 1.0625rem; min-height: 3rem; padding: 0.6rem 0.8rem; width: 100%; }
</style>

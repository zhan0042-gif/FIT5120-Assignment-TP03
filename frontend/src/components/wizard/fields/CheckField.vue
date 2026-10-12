<script setup>
defineProps({
  id: { type: String, required: true },
  label: { type: String, required: true },
  helper: { type: String, default: '' },
  error: { type: String, default: '' },
  options: { type: Array, required: true },
})
const model = defineModel({ type: Array, default: () => [] })

function toggle(value) {
  model.value = model.value.includes(value) ? model.value.filter((item) => item !== value) : [...model.value, value]
}
</script>

<template>
  <fieldset :id="id" class="group" :aria-describedby="error ? `${id}-error` : undefined">
    <legend class="label">{{ label }}</legend>
    <p v-if="helper" class="helper">{{ helper }}</p>
    <label v-for="[value, text] in options" :key="value" class="check" :class="{ 'is-selected': model.includes(value) }">
      <input type="checkbox" :value="value" :checked="model.includes(value)" @change="toggle(value)" />
      <span>{{ text }}</span>
    </label>
    <p v-if="error" :id="`${id}-error`" class="field-error">{{ error }}</p>
  </fieldset>
</template>

<style scoped>
.group { border: 0; display: grid; gap: 0.5rem; margin: 0; min-width: 0; padding: 0; }
.label { font-weight: 700; padding: 0; }
.helper { color: var(--color-text-muted); font-size: 0.9375rem; margin: 0; }
.check { align-items: center; background: var(--color-bg-card); border: 2px solid var(--color-border-strong); border-radius: 12px; cursor: pointer; display: flex; gap: 0.7rem; min-height: 3rem; padding: 0.5rem 0.9rem; }
.check.is-selected { background: var(--color-accent-soft); border-color: var(--color-accent-ink); font-weight: 700; }
.check input { flex: none; height: 1.2rem; width: 1.2rem; }
.check:focus-within { outline: 3px solid var(--color-focus); outline-offset: 2px; }
</style>

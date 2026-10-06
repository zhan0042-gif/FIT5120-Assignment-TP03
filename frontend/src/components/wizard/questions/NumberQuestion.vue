<script setup>
defineProps({
  id: { type: String, required: true },
  describedBy: { type: String, default: undefined },
  min: { type: Number, default: 0 },
})
const model = defineModel({ default: 1 })
</script>

<template>
  <input
    :id="id"
    v-model.number="model"
    class="wizard-input"
    type="number"
    inputmode="numeric"
    :min="min"
    step="1"
    :aria-describedby="describedBy"
  />
</template>

<style scoped>
.wizard-input { width: 100%; max-width: 12rem; border: 2px solid var(--color-border-strong); border-radius: 12px; background: var(--color-bg-card); color: var(--color-text); font-size: 1.125rem; min-height: 3.25rem; padding: 0.7rem 0.9rem; }
</style>

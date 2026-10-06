<script setup>
defineProps({
  id: { type: String, required: true },
  describedBy: { type: String, default: undefined },
  placeholder: { type: String, default: '' },
  maxLength: { type: Number, default: 200 },
})
const model = defineModel({ type: String, default: '' })
</script>

<template>
  <input
    :id="id"
    v-model="model"
    class="wizard-input"
    type="text"
    autocomplete="off"
    :placeholder="placeholder"
    :maxlength="maxLength"
    :aria-describedby="describedBy"
  />
</template>

<style scoped>
.wizard-input { width: 100%; border: 2px solid var(--color-border-strong); border-radius: 12px; background: var(--color-bg-card); color: var(--color-text); font-size: 1.125rem; min-height: 3.25rem; padding: 0.7rem 0.9rem; }
</style>

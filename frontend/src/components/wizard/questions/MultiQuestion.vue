<script setup>
defineProps({
  options: { type: Array, required: true },
  describedBy: { type: String, default: undefined },
})
const model = defineModel({ type: Array, default: () => [] })

function toggle(value) {
  model.value = model.value.includes(value)
    ? model.value.filter((item) => item !== value)
    : [...model.value, value]
}
</script>

<template>
  <div class="choices" role="group" aria-labelledby="wizard-prompt" :aria-describedby="describedBy">
    <label v-for="[value, label] in options" :key="value" class="choice" :class="{ 'is-selected': model.includes(value) }">
      <input type="checkbox" :value="value" :checked="model.includes(value)" @change="toggle(value)" />
      <span>{{ label }}</span>
    </label>
  </div>
</template>

<style scoped>
.choices { display: grid; gap: 0.6rem; }
.choice { align-items: center; background: var(--color-bg-card); border: 2px solid var(--color-border-strong); border-radius: 14px; cursor: pointer; display: flex; font-size: 1.0625rem; gap: 0.75rem; min-height: 3.25rem; padding: 0.6rem 1rem; }
.choice:hover { background: var(--color-bg-card-muted); }
.choice.is-selected { background: var(--color-accent-soft); border-color: var(--color-accent-ink); font-weight: 700; }
.choice input { flex: none; height: 1.25rem; width: 1.25rem; }
.choice:focus-within { outline: 3px solid var(--color-focus); outline-offset: 2px; }
</style>

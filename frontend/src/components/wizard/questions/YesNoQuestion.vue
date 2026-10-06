<script setup>
defineProps({ current: { type: [Boolean, null], default: null } })
const emit = defineEmits(['answer'])
</script>

<template>
  <div class="yesno">
    <button type="button" class="btn btn-accent btn-big" :aria-pressed="current === true" @click="emit('answer', true)">Yes</button>
    <button type="button" class="btn btn-primary btn-big" :aria-pressed="current === false" @click="emit('answer', false)">No</button>
  </div>
</template>

<style scoped>
.yesno { display: flex; flex-wrap: wrap; gap: 1rem; }
.btn-big { flex: 1 1 8rem; font-size: 1.125rem; min-height: 3.5rem; }
</style>

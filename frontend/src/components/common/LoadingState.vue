<script setup>
defineProps({ message: { type: String, default: 'Loading…' } })
</script>

<template>
  <div class="state-block" role="status">
    <span class="spinner" aria-hidden="true" />
    <p>{{ message }}</p>
  </div>
</template>

<style scoped>
.spinner {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-accent);
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>

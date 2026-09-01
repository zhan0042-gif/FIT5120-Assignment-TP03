<script setup>
defineProps({
  title: { type: String, default: 'Nothing here yet' },
  message: { type: String, default: undefined },
})
</script>

<template>
  <div class="state-block">
    <p class="state-title">{{ title }}</p>
    <p v-if="message">{{ message }}</p>
    <slot />
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ title?: string; message?: string }>(), {
  title: 'Nothing here yet',
})
</script>

<template>
  <div class="state-block">
    <p class="state-title">{{ title }}</p>
    <p v-if="message">{{ message }}</p>
    <slot />
  </div>
</template>

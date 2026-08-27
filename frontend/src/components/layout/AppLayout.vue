<script setup lang="ts">
import AppSidebar from './AppSidebar.vue'
</script>

<template>
  <div class="layout">
    <AppSidebar />
    <main class="content">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  min-height: 100vh;
}

.content {
  flex: 1;
  min-width: 0;
  padding: 2.5rem 3rem;
}

@media (max-width: 720px) {
  .layout {
    flex-direction: column;
  }

  .content {
    padding: 1.5rem;
  }
}
</style>

<script setup>
import FdrPredictionPanel from '../components/overview/FdrPredictionPanel.vue'
import SafetyChatPanel from '../components/overview/SafetyChatPanel.vue'
</script>

<template>
  <div class="safety-insights">
    <header class="page-header">
      <h1>Safety Insights</h1>
      <p>Explore historical fire danger patterns and reviewed bushfire safety guidance.</p>
    </header>

    <div class="insights-stack">
      <FdrPredictionPanel />
      <SafetyChatPanel />
    </div>
  </div>
</template>

<style scoped>
.safety-insights {
  min-width: 0;
  width: 100%;
}

.page-header {
  margin-bottom: 1.75rem;
}

.page-header h1 {
  font-size: clamp(2rem, 4vw, 2.25rem);
  line-height: 1.2;
}

.page-header p {
  color: var(--color-text-muted);
  margin-top: 0.5rem;
}

.insights-stack {
  display: grid;
  gap: 1.75rem;
  min-width: 0;
}

.insights-stack :deep(.card) {
  margin-top: 0;
}
</style>

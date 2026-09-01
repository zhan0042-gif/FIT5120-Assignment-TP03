<script setup>
import { computed } from 'vue'
import { useLocalContextStore } from '../../stores/localContext'

const store = useLocalContextStore()

const SECTION_LABELS = {
  backup_transport: 'backup transport',
  backup_destination: 'backup destination',
  responsibilities: 'responsibilities',
}

const reviewLabels = computed(() =>
  (store.prepSupport?.sections_to_review ?? []).map((s) => SECTION_LABELS[s] ?? s),
)
</script>

<template>
  <section v-if="store.prepSupport" class="banner" :class="{ 'is-alert': store.prepSupport.status === 'review_recommended' }">
    <p class="message">{{ store.prepSupport.message }}</p>
    <p v-if="reviewLabels.length" class="review-list">
      Review: <strong>{{ reviewLabels.join(', ') }}</strong>
    </p>
  </section>
</template>

<style scoped>
.banner {
  border: 1px solid var(--color-border);
  border-left: 4px solid var(--color-success);
  border-radius: var(--radius);
  padding: 1rem 1.25rem;
  background: var(--color-bg-card);
  margin-bottom: 1.25rem;
}

.banner.is-alert {
  border-left-color: var(--color-accent);
}

.message {
  font-weight: 600;
  margin-top: 0.3rem;
}

.review-list {
  margin-top: 0.4rem;
  font-size: 0.875rem;
  color: var(--color-text-muted);
}
</style>

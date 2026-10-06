<script setup>
defineProps({
  section: { type: Object, required: true },
  text: { type: String, required: true },
  needsAttention: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  error: { type: String, default: null },
  isEdit: { type: Boolean, default: false },
})
const emit = defineEmits(['save', 'back'])
</script>

<template>
  <section class="recap" aria-labelledby="recap-title">
    <p class="eyebrow">Section done</p>
    <h2 id="recap-title" class="title">{{ section.title }}</h2>
    <p class="text">{{ text }}</p>
    <p v-if="needsAttention" class="note">Some answers are still missing. You can save now and fill them in later.</p>
    <p v-if="error" class="field-error" role="alert">{{ error }}</p>
    <div class="controls">
      <button type="button" class="btn btn-ghost" @click="emit('back')">Back</button>
      <span class="spacer"></span>
      <button type="button" class="btn btn-accent" :disabled="saving" @click="emit('save')">
        {{ saving ? 'Saving…' : isEdit ? 'Save and return to review' : 'Save and continue' }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.recap { display: grid; gap: 0.9rem; }
.title { font-size: clamp(1.6rem, 4vw, 2.25rem); }
.text { font-size: 1.125rem; }
.note { color: var(--color-text-muted); }
.controls { align-items: center; display: flex; flex-wrap: wrap; gap: 0.75rem; margin-top: 0.5rem; }
.spacer { flex: 1 1 0; }
</style>

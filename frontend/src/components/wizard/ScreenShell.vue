<script setup>
defineProps({
  screen: { type: Object, required: true },
  position: { type: Number, required: true },
  total: { type: Number, required: true },
  errors: { type: Array, default: () => [] },
  saveError: { type: String, default: null },
  saving: { type: Boolean, default: false },
  isEdit: { type: Boolean, default: false },
  canGoBack: { type: Boolean, default: false },
})
const emit = defineEmits(['save', 'skip', 'back'])
</script>

<template>
  <section class="shell" aria-labelledby="wizard-prompt">
    <p class="where">Part {{ position }} of {{ total }}</p>
    <h2 id="wizard-prompt" class="title" tabindex="-1">{{ screen.title }}</h2>

    <form class="body" novalidate @submit.prevent="emit('save')">
      <slot />

      <div v-if="errors.length" class="summary" role="alert">
        <p class="summary-title">Please fix this before saving:</p>
        <ul>
          <li v-for="item in errors" :key="item.field"><a :href="`#${item.field}`">{{ item.message }}</a></li>
        </ul>
      </div>
      <p v-if="saveError" class="field-error" role="alert">{{ saveError }}</p>

      <div class="controls">
        <button v-if="canGoBack" type="button" class="btn btn-ghost" @click="emit('back')">Back</button>
        <span class="spacer"></span>
        <button type="button" class="btn btn-ghost" @click="emit('skip')">Skip for now</button>
        <button type="submit" class="btn btn-accent" :disabled="saving">
          {{ saving ? 'Saving…' : isEdit ? 'Save and return to review' : 'Save and continue' }}
        </button>
      </div>
    </form>
  </section>
</template>

<style scoped>
.shell { display: grid; gap: 1rem; }
.where { color: var(--color-text-muted); font-size: 0.875rem; font-weight: 700; margin: 0; }
.title { font-size: clamp(1.5rem, 4vw, 2.1rem); margin: 0; }
.body { display: grid; gap: 1.1rem; }
.summary { background: var(--color-bg-card-muted); border: 2px solid var(--color-border-strong); border-radius: 12px; padding: 0.8rem 1rem; }
.summary-title { font-weight: 800; margin: 0 0 0.3rem; }
.summary ul { margin: 0; padding-left: 1.2rem; }
.controls { align-items: center; display: flex; flex-wrap: wrap; gap: 0.75rem; margin-top: 0.5rem; }
.spacer { flex: 1 1 0; }
</style>

<script setup>
import { ref, useId } from 'vue'

defineProps({
  text: { type: String, required: true },
  label: { type: String, default: 'More information' },
})

const tipId = useId()
// Hover and focus show the tip through CSS; this flag lets a tap on touch
// screens, which have no hover, keep it open until the next tap or blur.
const pinned = ref(false)
</script>

<template>
  <span class="info-tip" :class="{ 'is-open': pinned }">
    <button
      class="info-tip-trigger"
      type="button"
      :aria-label="label"
      :aria-describedby="tipId"
      @click.prevent.stop="pinned = !pinned"
      @blur="pinned = false"
      @keydown.esc="pinned = false"
    >i</button>
    <span :id="tipId" class="info-tip-bubble" role="tooltip">{{ text }}</span>
  </span>
</template>

<style scoped>
.info-tip {
  display: inline-flex;
  position: relative;
  vertical-align: middle;
  margin-left: 0.35rem;
  /* Labels around the tip are uppercase and letter-spaced; the bubble is prose. */
  letter-spacing: normal;
  text-transform: none;
  font-weight: 400;
}

.info-tip-trigger {
  align-items: center;
  background: transparent;
  border: 1.5px solid var(--color-text-muted);
  border-radius: 50%;
  color: var(--color-text-muted);
  cursor: help;
  display: inline-flex;
  font: italic 700 0.7rem/1 Georgia, serif;
  height: 1.05rem;
  justify-content: center;
  padding: 0;
  width: 1.05rem;
}

.info-tip-trigger:hover,
.info-tip-trigger:focus-visible,
.info-tip.is-open .info-tip-trigger {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.info-tip-trigger:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}

.info-tip-bubble {
  background: var(--color-text);
  border-radius: var(--radius);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.18);
  color: var(--color-bg-card);
  font-size: 0.8rem;
  left: -0.5rem;
  line-height: 1.45;
  opacity: 0;
  padding: 0.55rem 0.75rem;
  pointer-events: none;
  position: absolute;
  top: calc(100% + 0.45rem);
  transform: translateY(-2px);
  transition: opacity 0.12s ease, transform 0.12s ease, visibility 0.12s;
  visibility: hidden;
  width: max-content;
  max-width: min(18rem, 75vw);
  z-index: 20;
}

.info-tip-bubble::before {
  border: 6px solid transparent;
  border-bottom-color: var(--color-text);
  bottom: 100%;
  content: '';
  left: 0.75rem;
  position: absolute;
}

.info-tip:hover .info-tip-bubble,
.info-tip-trigger:focus-visible + .info-tip-bubble,
.info-tip.is-open .info-tip-bubble {
  opacity: 1;
  transform: none;
  visibility: visible;
}

@media (prefers-reduced-motion: reduce) {
  .info-tip-bubble { transition: none; }
}
</style>

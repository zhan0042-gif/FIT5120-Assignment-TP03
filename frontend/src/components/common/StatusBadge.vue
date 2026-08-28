<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ status: string }>()

const LABELS: Record<string, string> = {
  complete: 'Complete',
  needs_information: 'Needs information',
  pass: 'Pass',
  fail: 'Needs attention',
  not_checked: 'Not checked',
  ok: 'All checks pass',
  needs_attention: 'Needs attention',
  on_track: 'On track',
  review_recommended: 'Review recommended',
}

const VARIANTS: Record<string, string> = {
  complete: 'badge-success',
  pass: 'badge-success',
  ok: 'badge-success',
  on_track: 'badge-success',
  needs_information: 'badge-warning',
  review_recommended: 'badge-warning',
  fail: 'badge-danger',
  needs_attention: 'badge-danger',
  not_checked: 'badge-neutral',
}

const label = computed(() => LABELS[props.status] ?? props.status)
const variant = computed(() => VARIANTS[props.status] ?? 'badge-neutral')
</script>

<template>
  <span class="badge" :class="variant">{{ label }}</span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ status: { type: String, required: true } })

const LABELS = {
  complete: 'Complete',
  needs_information: 'Needs information',
  pass: 'Pass',
  fail: 'Needs attention',
  not_checked: 'Not checked',
  ok: 'All checks pass',
  needs_attention: 'Needs attention',
  up_to_date: 'Up to date',
  review_recommended: 'Review recommended',
  warning: 'Warning',
}

const VARIANTS = {
  complete: 'badge-success',
  pass: 'badge-success',
  ok: 'badge-success',
  up_to_date: 'badge-success',
  needs_information: 'badge-warning',
  review_recommended: 'badge-warning',
  warning: 'badge-warning',
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

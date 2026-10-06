<script setup>
import AddressAutocompleteInput from '../../common/AddressAutocompleteInput.vue'

defineProps({ label: { type: String, required: true }, helper: { type: String, default: '' } })
const model = defineModel({ type: String, default: '' })
const emit = defineEmits(['select'])
</script>

<template>
  <AddressAutocompleteInput
    v-model="model"
    :label="label"
    :helper-text="helper"
    placeholder="Start typing a Victorian street address"
    @select="emit('select', $event)"
  />
</template>

<script setup>
import { USUAL_LOCATION_KINDS } from '../../../wizard/options.js'
import { memberLabel, memberTitle } from '../../../wizard/labels.js'
import { selectUsualAddress, setUsualAddress, setUsualKind } from '../../../wizard/wizardDraft.js'
import AddressQuestion from '../questions/AddressQuestion.vue'
import SelectField from '../fields/SelectField.vue'

defineProps({
  plan: { type: Object, required: true },
  errors: { type: Object, default: () => ({}) },
})
const KIND_OPTIONS = [['', 'Not sure'], ...USUAL_LOCATION_KINDS]
</script>

<template>
  <div class="screen">
    <p v-if="!plan.members.length" class="notice">Add the people in your household first. Then come back here to say where each person is during the day.</p>
    <fieldset v-for="(member, i) in plan.members" :key="member.member_id" class="card-box">
      <legend>{{ memberTitle(plan, i) }}</legend>
      <SelectField
        :id="`location:${i}:kind`"
        :label="i === 0 ? 'Where are you during the day?' : `Where is ${memberLabel(plan, i)} during the day?`"
        :model-value="member.usual_location?.kind ?? ''"
        :options="KIND_OPTIONS"
        @update:model-value="setUsualKind(member, $event)"
      />
      <AddressQuestion
        v-if="member.usual_location"
        label="What is the address?"
        helper="Pick a suggestion, or type it in if it is not listed."
        :model-value="member.usual_location.address ?? ''"
        @update:model-value="setUsualAddress(member, $event)"
        @select="selectUsualAddress(member, $event)"
      />
    </fieldset>
  </div>
</template>

<style scoped>
.screen { display: grid; gap: 1rem; }
.notice { color: var(--color-text-muted); }
.card-box { border: 2px solid var(--color-border-strong); border-radius: 16px; display: grid; gap: 0.9rem; margin: 0; min-width: 0; padding: 1rem; }
.card-box legend { font-weight: 800; padding: 0 0.4rem; }
</style>

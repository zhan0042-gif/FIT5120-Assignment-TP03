<script setup>
import { addBackupPlace } from '../../../wizard/formActions.js'
import {
  backupDestination, primaryDestination, removeBackupPlace, selectDestinationAddress, setDestinationAddress,
} from '../../../wizard/wizardDraft.js'
import AddressQuestion from '../questions/AddressQuestion.vue'
import TextField from '../fields/TextField.vue'

const props = defineProps({
  plan: { type: Object, required: true },
  errors: { type: Object, default: () => ({}) },
})
const primary = () => props.plan.arrangements?.primary_destination ?? null
const backups = () => (props.plan.arrangements?.backup_arrangements ?? [])
  .map((entry, index) => ({ entry, index }))
  .filter(({ entry }) => entry.destination)

function setPrimaryName(value) {
  primaryDestination(props.plan).display_name = value
}
function setMeeting(value) {
  props.plan.arrangements ??= {}
  props.plan.arrangements.meeting_point = value || null
}
function addPlace() {
  const entry = addBackupPlace(props.plan)
  backupDestination(props.plan, props.plan.arrangements.backup_arrangements.indexOf(entry))
}
</script>

<template>
  <div class="screen">
    <fieldset class="card-box">
      <legend>Where you would go</legend>
      <TextField
        id="place:name"
        :model-value="primary()?.display_name ?? ''"
        label="Where would you go?"
        helper="A name you would recognise, such as Nan's house."
        placeholder="e.g. Relative's house"
        :max-length="100"
        @update:model-value="setPrimaryName"
      />
      <AddressQuestion
        v-if="primary()"
        label="What is the address?"
        helper="Pick a suggestion, or type it in if it is not listed."
        :model-value="primary().address ?? ''"
        @update:model-value="setDestinationAddress(primary(), $event)"
        @select="selectDestinationAddress(primary(), $event)"
      />
      <TextField
        id="place:meeting"
        :model-value="plan.arrangements?.meeting_point ?? ''"
        label="If your household is separated, where would you meet?"
        helper="Optional."
        placeholder="e.g. Front gate"
        :max-length="200"
        @update:model-value="setMeeting"
      />
    </fieldset>

    <fieldset v-for="({ entry, index }, n) in backups()" :key="entry.destination.destination_id" class="card-box">
      <legend>Backup place {{ n + 1 }}</legend>
      <TextField
        :id="`backupplace:${index}:name`"
        v-model="entry.destination.display_name"
        :label="n === 0 ? 'If you could not go there, where would you go instead?' : 'Where else could you go?'"
        placeholder="e.g. Community centre"
        :max-length="100"
      />
      <AddressQuestion
        label="What is the address?"
        helper="Pick a suggestion, or type it in if it is not listed."
        :model-value="entry.destination.address ?? ''"
        @update:model-value="setDestinationAddress(entry.destination, $event)"
        @select="selectDestinationAddress(entry.destination, $event)"
      />
      <button type="button" class="btn btn-danger btn-sm" @click="removeBackupPlace(plan, index)">Remove this place</button>
    </fieldset>
    <button type="button" class="btn btn-ghost" @click="addPlace">Add another place</button>
  </div>
</template>

<style scoped>
.screen { display: grid; gap: 1.1rem; }
.card-box { border: 2px solid var(--color-border-strong); border-radius: 16px; display: grid; gap: 0.9rem; margin: 0; min-width: 0; padding: 1rem; }
.card-box legend { font-weight: 800; padding: 0 0.4rem; }
</style>

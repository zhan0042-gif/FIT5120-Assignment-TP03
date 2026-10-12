<script setup>
import { TRANSPORT_TYPES, transportLabel } from '../../../wizard/options.js'
import { memberTitle } from '../../../wizard/labels.js'
import { addVehicle, setFirstVehicle, setHasVehicle, setVehicleType } from '../../../wizard/formActions.js'
import { backupTransportIds, removeTransport, setBackupTransports } from '../../../wizard/wizardDraft.js'
import YesNoQuestion from '../questions/YesNoQuestion.vue'
import CheckField from '../fields/CheckField.vue'
import SelectField from '../fields/SelectField.vue'
import TextField from '../fields/TextField.vue'

const props = defineProps({
  plan: { type: Object, required: true },
  errors: { type: Object, default: () => ({}) },
})
const err = (field) => props.errors[field] ?? ''
const driverOptions = () => props.plan.members.map((member, index) => [member.member_id, memberTitle(props.plan, index)])
const firstOptions = () => [['', 'Not sure yet'], ...props.plan.transports.map((t) => [t.transport_id, transportLabel(t)])]
const firstId = () => props.plan.arrangements?.primary_transport_id ?? ''
// A backup needs a second vehicle: with only one there is nothing to back it up,
// even before a first choice has been made.
const backupCandidates = () =>
  props.plan.transports.length < 2
    ? []
    : props.plan.transports.filter((t) => t.transport_id !== firstId()).map((t) => [t.transport_id, transportLabel(t)])
</script>

<template>
  <div class="screen">
    <section aria-labelledby="has-vehicle">
      <h3 id="has-vehicle" class="group-title">Do you have a vehicle you would leave in?</h3>
      <YesNoQuestion :current="plan.has_private_transport ?? null" @answer="setHasVehicle(plan, $event)" />
    </section>

    <template v-if="plan.has_private_transport === true">
      <fieldset v-for="(vehicle, i) in plan.transports" :key="vehicle.transport_id" class="card-box">
        <legend>Vehicle {{ i + 1 }}</legend>
        <SelectField
          :id="`vehicle:${i}:type`"
          label="What kind of vehicle is it?"
          :model-value="vehicle.transport_type"
          :options="TRANSPORT_TYPES"
          @update:model-value="setVehicleType(vehicle, $event)"
        />
        <TextField
          v-if="vehicle.transport_type === 'other'"
          :id="`vehicle:${i}:type_other`"
          :model-value="vehicle.transport_type_other ?? ''"
          label="What kind of vehicle?"
          placeholder="e.g. Tractor"
          :max-length="100"
          :error="err(`vehicle:${i}:type_other`)"
          @update:model-value="vehicle.transport_type_other = $event || null"
        />
        <TextField
          :id="`vehicle:${i}:name`"
          v-model="vehicle.display_name"
          label="What do you call it?"
          helper="For example Dad's ute. Optional."
          placeholder="Optional"
          :max-length="100"
        />
        <CheckField
          v-if="plan.members.length"
          :id="`vehicle:${i}:drivers`"
          v-model="vehicle.driver_member_ids"
          label="Who can drive it?"
          helper="Tick everyone who could drive it."
          :options="driverOptions()"
        />
        <button type="button" class="btn btn-danger btn-sm" @click="removeTransport(plan, vehicle.transport_id)">Remove this vehicle</button>
      </fieldset>
      <button type="button" class="btn btn-ghost" @click="addVehicle(plan)">Add another vehicle</button>

      <SelectField
        v-if="plan.transports.length"
        id="transport:primary"
        label="Which one would you take first?"
        :model-value="firstId()"
        :options="firstOptions()"
        @update:model-value="setFirstVehicle(plan, $event)"
      />

      <CheckField
        v-if="backupCandidates().length"
        id="backup:vehicles"
        label="If your first vehicle cannot be used, which others could you take?"
        :model-value="backupTransportIds(plan)"
        :options="backupCandidates()"
        @update:model-value="setBackupTransports(plan, $event)"
      />
      <p v-else-if="plan.transports.length" class="notice">Add a second vehicle to choose a backup.</p>
    </template>
  </div>
</template>

<style scoped>
.screen { display: grid; gap: 1.1rem; }
.group-title { font-size: 1.125rem; margin: 0 0 0.6rem; }
.notice { color: var(--color-text-muted); }
.card-box { border: 2px solid var(--color-border-strong); border-radius: 16px; display: grid; gap: 0.9rem; margin: 0; min-width: 0; padding: 1rem; }
.card-box legend { font-weight: 800; padding: 0 0.4rem; }
</style>

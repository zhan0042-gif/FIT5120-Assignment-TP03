<script setup>
import { ANIMAL_CATEGORIES, ANIMAL_TYPES, RELATIONSHIPS } from '../../../wizard/options.js'
import { memberTitle } from '../../../wizard/labels.js'
import {
  HELP_OPTIONS, addAnimal, addMember, memberHelpValues, setAnimalCategory, setAnimalType,
  setAnimalsAny, setMemberHelp, setMemberRelationship,
} from '../../../wizard/formActions.js'
import { removeAnimal, removeMember } from '../../../wizard/wizardDraft.js'
import { focusAfterRender } from '../../../wizard/focus.js'
import YesNoQuestion from '../questions/YesNoQuestion.vue'
import CheckField from '../fields/CheckField.vue'
import NumberField from '../fields/NumberField.vue'
import SelectField from '../fields/SelectField.vue'
import TextField from '../fields/TextField.vue'

const props = defineProps({
  plan: { type: Object, required: true },
  errors: { type: Object, default: () => ({}) },
})

const err = (field) => props.errors[field] ?? ''
const RELATIONSHIP_OPTIONS = [['', 'Prefer not to say'], ...RELATIONSHIPS.filter(([value]) => value !== 'self')]
const animalsAnswer = () => (props.plan.animals.length > 0 ? true : null)
function addPerson() {
  addMember(props.plan)
  focusAfterRender(`member:${props.plan.members.length - 1}:name`)
}
function dropPerson(member) {
  removeMember(props.plan, member.member_id)
  focusAfterRender('add-person')
}
function addOneAnimal() {
  addAnimal(props.plan)
  focusAfterRender(`animal:${props.plan.animals.length - 1}:category`)
}
function dropAnimal(index) {
  removeAnimal(props.plan, index)
  focusAfterRender('add-animal')
}
const nameOf = (member) => member.display_name?.trim() || 'this person'
</script>

<template>
  <div class="screen">
    <fieldset v-for="(member, i) in plan.members" :key="member.member_id" class="card-box">
      <legend>{{ memberTitle(plan, i) }}</legend>
      <TextField
        :id="`member:${i}:name`"
        v-model="member.display_name"
        :label="i === 0 ? 'What is your name?' : 'What is their name?'"
        placeholder="e.g. Maya"
        :max-length="100"
        :error="err(`member:${i}:name`)"
      />
      <SelectField
        v-if="i > 0"
        :id="`member:${i}:relationship`"
        :label="`How is ${nameOf(member)} related to you?`"
        :model-value="member.relationship ?? ''"
        :options="RELATIONSHIP_OPTIONS"
        @update:model-value="setMemberRelationship(member, $event)"
      />
      <TextField
        v-if="member.relationship === 'other'"
        :id="`member:${i}:relationship_other`"
        :model-value="member.relationship_other ?? ''"
        :label="`How would you describe ${nameOf(member)}?`"
        placeholder="e.g. Neighbour"
        :max-length="100"
        @update:model-value="member.relationship_other = $event || null"
      />
      <CheckField
        :id="`member:${i}:help`"
        :label="i === 0 ? 'Do you need any extra help to leave?' : 'Do they need any extra help to leave?'"
        helper="Tick any that apply."
        :model-value="memberHelpValues(member)"
        :options="HELP_OPTIONS"
        @update:model-value="setMemberHelp(member, $event)"
      />
      <TextField
        v-if="member.is_dependant || member.mobility_support_required"
        :id="`member:${i}:support_notes`"
        :model-value="member.support_notes ?? ''"
        label="Is there anything else we should know?"
        placeholder="e.g. Needs medication prepared"
        @update:model-value="member.support_notes = $event || null"
      />
      <button v-if="i > 0" type="button" class="btn btn-danger btn-sm" @click="dropPerson(member)">Remove this person</button>
    </fieldset>
    <button id="add-person" type="button" class="btn btn-ghost" @click="addPerson">Add another person</button>

    <section class="animals" aria-labelledby="animals-title">
      <h3 id="animals-title" class="group-title">Do any animals leave with you?</h3>
      <p class="helper">Pets or livestock. Choose No if you have none.</p>
      <YesNoQuestion :current="animalsAnswer()" @answer="setAnimalsAny(plan, $event)" />

      <fieldset v-for="(animal, i) in plan.animals" :key="animal.animal_id" class="card-box">
        <legend>Animal {{ i + 1 }}</legend>
        <SelectField
          :id="`animal:${i}:category`"
          label="Is this a pet or livestock?"
          :model-value="animal.category"
          :options="ANIMAL_CATEGORIES"
          @update:model-value="setAnimalCategory(animal, $event)"
        />
        <SelectField
          :id="`animal:${i}:type`"
          label="What kind of animal is it?"
          :model-value="animal.animal_type"
          :options="ANIMAL_TYPES[animal.category] ?? ANIMAL_TYPES.pet"
          @update:model-value="setAnimalType(animal, $event)"
        />
        <TextField
          v-if="animal.animal_type === 'other'"
          :id="`animal:${i}:type_other`"
          :model-value="animal.animal_type_other ?? ''"
          label="What kind of animal?"
          placeholder="e.g. Ferret"
          :max-length="100"
          :error="err(`animal:${i}:type_other`)"
          @update:model-value="animal.animal_type_other = $event || null"
        />
        <NumberField :id="`animal:${i}:quantity`" v-model="animal.quantity" label="How many?" :min="1" :error="err(`animal:${i}:quantity`)" />
        <button type="button" class="btn btn-danger btn-sm" @click="dropAnimal(i)">Remove this animal</button>
      </fieldset>
      <button v-if="plan.animals.length" id="add-animal" type="button" class="btn btn-ghost" @click="addOneAnimal">Add another animal</button>
    </section>
  </div>
</template>

<style scoped>
.screen { display: grid; gap: 1.1rem; }
.card-box { border: 2px solid var(--color-border-strong); border-radius: 16px; display: grid; gap: 0.9rem; margin: 0; min-width: 0; padding: 1rem; }
.card-box legend { font-weight: 800; padding: 0 0.4rem; }
.group-title { font-size: 1.125rem; margin: 0.5rem 0 0; }
.helper { color: var(--color-text-muted); margin: 0.2rem 0 0.6rem; }
.animals { display: grid; gap: 0.9rem; }
</style>

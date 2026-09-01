<script setup>
import { newId } from '../../api/client'
import EmptyState from '../common/EmptyState.vue'

const members = defineModel('members', { required: true })
const animals = defineModel('animals', { required: true })

function addMember() {
  members.value.push({
    member_id: newId('m'),
    display_name: '',
    is_dependant: false,
    mobility_support_required: false,
    support_notes: null,
    relationship: null,
    relationship_other: null,
  })
}

function removeMember(id) {
  members.value = members.value.filter((m) => m.member_id !== id)
}

function addAnimal() {
  animals.value.push({
    animal_id: newId('a'),
    category: 'pet',
    display_name: '',
    animal_type: 'dog',
    animal_type_other: null,
    quantity: 1,
    support_notes: null,
  })
}

function removeAnimal(id) {
  animals.value = animals.value.filter((animal) => animal.animal_id !== id)
}

const RELATIONSHIPS = [
  ['self', 'Self'],
  ['partner', 'Partner / Spouse'],
  ['child', 'Child'],
  ['parent', 'Parent'],
  ['grandparent', 'Grandparent'],
  ['sibling', 'Sibling'],
  ['other_relative', 'Other relative'],
  ['friend_or_housemate', 'Friend / Housemate'],
  ['carer', 'Carer'],
  ['other', 'Other'],
]

const ANIMAL_TYPES = {
  pet: [['dog', 'Dog'], ['cat', 'Cat'], ['bird', 'Bird'], ['rabbit', 'Rabbit'], ['reptile', 'Reptile'], ['other', 'Other']],
  livestock: [['horse', 'Horse'], ['cattle', 'Cattle'], ['sheep', 'Sheep'], ['goat', 'Goat'], ['alpaca', 'Alpaca'], ['poultry', 'Poultry'], ['other', 'Other']],
}

function changeAnimalCategory(animal) {
  animal.animal_type = ANIMAL_TYPES[animal.category][0][0]
  animal.animal_type_other = null
  if (animal.category === 'pet' && !animal.quantity) animal.quantity = 1
}
</script>

<template>
  <section class="card">
    <div class="card-header">
      <div>
        <h3 class="card-title">Household members</h3>
      </div>
      <span class="badge" :class="members.length ? 'badge-success' : 'badge-neutral'">
        {{ members.length }} recorded
      </span>
    </div>

    <EmptyState
      v-if="members.length === 0"
      title="No household members yet"
      message="Add everyone who needs to be considered in this plan, including any support needs."
    >
      <button class="btn btn-primary btn-sm" type="button" @click="addMember">Add member</button>
    </EmptyState>

    <template v-else>
      <div v-for="member in members" :key="member.member_id" class="member-row">
        <div class="field-grid">
          <div class="field">
            <label :for="`${member.member_id}-name`">Name</label>
            <input :id="`${member.member_id}-name`" v-model="member.display_name" type="text" placeholder="e.g. Maya" />
            <span v-if="!member.display_name.trim()" class="field-error">A name helps identify this member in results.</span>
          </div>
          <div class="field">
            <label>Relationship to household</label>
            <select v-model="member.relationship">
              <option :value="null">Prefer not to specify</option>
              <option v-for="[value, label] in RELATIONSHIPS" :key="value" :value="value">{{ label }}</option>
            </select>
          </div>
          <div v-if="member.relationship === 'other'" class="field">
            <label>Please specify relationship (optional)</label>
            <input v-model="member.relationship_other" type="text" maxlength="100" placeholder="e.g. Neighbour" />
          </div>
          <div class="field">
            <label>Other support needs (optional)</label>
            <input v-model="member.support_notes" type="text" placeholder="e.g. Needs medication prepared or help communicating" />
            <span class="field-help">Record only practical information needed for emergency planning.</span>
          </div>
        </div>
        <div class="checkbox-group">
          <label class="checkbox-row">
            <input v-model="member.is_dependant" type="checkbox" />
            Needs help from another household member during an emergency?
          </label>
          <span class="field-help checkbox-help">For example, a young child or someone who cannot prepare to leave independently.</span>
          <label class="checkbox-row">
            <input v-model="member.mobility_support_required" type="checkbox" />
            Has limited mobility or needs help moving?
          </label>
          <span class="field-help checkbox-help">This means moving or transport support, such as a wheelchair, walking frame, accessible vehicle or help getting into a vehicle.</span>
          <button class="btn btn-danger btn-sm" type="button" @click="removeMember(member.member_id)">Remove</button>
        </div>
      </div>
      <button class="btn btn-ghost btn-sm" type="button" @click="addMember">+ Add another member</button>
    </template>

    <hr class="divider" />

    <div class="card-header">
      <h3 class="card-title">Animals</h3>
      <span class="badge badge-neutral">{{ animals.length }} recorded</span>
    </div>

    <EmptyState v-if="animals.length === 0" title="No animals recorded" message="This is fine — animals are optional.">
      <button class="btn btn-ghost btn-sm" type="button" @click="addAnimal">Add animal</button>
    </EmptyState>

    <template v-else>
      <div v-for="animal in animals" :key="animal.animal_id" class="member-row">
        <div class="field-grid">
          <div class="field">
            <label>Category</label>
            <select v-model="animal.category" required @change="changeAnimalCategory(animal)">
              <option value="pet">Pet</option>
              <option value="livestock">Livestock</option>
            </select>
          </div>
          <div class="field">
            <label>Animal type</label>
            <select v-model="animal.animal_type" required>
              <option value="" disabled>Select a type</option>
              <option v-for="[value, label] in ANIMAL_TYPES[animal.category]" :key="value" :value="value">{{ label }}</option>
            </select>
          </div>
          <div v-if="animal.animal_type === 'other'" class="field">
            <label>Other animal type</label>
            <input v-model="animal.animal_type_other" type="text" maxlength="100" placeholder="e.g. Ferret" />
          </div>
          <div class="field">
            <label>Quantity</label>
            <input v-model.number="animal.quantity" type="number" min="1" step="1" required />
            <span class="field-help">
              {{ animal.category === 'livestock' ? 'Use one record for a group, such as 20 sheep.' : 'Usually 1 for a named pet.' }}
            </span>
          </div>
          <div class="field">
            <label>{{ animal.category === 'pet' ? 'Name (optional)' : 'Group name (optional)' }}</label>
            <input v-model="animal.display_name" type="text" :placeholder="animal.category === 'pet' ? 'e.g. Coco' : 'e.g. North paddock sheep'" />
          </div>
          <div class="field">
            <label>Special transport or care notes (optional)</label>
            <input v-model="animal.support_notes" type="text" placeholder="e.g. Needs a carrier or livestock trailer" />
          </div>
        </div>
        <button class="btn btn-danger btn-sm" type="button" @click="removeAnimal(animal.animal_id)">Remove</button>
      </div>
      <button class="btn btn-ghost btn-sm" type="button" @click="addAnimal">+ Add another animal</button>
    </template>
  </section>
</template>

<style scoped>
.member-row {
  padding: 1rem 0;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.checkbox-group {
  display: flex;
  align-items: center;
  gap: 1.25rem;
  flex-wrap: wrap;
}

.field-help {
  color: var(--color-text-muted);
  font-size: 0.8rem;
}

.checkbox-help {
  flex-basis: 100%;
  margin-top: -0.8rem;
}

.member-row > .btn-danger {
  align-self: flex-end;
}

.checkbox-group > .btn-danger {
  margin-left: auto;
}
</style>

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
    animal_type: '',
    support_notes: null,
  })
}

function removeAnimal(id) {
  animals.value = animals.value.filter((animal) => animal.animal_id !== id)
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
            <label>Support notes (optional)</label>
            <input v-model="member.support_notes" type="text" placeholder="e.g. Uses a wheelchair" />
          </div>
        </div>
        <div class="checkbox-group">
          <label class="checkbox-row">
            <input v-model="member.is_dependant" type="checkbox" />
            Dependant
          </label>
          <label class="checkbox-row">
            <input v-model="member.mobility_support_required" type="checkbox" />
            Requires mobility support
          </label>
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
            <select v-model="animal.category" required>
              <option value="pet">Pet</option>
              <option value="livestock">Livestock</option>
            </select>
          </div>
          <div class="field">
            <label>Animal type</label>
            <input v-model="animal.animal_type" type="text" placeholder="e.g. dog" />
          </div>
          <div class="field">
            <label>Name</label>
            <input v-model="animal.display_name" type="text" placeholder="e.g. Buddy" />
          </div>
          <div class="field">
            <label>Support notes (optional)</label>
            <input v-model="animal.support_notes" type="text" />
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

.member-row > .btn-danger {
  align-self: flex-end;
}

.checkbox-group > .btn-danger {
  margin-left: auto;
}
</style>

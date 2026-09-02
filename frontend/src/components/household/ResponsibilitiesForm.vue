<script setup>
import { newId } from '../../api/client'
import EmptyState from '../common/EmptyState.vue'

defineProps({ members: { type: Array, required: true } })
const responsibilities = defineModel({ required: true })

const TASK_PRESETS = [
  'Prepare emergency kit',
  'Assist children or dependants',
  'Collect pets / animals',
  'Prepare important medication / documents',
  'Drive the household',
  'Contact household members',
]

function addResponsibility() {
  responsibilities.value.push({
    responsibility_id: newId('r'),
    task_name: TASK_PRESETS[0],
    primary_member_id: null,
    backup_member_id: null,
  })
}

function selectedTask(taskName) {
  return TASK_PRESETS.includes(taskName) ? taskName : 'other'
}

function changeTask(responsibility, value) {
  responsibility.task_name = value === 'other' ? '' : value
}

function removeResponsibility(id) {
  responsibilities.value = responsibilities.value.filter((r) => r.responsibility_id !== id)
}

function isConflict(r) {
  return !!r.backup_member_id && r.backup_member_id === r.primary_member_id
}
</script>

<template>
  <section class="card">
    <div class="card-header">
      <div>
        <h3 class="card-title">Responsibilities & backup people</h3>
      </div>
      <span class="badge" :class="responsibilities.length ? 'badge-success' : 'badge-neutral'">
        {{ responsibilities.length }} assigned
      </span>
    </div>

    <EmptyState
      v-if="responsibilities.length === 0"
      title="No responsibilities assigned"
      message="Assign key tasks like driving, caring for animals or coordinating children."
    >
      <button class="btn btn-primary btn-sm" type="button" :disabled="members.length === 0" @click="addResponsibility">
        Add responsibility
      </button>
      <p v-if="members.length === 0" class="hint">Add household members first.</p>
    </EmptyState>

    <template v-else>
      <div v-for="r in responsibilities" :key="r.responsibility_id" class="resp-row">
        <div class="field-grid">
          <div class="field">
            <label>Task</label>
            <select :value="selectedTask(r.task_name)" @change="changeTask(r, $event.target.value)">
              <option v-for="task in TASK_PRESETS" :key="task" :value="task">{{ task }}</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div v-if="selectedTask(r.task_name) === 'other'" class="field">
            <label>Custom task</label>
            <input v-model="r.task_name" type="text" placeholder="Describe the preparedness task" />
          </div>
          <div class="field">
            <label>Primary person</label>
            <select v-model="r.primary_member_id">
              <option :value="null">Not set</option>
              <option v-for="m in members" :key="m.member_id" :value="m.member_id">{{ m.display_name || 'Unnamed member' }}</option>
            </select>
          </div>
          <div class="field">
            <label>Backup person</label>
            <select v-model="r.backup_member_id">
              <option :value="null">Not set</option>
              <option v-for="m in members" :key="m.member_id" :value="m.member_id">{{ m.display_name || 'Unnamed member' }}</option>
            </select>
            <span v-if="isConflict(r)" class="field-error">Backup must be a different person from the primary.</span>
          </div>
        </div>
        <button class="btn btn-danger btn-sm" type="button" @click="removeResponsibility(r.responsibility_id)">Remove</button>
      </div>
      <button class="btn btn-ghost btn-sm" type="button" @click="addResponsibility">+ Add another responsibility</button>
    </template>
  </section>
</template>

<style scoped>
.resp-row {
  padding: 1rem 0;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.resp-row > .btn-danger {
  align-self: flex-end;
}

.hint {
  font-size: 0.875rem;
  color: var(--color-text-muted);
}
</style>

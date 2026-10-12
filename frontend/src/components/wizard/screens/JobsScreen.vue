<script setup>
import { TASK_PRESETS } from '../../../wizard/options.js'
import { memberTitle } from '../../../wizard/labels.js'
import { addJob, setJobMain, setTaskChoice, taskChoice } from '../../../wizard/formActions.js'
import { removeResponsibility } from '../../../wizard/wizardDraft.js'
import { focusAfterRender } from '../../../wizard/focus.js'
import SelectField from '../fields/SelectField.vue'
import TextField from '../fields/TextField.vue'

const props = defineProps({
  plan: { type: Object, required: true },
  errors: { type: Object, default: () => ({}) },
})
const err = (field) => props.errors[field] ?? ''
const TASK_OPTIONS = [['', 'Choose a job'], ...TASK_PRESETS.map((task) => [task, task]), ['other', 'Something else']]
function addOneJob() {
  addJob(props.plan)
  focusAfterRender(`resp:${props.plan.responsibilities.length - 1}:task`)
}
function dropJob(index) {
  removeResponsibility(props.plan, index)
  focusAfterRender('add-job')
}
const people = () => props.plan.members.map((member, index) => [member.member_id, memberTitle(props.plan, index)])
const backupOptions = (job) => [['', 'No one yet'], ...people().filter(([id]) => id !== job.primary_member_id)]
</script>

<template>
  <div class="screen">
    <p v-if="!plan.members.length" class="notice">Add the people in your household first. Then come back here to say who does what.</p>
    <template v-else>
      <fieldset v-for="(job, i) in plan.responsibilities" :key="job.responsibility_id" class="card-box">
        <legend>Job {{ i + 1 }}</legend>
        <SelectField
          :id="`resp:${i}:task`"
          label="What is one job that has to happen?"
          :model-value="taskChoice(job)"
          :options="TASK_OPTIONS"
          @update:model-value="setTaskChoice(job, $event)"
        />
        <TextField
          v-if="taskChoice(job) === 'other'"
          :id="`resp:${i}:task_custom`"
          :model-value="job.task_name.trim() ? job.task_name : ''"
          label="What is the job?"
          placeholder="e.g. Feed the chickens"
          :max-length="100"
          :error="err(`resp:${i}:task_custom`)"
          @update:model-value="job.task_name = $event === '' ? ' ' : $event"
        />
        <SelectField
          :id="`resp:${i}:primary`"
          label="Who does it?"
          :model-value="job.primary_member_id ?? ''"
          :options="[['', 'Not decided yet'], ...people()]"
          @update:model-value="setJobMain(job, $event)"
        />
        <SelectField
          :id="`resp:${i}:backup`"
          label="Who covers it if they cannot?"
          :model-value="job.backup_member_id ?? ''"
          :options="backupOptions(job)"
          :error="err(`resp:${i}:backup`)"
          @update:model-value="job.backup_member_id = $event || null"
        />
        <button type="button" class="btn btn-danger btn-sm" @click="dropJob(i)">Remove this job</button>
      </fieldset>
      <button id="add-job" type="button" class="btn btn-ghost" @click="addOneJob">Add another job</button>
    </template>
  </div>
</template>

<style scoped>
.screen { display: grid; gap: 1rem; }
.notice { color: var(--color-text-muted); }
.card-box { border: 2px solid var(--color-border-strong); border-radius: 16px; display: grid; gap: 0.9rem; margin: 0; min-width: 0; padding: 1rem; }
.card-box legend { font-weight: 800; padding: 0 0.4rem; }
</style>

import { TASK_PRESETS } from '../options.js'
import { memberTitle } from '../labels.js'
import { question } from '../step.js'
import { responsibilityAt } from '../wizardDraft.js'

const SECTION = 'responsibilities'

export function responsibilitySteps(plan) {
  if (!plan.members.length) {
    return [question(SECTION, 'resp:none', 'notice', 'Add the people in your household first', {
      helper: 'Once they are added, come back here to say who does what.',
    })]
  }

  const people = plan.members.map((member, index) => [member.member_id, memberTitle(plan, index)])
  const count = Math.max(plan.responsibilities.length, 1)
  const steps = []

  for (let i = 0; i < count; i += 1) {
    const item = plan.responsibilities[i]

    steps.push(question(SECTION, `resp:${i}:task`, 'choice', i === 0 ? 'What is one job that has to happen?' : 'What is the next job?', {
      options: [...TASK_PRESETS.map((task) => [task, task]), ['other', 'Something else']],
      read: (p) => {
        const name = p.responsibilities[i]?.task_name
        if (!p.responsibilities[i]) return ''
        return TASK_PRESETS.includes(name) ? name : 'other'
      },
      write: (p, value) => {
        responsibilityAt(p, i).task_name = value === 'other' ? '' : value
      },
    }))

    if (item && !TASK_PRESETS.includes(item.task_name)) {
      steps.push(question(SECTION, `resp:${i}:task_custom`, 'text', 'What is the job?', {
        placeholder: 'e.g. Feed the chickens',
        maxLength: 100,
        optional: false,
        read: (p) => p.responsibilities[i]?.task_name ?? '',
        write: (p, value) => { responsibilityAt(p, i).task_name = value.trim() },
        validate: (value) => (value.trim() ? null : 'Please describe the task.'),
      }))
    }

    steps.push(question(SECTION, `resp:${i}:primary`, 'choice', 'Who does it?', {
      options: [['', 'Not decided yet'], ...people],
      read: (p) => p.responsibilities[i]?.primary_member_id ?? '',
      write: (p, value) => { responsibilityAt(p, i).primary_member_id = value || null },
    }))

    steps.push(question(SECTION, `resp:${i}:backup`, 'choice', 'Who covers it if they cannot?', {
      options: [['', 'No one yet'], ...people.filter(([id]) => id !== item?.primary_member_id)],
      read: (p) => p.responsibilities[i]?.backup_member_id ?? '',
      write: (p, value) => { responsibilityAt(p, i).backup_member_id = value || null },
      validate: (value, p) => (
        value && value === p.responsibilities[i]?.primary_member_id
          ? 'Choose someone other than the main person.'
          : null
      ),
    }))
  }

  const last = count - 1
  if (plan.responsibilities[last]?.task_name?.trim()) {
    steps.push(question(SECTION, `resp:${last}:more`, 'yesno', 'Is there another job to cover?', {
      read: () => false,
      write: (p, value) => { if (value) responsibilityAt(p, count) },
    }))
  }

  return steps
}

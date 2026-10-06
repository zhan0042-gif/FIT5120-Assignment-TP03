import { ANIMAL_CATEGORIES, ANIMAL_TYPES, RELATIONSHIPS } from '../options.js'
import { memberLabel } from '../labels.js'
import { question } from '../step.js'
import { animalAt, memberAt, removeAnimal, removeMember } from '../wizardDraft.js'

const SECTION = 'household_profile'

const HELP_OPTIONS = [
  ['dependant', 'Depends on someone else to leave, such as a young child'],
  ['mobility', 'Needs help moving or getting into a vehicle'],
]

export function householdProfileSteps(plan) {
  const steps = []
  const memberCount = Math.max(plan.members.length, 1)

  for (let i = 0; i < memberCount; i += 1) {
    const member = plan.members[i]
    const label = memberLabel(plan, i)

    steps.push(question(SECTION, `member:${i}:name`, 'text', i === 0 ? 'What is your name?' : 'What is their name?', {
      placeholder: 'e.g. Maya',
      maxLength: 100,
      remove: member
        ? { label: 'Remove this person', run: (p) => removeMember(p, p.members[i]?.member_id) }
        : undefined,
      read: (p) => p.members[i]?.display_name ?? '',
      write: (p, value) => {
        const created = !p.members[i]
        const target = memberAt(p, i)
        target.display_name = value.trim()
        if (created && i === 0 && target.relationship === null) target.relationship = 'self'
      },
    }))

    if (i > 0) {
      steps.push(question(SECTION, `member:${i}:relationship`, 'choice', `How is ${label} related to you?`, {
        options: [['', 'Prefer not to say'], ...RELATIONSHIPS.filter(([value]) => value !== 'self')],
        read: (p) => p.members[i]?.relationship ?? '',
        write: (p, value) => { memberAt(p, i).relationship = value || null },
      }))
    }

    if (member?.relationship === 'other') {
      steps.push(question(SECTION, `member:${i}:relationship_other`, 'text', `How would you describe ${label}?`, {
        placeholder: 'e.g. Neighbour',
        maxLength: 100,
        read: (p) => p.members[i]?.relationship_other ?? '',
        write: (p, value) => { memberAt(p, i).relationship_other = value.trim() || null },
      }))
    }

    steps.push(question(
      SECTION,
      `member:${i}:help`,
      'multi',
      i === 0 ? 'Do you need any extra help to leave?' : `Does ${label} need any extra help to leave?`,
      {
        helper: 'Tick any that apply. Skip if none do.',
        options: HELP_OPTIONS,
        read: (p) => {
          const m = p.members[i]
          return [m?.is_dependant && 'dependant', m?.mobility_support_required && 'mobility'].filter(Boolean)
        },
        write: (p, values) => {
          const m = memberAt(p, i)
          m.is_dependant = values.includes('dependant')
          m.mobility_support_required = values.includes('mobility')
        },
      },
    ))

    if (member?.is_dependant || member?.mobility_support_required) {
      steps.push(question(SECTION, `member:${i}:support_notes`, 'text', `Is there anything else we should know about ${label}?`, {
        placeholder: 'e.g. Needs medication prepared',
        read: (p) => p.members[i]?.support_notes ?? '',
        write: (p, value) => { memberAt(p, i).support_notes = value.trim() || null },
      }))
    }
  }

  const last = memberCount - 1
  if (plan.members[last]?.display_name?.trim()) {
    steps.push(question(SECTION, `member:${last}:more`, 'yesno', 'Is there anyone else in your household?', {
      read: () => null,
      write: (p, value) => { if (value) memberAt(p, memberCount) },
    }))
  }

  steps.push(question(SECTION, 'animals:any', 'yesno', 'Do any animals leave with you?', {
    helper: 'Pets or livestock. Skip if you have none.',
    read: (p) => (p.animals.length > 0 ? true : null),
    write: (p, value) => {
      if (value) animalAt(p, 0)
      else p.animals.splice(0)
    },
  }))

  const animalCount = plan.animals.length
  for (let i = 0; i < animalCount; i += 1) {
    const animal = plan.animals[i]
    steps.push(question(SECTION, `animal:${i}:category`, 'choice', 'Is this a pet or livestock?', {
      options: ANIMAL_CATEGORIES,
      remove: { label: 'Remove this animal', run: (p) => removeAnimal(p, i) },
      read: (p) => p.animals[i]?.category ?? '',
      write: (p, value) => {
        const target = animalAt(p, i)
        // The same category again (Next on a pre-filled question) must keep the type.
        if (target.category === value) return
        target.category = value
        target.animal_type = ANIMAL_TYPES[value][0][0]
        target.animal_type_other = null
      },
    }))
    steps.push(question(SECTION, `animal:${i}:type`, 'choice', 'What kind of animal is it?', {
      options: ANIMAL_TYPES[animal.category] ?? ANIMAL_TYPES.pet,
      read: (p) => p.animals[i]?.animal_type ?? '',
      write: (p, value) => {
        const target = animalAt(p, i)
        target.animal_type = value
        if (value !== 'other') target.animal_type_other = null
      },
    }))
    if (animal.animal_type === 'other') {
      steps.push(question(SECTION, `animal:${i}:type_other`, 'text', 'What kind of animal?', {
        placeholder: 'e.g. Ferret',
        maxLength: 100,
        optional: false,
        read: (p) => p.animals[i]?.animal_type_other ?? '',
        write: (p, value) => { animalAt(p, i).animal_type_other = value.trim() || null },
        validate: (value) => (value.trim() ? null : 'Please describe the animal.'),
      }))
    }
    steps.push(question(SECTION, `animal:${i}:quantity`, 'number', 'How many?', {
      min: 1,
      read: (p) => p.animals[i]?.quantity ?? 1,
      write: (p, value) => { animalAt(p, i).quantity = Number(value) },
      validate: (value) => (Number.isInteger(Number(value)) && Number(value) >= 1 ? null : 'Enter a whole number of at least 1.'),
    }))
  }

  if (animalCount > 0) {
    const lastAnimal = animalCount - 1
    steps.push(question(SECTION, `animal:${lastAnimal}:more`, 'yesno', 'Is there another animal?', {
      read: () => null,
      write: (p, value) => { if (value) animalAt(p, animalCount) },
    }))
  }

  return steps
}

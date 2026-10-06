import { USUAL_LOCATION_KINDS } from '../options.js'
import { memberLabel } from '../labels.js'
import { question } from '../step.js'
import { memberAt, selectUsualAddress, setUsualAddress, setUsualKind } from '../wizardDraft.js'

const SECTION = 'member_locations'

export function memberLocationSteps(plan) {
  if (!plan.members.length) {
    return [question(SECTION, 'locations:none', 'notice', 'Add the people in your household first', {
      helper: 'Once they are added, come back here to say where each person is during the day.',
    })]
  }

  const steps = []
  plan.members.forEach((member, i) => {
    const label = memberLabel(plan, i)
    steps.push(question(
      SECTION,
      `location:${i}:kind`,
      'choice',
      i === 0 ? 'Where are you during the day?' : `Where is ${label} during the day?`,
      {
        options: [['', 'Not sure'], ...USUAL_LOCATION_KINDS],
        read: (p) => p.members[i]?.usual_location?.kind ?? '',
        write: (p, value) => setUsualKind(memberAt(p, i), value),
      },
    ))
    if (member.usual_location) {
      steps.push(question(SECTION, `location:${i}:address`, 'address', 'What is the address?', {
        helper: 'Pick a suggestion, or type it in if it is not listed.',
        read: (p) => p.members[i]?.usual_location?.address ?? '',
        write: (p, value) => {
          const target = p.members[i]
          if (target?.usual_location) setUsualAddress(target, value)
        },
        select: (p, suggestion) => {
          const target = p.members[i]
          if (target?.usual_location) selectUsualAddress(target, suggestion)
        },
      }))
    }
  })
  return steps
}

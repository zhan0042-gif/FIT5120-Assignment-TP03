import { question } from '../step.js'
import { primaryDestination, selectDestinationAddress, setDestinationAddress } from '../wizardDraft.js'

const SECTION = 'primary_destination'

export function primaryDestinationSteps(plan) {
  const place = plan.arrangements?.primary_destination ?? null
  const steps = [question(SECTION, 'place:name', 'text', 'Where would you go?', {
    helper: 'A name you would recognise, such as "Nan\'s house".',
    placeholder: "e.g. Relative's house",
    maxLength: 100,
    read: (p) => p.arrangements?.primary_destination?.display_name ?? '',
    write: (p, value) => { primaryDestination(p).display_name = value.trim() },
  })]

  if (place) {
    steps.push(question(SECTION, 'place:address', 'address', 'What is the address?', {
      helper: 'Pick a suggestion, or type it in if it is not listed.',
      read: (p) => p.arrangements?.primary_destination?.address ?? '',
      write: (p, value) => {
        const target = p.arrangements?.primary_destination
        if (target) setDestinationAddress(target, value)
      },
      select: (p, suggestion) => {
        const target = p.arrangements?.primary_destination
        if (target) selectDestinationAddress(target, suggestion)
      },
    }))
  }

  steps.push(question(SECTION, 'place:meeting', 'text', 'If your household is separated, where would you meet?', {
    helper: 'Optional.',
    placeholder: 'e.g. Front gate',
    maxLength: 200,
    read: (p) => p.arrangements?.meeting_point ?? '',
    write: (p, value) => {
      p.arrangements ??= {}
      p.arrangements.meeting_point = value.trim() || null
    },
  }))

  return steps
}

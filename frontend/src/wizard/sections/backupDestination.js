import { question } from '../step.js'
import { backupAt, backupDestination, selectDestinationAddress, setDestinationAddress } from '../wizardDraft.js'

const SECTION = 'backup_destination'

export function backupDestinationSteps(plan) {
  const backups = plan.arrangements?.backup_arrangements ?? []
  const count = Math.max(backups.length, 1)
  const steps = []

  for (let i = 0; i < count; i += 1) {
    const place = backups[i]?.destination ?? null

    steps.push(question(
      SECTION,
      `backupplace:${i}:name`,
      'text',
      i === 0 ? 'If you could not go there, where would you go instead?' : 'Where else could you go?',
      {
        placeholder: 'e.g. Community centre',
        maxLength: 100,
        read: (p) => p.arrangements?.backup_arrangements?.[i]?.destination?.display_name ?? '',
        write: (p, value) => { backupDestination(p, i).display_name = value.trim() },
      },
    ))

    if (place) {
      steps.push(question(SECTION, `backupplace:${i}:address`, 'address', 'What is the address?', {
        helper: 'Pick a suggestion, or type it in if it is not listed.',
        read: (p) => p.arrangements?.backup_arrangements?.[i]?.destination?.address ?? '',
        write: (p, value) => {
          const target = p.arrangements?.backup_arrangements?.[i]?.destination
          if (target) setDestinationAddress(target, value)
        },
        select: (p, suggestion) => {
          const target = p.arrangements?.backup_arrangements?.[i]?.destination
          if (target) selectDestinationAddress(target, suggestion)
        },
      }))
    }
  }

  const last = count - 1
  if (backups[last]?.destination?.display_name?.trim()) {
    steps.push(question(SECTION, `backupplace:${last}:more`, 'yesno', 'Is there another place you could go?', {
      read: () => false,
      write: (p, value) => { if (value) backupAt(p, count) },
    }))
  }

  return steps
}

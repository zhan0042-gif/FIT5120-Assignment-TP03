import { transportLabel } from '../options.js'
import { question } from '../step.js'
import { backupAt } from '../wizardDraft.js'

const SECTION = 'backup_transport'

export function backupTransportSteps(plan) {
  // With no private transport the backend already counts this section complete.
  if (plan.has_private_transport === false) return []

  const primary = plan.arrangements?.primary_transport_id ?? null
  const candidates = plan.transports.filter((t) => t.transport_id !== primary)

  if (!candidates.length) {
    return [question(SECTION, 'backup:none', 'choice', 'If your main vehicle cannot be used, which would you take?', {
      helper: 'You have not added a second vehicle yet.',
      options: [],
      addVehicle: true,
      read: () => '',
      write: () => {},
    })]
  }

  const backups = plan.arrangements?.backup_arrangements ?? []
  const count = Math.max(backups.length, 1)
  const steps = []

  for (let i = 0; i < count; i += 1) {
    steps.push(question(
      SECTION,
      `backup:${i}:transport`,
      'choice',
      i === 0 ? 'If your main vehicle cannot be used, which would you take?' : 'Which other vehicle could you use?',
      {
        options: [['', 'Not sure yet'], ...candidates.map((t) => [t.transport_id, transportLabel(t)])],
        read: (p) => p.arrangements?.backup_arrangements?.[i]?.transport_id ?? '',
        write: (p, value) => { backupAt(p, i).transport_id = value || null },
      },
    ))
  }

  const last = count - 1
  const assigned = backups.filter((backup) => backup.transport_id).length
  if (backups[last]?.transport_id && assigned < candidates.length) {
    steps.push(question(SECTION, `backup:${last}:more`, 'yesno', 'Is there another vehicle you could use?', {
      read: () => null,
      write: (p, value) => { if (value) backupAt(p, count) },
    }))
  }

  return steps
}

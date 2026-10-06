import { TRANSPORT_TYPES, transportLabel } from '../options.js'
import { memberTitle } from '../labels.js'
import { question } from '../step.js'
import { removePrivateTransports, removeTransport, transportAt } from '../wizardDraft.js'

const SECTION = 'transport'

export function transportSteps(plan) {
  const steps = [question(SECTION, 'transport:has', 'yesno', 'Do you have a vehicle you would leave in?', {
    read: (p) => (p.has_private_transport === undefined ? null : p.has_private_transport),
    write: (p, value) => {
      p.has_private_transport = value
      if (value) {
        transportAt(p, 0)
      } else {
        // The backend rejects "no private transport" beside private vehicle
        // records, and only counts it complete while no primary vehicle is set.
        removePrivateTransports(p)
        p.arrangements ??= {}
        p.arrangements.primary_transport_id = null
      }
    },
  })]

  if (plan.has_private_transport !== true) return steps

  const count = Math.max(plan.transports.length, 1)
  for (let i = 0; i < count; i += 1) {
    const vehicle = plan.transports[i]

    steps.push(question(SECTION, `vehicle:${i}:type`, 'choice', i === 0 ? 'What kind of vehicle is it?' : 'What kind of vehicle is the next one?', {
      options: TRANSPORT_TYPES,
      remove: vehicle
        ? { label: 'Remove this vehicle', run: (p) => removeTransport(p, p.transports[i]?.transport_id) }
        : undefined,
      read: (p) => p.transports[i]?.transport_type ?? '',
      write: (p, value) => {
        const target = transportAt(p, i)
        target.transport_type = value
        if (value !== 'other') target.transport_type_other = null
      },
    }))

    if (vehicle?.transport_type === 'other') {
      steps.push(question(SECTION, `vehicle:${i}:type_other`, 'text', 'What kind of vehicle?', {
        placeholder: 'e.g. Tractor',
        maxLength: 100,
        optional: false,
        read: (p) => p.transports[i]?.transport_type_other ?? '',
        write: (p, value) => { transportAt(p, i).transport_type_other = value.trim() || null },
        validate: (value) => (value.trim() ? null : 'Please describe the vehicle.'),
      }))
    }

    steps.push(question(SECTION, `vehicle:${i}:name`, 'text', 'What do you call it?', {
      helper: 'For example "Dad\'s ute". Optional.',
      placeholder: 'Optional',
      maxLength: 100,
      read: (p) => p.transports[i]?.display_name ?? '',
      write: (p, value) => { transportAt(p, i).display_name = value.trim() },
    }))

    if (plan.members.length) {
      steps.push(question(SECTION, `vehicle:${i}:drivers`, 'multi', 'Who can drive it?', {
        helper: 'Tick everyone who could drive it. Skip if you are not sure.',
        options: plan.members.map((member, index) => [member.member_id, memberTitle(plan, index)]),
        read: (p) => p.transports[i]?.driver_member_ids ?? [],
        write: (p, values) => { transportAt(p, i).driver_member_ids = [...values] },
      }))
    }
  }

  const last = count - 1
  steps.push(question(SECTION, `vehicle:${last}:more`, 'yesno', 'Is there another vehicle?', {
    read: () => null,
    write: (p, value) => { if (value) transportAt(p, count) },
  }))

  if (plan.transports.length) {
    steps.push(question(SECTION, 'transport:primary', 'choice', 'Which one would you take first?', {
      options: [['', 'Not sure yet'], ...plan.transports.map((t) => [t.transport_id, transportLabel(t)])],
      read: (p) => p.arrangements?.primary_transport_id ?? '',
      write: (p, value) => {
        p.arrangements ??= {}
        p.arrangements.primary_transport_id = value || null
      },
    }))
  }

  return steps
}

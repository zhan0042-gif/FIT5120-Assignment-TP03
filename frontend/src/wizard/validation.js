const blankText = (value) => !String(value ?? '').trim()

function memberIsBlank(member) {
  return blankText(member.display_name) && !member.is_dependant && !member.mobility_support_required
    && blankText(member.support_notes) && blankText(member.relationship_other) && !member.usual_location
    && (member.relationship === null || member.relationship === 'self')
}

const destinationIsBlank = (place) => !place || (blankText(place.display_name) && blankText(place.address))

const jobIsBlank = (job) => blankText(job.task_name) && !job.primary_member_id && !job.backup_member_id

// Drops cards that were opened but never filled in, and trims typed names. Only
// people, jobs, the destination and backup places can be blank: an animal or a
// vehicle card holds default values and counts as filled.
export function finalisePlan(plan) {
  plan.members = plan.members.filter((member) => !memberIsBlank(member))
  for (const member of plan.members) member.display_name = (member.display_name ?? '').trim()
  for (const vehicle of plan.transports) vehicle.display_name = (vehicle.display_name ?? '').trim()
  plan.responsibilities = plan.responsibilities.filter((job) => !jobIsBlank(job))
  for (const job of plan.responsibilities) {
    if (!blankText(job.task_name)) job.task_name = job.task_name.trim()
  }
  const arrangements = (plan.arrangements ??= {})
  if (destinationIsBlank(arrangements.primary_destination)) arrangements.primary_destination = null
  else arrangements.primary_destination.display_name = (arrangements.primary_destination.display_name ?? '').trim()
  const backups = arrangements.backup_arrangements ?? []
  for (const entry of backups) {
    if (destinationIsBlank(entry.destination)) entry.destination = null
    else entry.destination.display_name = (entry.destination.display_name ?? '').trim()
  }
  arrangements.backup_arrangements = backups.filter((entry) => entry.transport_id || entry.destination)
  return plan
}

export const finalisedClone = (plan) => finalisePlan(JSON.parse(JSON.stringify(plan)))

// What blocks a save. Everything else may be left blank: an incomplete plan is
// always saveable. Each item is { field, message }; `field` is the id of the
// control to focus.
export function validateScreen(plan, screenId) {
  const errors = []
  const add = (field, message) => errors.push({ field, message })

  if (screenId === 'household') {
    plan.animals.forEach((animal, i) => {
      if (animal.animal_type === 'other' && blankText(animal.animal_type_other)) {
        add(`animal:${i}:type_other`, 'Please describe the animal.')
      }
      const quantity = Number(animal.quantity)
      if (!Number.isInteger(quantity) || quantity < 1) {
        add(`animal:${i}:quantity`, 'Enter a whole number of at least 1.')
      }
    })
  }

  if (screenId === 'vehicles') {
    plan.transports.forEach((vehicle, i) => {
      if (vehicle.transport_type === 'other' && blankText(vehicle.transport_type_other)) {
        add(`vehicle:${i}:type_other`, 'Please describe the vehicle.')
      }
    })
  }

  if (screenId === 'jobs') {
    plan.responsibilities.forEach((job, i) => {
      const name = job.task_name ?? ''
      if (name !== '' && blankText(name)) add(`resp:${i}:task_custom`, 'Please describe the task.')
      if (job.backup_member_id && job.backup_member_id === job.primary_member_id) {
        add(`resp:${i}:backup`, 'Choose someone other than the main person.')
      }
    })
  }

  return errors
}

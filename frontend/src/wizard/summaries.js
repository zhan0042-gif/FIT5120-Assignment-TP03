import { transportLabel } from './options.js'
import { memberTitle } from './labels.js'

const plural = (count, word) => `${count} ${word}${count === 1 ? '' : 's'}`

export function describeSection(plan, sectionId) {
  const arrangements = plan.arrangements ?? {}
  const backups = arrangements.backup_arrangements ?? []

  switch (sectionId) {
    case 'household_profile': {
      if (!plan.members.length) return 'No one added yet'
      const names = plan.members.map((_, index) => memberTitle(plan, index)).join(', ')
      return plan.animals.length ? `${names}. ${plural(plan.animals.length, 'animal')}` : names
    }
    case 'member_locations': {
      if (!plan.members.length) return 'No one added yet'
      const placed = plan.members.filter((member) => member.usual_location).length
      return `${placed} of ${plan.members.length} ${placed === 1 && plan.members.length === 1 ? 'person has' : 'people have'} a daytime place`
    }
    case 'transport': {
      if (plan.has_private_transport === false) return 'No private vehicle'
      if (!plan.transports.length) return 'Not answered yet'
      const labels = plan.transports.map(transportLabel).join(', ')
      const primary = plan.transports.find((t) => t.transport_id === arrangements.primary_transport_id)
      return primary ? `${labels}. First choice: ${transportLabel(primary)}` : labels
    }
    case 'backup_transport': {
      if (plan.has_private_transport === false) return 'Not needed without a vehicle'
      const chosen = backups
        .map((backup) => plan.transports.find((t) => t.transport_id === backup.transport_id))
        .filter(Boolean)
      return chosen.length ? chosen.map(transportLabel).join(', ') : 'No backup vehicle yet'
    }
    case 'primary_destination': {
      const place = arrangements.primary_destination
      if (!place?.display_name) return 'No destination yet'
      return place.address ? `${place.display_name}, ${place.address}` : place.display_name
    }
    case 'backup_destination': {
      const names = backups.map((backup) => backup.destination?.display_name).filter(Boolean)
      return names.length ? names.join(', ') : 'No backup place yet'
    }
    case 'responsibilities':
      return plan.responsibilities.length ? plural(plan.responsibilities.length, 'job') : 'No jobs yet'
    default:
      return ''
  }
}

import type { HouseholdPlan } from '../types/household'

export function createEmptyHouseholdPlan(): HouseholdPlan {
  return {
    members: [],
    animals: [],
    transports: [],
    arrangements: {
      primary_transport_id: null,
      backup_transport_id: null,
      primary_destination: null,
      backup_destination: null,
      meeting_point: null,
    },
    responsibilities: [],
  }
}

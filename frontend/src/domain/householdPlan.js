export function createEmptyHouseholdPlan() {
  return {
    members: [],
    animals: [],
    has_private_transport: null,
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

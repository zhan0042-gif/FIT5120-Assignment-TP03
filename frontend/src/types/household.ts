// Mirrors the Household Plan JSON contract (Iteration 1 — Frontend 分工与数据清单 v0.1, section 3/4)

export interface HouseholdMember {
  member_id: string
  display_name: string
  is_dependant: boolean
  mobility_support_required: boolean
  support_notes: string | null
}

export type AnimalCategory = 'pet' | 'livestock'

export interface Animal {
  animal_id: string
  category: AnimalCategory
  animal_type: string
  display_name: string
  support_notes: string | null
}

export type TransportType = 'car' | 'other' | 'none'

export interface Transport {
  transport_id: string
  transport_type: TransportType
  display_name: string | null
  driver_member_ids: string[]
}

export interface Destination {
  destination_id: string
  display_name: string
  address: string | null
}

export interface Arrangements {
  primary_transport_id: string | null
  backup_transport_id: string | null
  primary_destination: Destination | null
  backup_destination: Destination | null
  meeting_point: string | null
}

export interface Responsibility {
  responsibility_id: string
  task_name: string
  primary_member_id: string | null
  backup_member_id: string | null
}

export interface HouseholdPlan {
  members: HouseholdMember[]
  animals: Animal[]
  transports: Transport[]
  arrangements: Arrangements
  responsibilities: Responsibility[]
}

export interface HouseholdCreate {
  display_name?: string | null
}

export interface HouseholdCreated {
  household_id: string
}

export type SectionStatus = 'complete' | 'needs_information'
export type CompletionSectionName =
  | 'household_profile'
  | 'transport'
  | 'backup_transport'
  | 'primary_destination'
  | 'backup_destination'
  | 'responsibilities'

export interface CompletionSection {
  section: CompletionSectionName
  status: SectionStatus
}

export type ImmediateCheckName =
  | 'missing_backup_transport'
  | 'missing_backup_destination'
  | 'missing_backup_person'
  | 'shared_transport_resource'

export interface ImmediateCheck {
  check: ImmediateCheckName
  section: 'backup_transport' | 'backup_destination' | 'responsibilities'
  status: 'warning'
  message: string
}

export interface PlanCompletion {
  overall_status: SectionStatus
  sections: CompletionSection[]
  immediate_checks: ImmediateCheck[]
}

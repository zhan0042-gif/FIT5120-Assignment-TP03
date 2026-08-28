// Mirrors Local Context / Preparation Support contracts (Epic 2, US2.1-US2.3)

import type { CompletionSectionName } from './household'

export interface ResolvedLocation {
  address: string
  latitude: number
  longitude: number
}

export interface LocationRequest {
  address: string
}

export interface BushfireContext {
  is_bushfire_prone_area: boolean
  fire_district: string
}

export type FireDangerLevel = 'No Rating' | 'Moderate' | 'High' | 'Extreme' | 'Catastrophic'

export interface AvailableFireDanger {
  availability: 'available'
  today: FireDangerLevel
  tomorrow: FireDangerLevel
  day_3: FireDangerLevel
  day_4: FireDangerLevel
  source_updated_at: string
  source_url: string | null
  message: null
}

export interface UnavailableFireDanger {
  availability: 'unavailable'
  today: null
  tomorrow: null
  day_3: null
  day_4: null
  source_updated_at: null
  source_url: null
  message: string
}

export type FireDangerContext = AvailableFireDanger | UnavailableFireDanger

export interface Weather {
  temperature_c: number
  relative_humidity: number
  wind_speed_kmh: number
  wind_direction: string
  observed_at: string
  station_name: string
}

export interface EnvironmentalContext {
  fire_history_summary: string | null
  vegetation_context: string | null
  terrain_context: string | null
}

export interface LocalContext {
  location: ResolvedLocation
  bushfire_context: BushfireContext
  fire_danger: FireDangerContext
  weather: Weather
  environmental_context: EnvironmentalContext
}

export type PreparationSupportStatus = 'up_to_date' | 'review_recommended'

export interface PreparationSupport {
  status: PreparationSupportStatus
  message: string
  sections_to_review: CompletionSectionName[]
}

// Mirrors Local Context / Preparation Support contracts (Epic 2, US2.1-US2.3)

export interface ResolvedLocation {
  address: string
  latitude: number
  longitude: number
}

export interface BushfireContext {
  is_bushfire_prone_area: boolean
  fire_district: string
}

export type FireDangerLevel = 'No Rating' | 'Moderate' | 'High' | 'Extreme' | 'Catastrophic'

export interface FireDanger {
  today: FireDangerLevel
  tomorrow: FireDangerLevel
  day_3: FireDangerLevel
  day_4: FireDangerLevel
  source_updated_at: string
}

export interface Weather {
  temperature_c: number
  relative_humidity: number
  wind_speed_kmh: number
  wind_direction: string
  forecast_time: string
}

export interface EnvironmentalContext {
  vegetation: string | null
  terrain: string | null
}

export interface LocalContext {
  location: ResolvedLocation
  bushfire_context: BushfireContext
  fire_danger: FireDanger
  weather: Weather
  environmental_context: EnvironmentalContext
}

export type PreparationSupportStatus = 'up_to_date' | 'review_recommended'

export interface PreparationSupport {
  status: PreparationSupportStatus
  message: string
  sections_to_review: string[]
}

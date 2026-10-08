// The named parts of pages the assistant can jump to. The ids and routes must match
// backend/app/content/voice_sections.json (a test checks it). Each part is found on screen
// by a `data-voice-section="<id with hyphens>"` attribute on its element.

export const SECTIONS = [
  { id: 'safety_guidance', route: '/safety-insights', spoken: 'the safety guidance' },
  { id: 'fire_danger_patterns', route: '/safety-insights', spoken: 'the historical fire danger pattern' },
  { id: 'plan_summary', route: '/overview', spoken: 'the household plan summary' },
  { id: 'current_conditions', route: '/map', spoken: 'the current conditions' },
  { id: 'household_address', route: '/map', spoken: 'the household address' },
  { id: 'fire_history', route: '/map', spoken: 'the fire history' },
  { id: 'rendezvous', route: '/scenarios', spoken: 'the meet-up simulation' },
  { id: 'travel_map', route: '/travel-readiness', spoken: 'the travel map' },
  { id: 'travel_disruptions', route: '/travel-readiness', spoken: 'the reported disruptions' },
]

export const sectionKey = (id) => id.replaceAll('_', '-')

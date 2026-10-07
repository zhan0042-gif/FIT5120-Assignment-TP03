// One handler per voice action. A handler navigates and reads; none of them saves,
// edits or deletes. Every read handler first opens the page that shows the same
// figures, so what is spoken is also on screen. Handlers return the sentence to say
// and, for read-outs, a label the server is told so "say that again" can be understood.

import { EMERGENCY_MESSAGE, NO_MATCH_MESSAGE } from '../utils/safetyGuidanceCopy.js'
import { VOICE_NOTHING_TO_REPEAT, VOICE_UNAVAILABLE } from '../utils/voiceCopy.js'
import {
  fireDangerReadout,
  fireHistoryReadout,
  planCompletionReadout,
  travelDisruptionsReadout,
  weatherReadout,
} from './readouts.js'

const PAGE_LABELS = {
  welcome: 'welcome',
  overview: 'overview',
  'plan-builder': 'my plan',
  'fire-map': 'fire map',
  'travel-readiness': 'travel readiness',
  'scenario-tester': 'test my plan',
}

export function pageLabel(routeName) {
  return PAGE_LABELS[routeName] ?? 'other'
}

const NAVIGATION = {
  open_overview: ['/overview', 'Opening the overview.'],
  open_plan: ['/plan', 'Opening your plan.'],
  open_fire_map: ['/map', 'Opening the fire map.'],
  open_scenarios: ['/scenarios', 'Opening Test My Plan.'],
  open_travel_readiness: ['/travel-readiness', 'Opening travel readiness.'],
}

const FIXED_SAFETY_REPLIES = {
  emergency: EMERGENCY_MESSAGE,
  no_match: NO_MATCH_MESSAGE,
  unavailable: VOICE_UNAVAILABLE,
}

export function createHandlers({
  router,
  householdStore,
  localContextStore,
  fireMapStore,
  travelStore,
  safetyStore,
  getLastText,
}) {
  const handlers = {}

  for (const [action, [path, spoken]] of Object.entries(NAVIGATION)) {
    handlers[action] = async () => {
      await router.push(path)
      return { spoken }
    }
  }

  handlers.go_back = async () => {
    router.back()
    return { spoken: 'Going back.' }
  }

  handlers.repeat_last = async () => ({ spoken: getLastText() || VOICE_NOTHING_TO_REPEAT })

  // The overview page loads the saved location itself when it mounts; do the same if
  // that has not happened yet. Only load the context once a location exists, so a
  // failed or empty location load keeps its own status instead of being overwritten.
  async function loadOverviewContext() {
    await router.push('/overview')
    if (!localContextStore.location) await localContextStore.init()
    if (localContextStore.location) await localContextStore.loadContext()
  }

  handlers.read_weather = async () => {
    await loadOverviewContext()
    return {
      label: 'weather',
      spoken: weatherReadout({
        status: localContextStore.contextStatus,
        weather: localContextStore.context?.weather ?? null,
      }),
    }
  }

  handlers.read_fire_danger = async () => {
    await loadOverviewContext()
    return {
      label: 'fire danger',
      spoken: fireDangerReadout({
        status: localContextStore.contextStatus,
        fireDanger: localContextStore.context?.fire_danger ?? null,
      }),
    }
  }

  handlers.read_plan_completion = async () => {
    await router.push('/overview')
    await householdStore.loadCompletion()
    return {
      label: 'plan completion',
      spoken: planCompletionReadout({
        status: householdStore.completionStatus,
        completion: householdStore.completion,
      }),
    }
  }

  handlers.show_fire_history = async () => {
    await router.push('/map')
    await fireMapStore.loadFirePoints()
    return {
      label: 'fire history',
      spoken: fireHistoryReadout({
        status: fireMapStore.status,
        totalCount: fireMapStore.totalCount,
        searchRadiusKm: fireMapStore.searchRadiusKm,
        mostRecentFire: fireMapStore.mostRecentFire,
        nearestFire: fireMapStore.nearestFire,
      }),
    }
  }

  handlers.check_travel_disruptions = async () => {
    await router.push('/scenarios')
    await travelStore.load(await householdStore.ensureHousehold())
    return {
      label: 'road disruptions',
      spoken: travelDisruptionsReadout({ status: travelStore.status, result: travelStore.result }),
    }
  }

  handlers.ask_safety_question = async ({ utterance }) => {
    // The reviewed text and its CFA source appear in the safety chat on the overview.
    if (router.currentRoute.value.name !== 'overview') await router.push('/overview')
    if (safetyStore.status !== 'success') {
      await safetyStore.loadFor(() => householdStore.ensureHousehold())
    }
    const before = safetyStore.messages.length
    const sent = await safetyStore.askTyped(householdStore.householdId, utterance)
    if (!sent) return { spoken: VOICE_UNAVAILABLE }

    const replies = safetyStore.messages.slice(before).filter((message) => message.role === 'assistant')
    const spoken = replies
      .map((reply) =>
        reply.kind ? FIXED_SAFETY_REPLIES[reply.kind] : safetyStore.entriesById[reply.entryId]?.answer,
      )
      .filter(Boolean)
      .join(' ')
    return spoken ? { label: 'safety answer', spoken } : { spoken: VOICE_UNAVAILABLE }
  }

  return handlers
}

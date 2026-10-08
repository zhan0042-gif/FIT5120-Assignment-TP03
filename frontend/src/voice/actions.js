// One handler per voice action. A handler navigates and reads; none of them saves,
// edits or deletes. Every read handler first opens the page that shows the same
// figures, so what is spoken is also on screen. Handlers return the sentence to say
// and, for read-outs, a label the server is told so "say that again" can be understood.

import { nextTick } from 'vue'
import { EMERGENCY_MESSAGE, NO_MATCH_MESSAGE } from '../utils/safetyGuidanceCopy.js'
import { VOICE_NOTHING_TO_REPEAT, VOICE_UNAVAILABLE } from '../utils/voiceCopy.js'
import {
  fireDangerReadout,
  fireHistoryReadout,
  planCompletionReadout,
  travelDisruptionsReadout,
  weatherReadout,
} from './readouts.js'
import { SECTIONS, sectionKey } from './sections.js'

const PAGE_LABELS = {
  welcome: 'welcome',
  overview: 'overview',
  'safety-insights': 'safety insights',
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
  open_safety_insights: ['/safety-insights', 'Opening safety insights.'],
  open_plan: ['/plan', 'Opening your plan.'],
  open_fire_map: ['/map', 'Opening the fire map.'],
  open_scenarios: ['/scenarios', 'Opening Test My Plan.'],
  open_travel_readiness: ['/travel-readiness', 'Opening travel readiness.'],
  open_home: ['/', 'Opening the home page.'],
}

// How far one "scroll down/up" moves, as a share of what is visible, and how close to an
// end counts as being there.
const SCROLL_STEP = 0.8
const EDGE_PX = 2
const NOTHING_TO_SCROLL = 'There is nothing more to scroll on this page.'
const SECTION_MISSING = "That part isn't on the page right now."
// A page can finish drawing a moment after it opens; look for a section for up to ~2 s.
const SECTION_POLLS = 20
const SECTION_POLL_MS = 100

// The page scrolls inside <main id="main-content">, not the window.
const defaultScroller = () => globalThis.document?.getElementById('main-content') ?? null
const defaultFindSection = (key) =>
  globalThis.document?.querySelector(`[data-voice-section="${key}"]`) ?? null
const defaultSleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const defaultBehavior = () =>
  globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'

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
  getScroller = defaultScroller,
  findSection = defaultFindSection,
  sleep = defaultSleep,
  behavior = defaultBehavior,
}) {
  const handlers = {}

  for (const [action, [path, spoken]] of Object.entries(NAVIGATION)) {
    handlers[action] = async () => {
      await router.push(path)
      return { spoken }
    }
  }

  // Scrolling and jumping only move the view; they never change data.
  function scrollHandler(direction) {
    return async () => {
      const box = getScroller()
      const room = box ? box.scrollHeight - box.clientHeight : 0
      if (!box || room <= EDGE_PX) return { spoken: NOTHING_TO_SCROLL }
      const atTop = box.scrollTop <= EDGE_PX
      const atBottom = box.scrollTop >= room - EDGE_PX
      if (direction === 'down') {
        if (atBottom) return { spoken: "You're already at the bottom of the page." }
        box.scrollBy({ top: Math.round(box.clientHeight * SCROLL_STEP), behavior: behavior() })
        return { spoken: 'Scrolling down.' }
      }
      if (direction === 'up') {
        if (atTop) return { spoken: "You're already at the top of the page." }
        box.scrollBy({ top: -Math.round(box.clientHeight * SCROLL_STEP), behavior: behavior() })
        return { spoken: 'Scrolling up.' }
      }
      box.scrollTo({ top: direction === 'top' ? 0 : box.scrollHeight, behavior: behavior() })
      return { spoken: direction === 'top' ? 'Going to the top of the page.' : 'Going to the bottom of the page.' }
    }
  }
  handlers.scroll_down = scrollHandler('down')
  handlers.scroll_up = scrollHandler('up')
  handlers.scroll_to_top = scrollHandler('top')
  handlers.scroll_to_bottom = scrollHandler('bottom')

  async function waitForSection(key) {
    await nextTick()
    for (let attempt = 0; attempt < SECTION_POLLS; attempt += 1) {
      const element = findSection(key)
      if (element) return element
      await sleep(SECTION_POLL_MS)
    }
    return findSection(key)
  }

  for (const section of SECTIONS) {
    handlers[`section_${section.id}`] = async () => {
      if (router.currentRoute.value.path !== section.route) await router.push(section.route)
      const element = await waitForSection(sectionKey(section.id))
      // Not on screen (no saved plan, not run yet, still loading): say so, never guess.
      if (!element) return { spoken: SECTION_MISSING }
      element.scrollIntoView({ block: 'start', behavior: behavior() })
      return { spoken: `Here is ${section.spoken}.` }
    }
  }

  handlers.go_back = async () => {
    router.back()
    return { spoken: 'Going back.' }
  }

  handlers.repeat_last = async () => ({ spoken: getLastText() || VOICE_NOTHING_TO_REPEAT })

  // The weather and fire danger tiles are on the fire map, which loads the saved location
  // itself when it mounts; do the same if that has not happened yet. Only load the context
  // once a location exists, so a failed or empty location load keeps its own status
  // instead of being overwritten.
  async function loadMapContext() {
    await router.push('/map')
    if (!localContextStore.location) await localContextStore.init()
    if (localContextStore.location) await localContextStore.loadContext()
  }

  handlers.read_weather = async () => {
    await loadMapContext()
    return {
      label: 'weather',
      spoken: weatherReadout({
        status: localContextStore.contextStatus,
        weather: localContextStore.context?.weather ?? null,
      }),
    }
  }

  handlers.read_fire_danger = async () => {
    await loadMapContext()
    return {
      label: 'fire danger',
      spoken: fireDangerReadout({
        status: localContextStore.contextStatus,
        fireDanger: localContextStore.context?.fire_danger ?? null,
      }),
    }
  }

  handlers.read_plan_completion = async () => {
    // My Plan's progress bar shows "N of M sections complete"; the overview no longer does.
    await router.push('/plan')
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
    // The disruptions panel is on Travel Readiness, so open that page to show what is read.
    await router.push('/travel-readiness')
    await travelStore.load(await householdStore.ensureHousehold())
    return {
      label: 'road disruptions',
      spoken: travelDisruptionsReadout({ status: travelStore.status, result: travelStore.result }),
    }
  }

  handlers.ask_safety_question = async ({ utterance }) => {
    // The reviewed text and its CFA source appear in the safety chat on Safety Insights.
    if (router.currentRoute.value.name !== 'safety-insights') {
      await router.push('/safety-insights')
      // Mounting the panel starts its own load, which clears the store and bumps its
      // revision; a question asked in that window is discarded. Wait for the mount, then
      // load last, so this load is the final revision and the question below survives.
      await nextTick()
      await safetyStore.loadFor(() => householdStore.ensureHousehold())
    } else if (safetyStore.status !== 'success') {
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

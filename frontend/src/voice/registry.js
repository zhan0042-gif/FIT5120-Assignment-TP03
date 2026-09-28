import { inject, onBeforeUnmount, provide } from 'vue'

// Components register getters, not targets. The voice store calls every getter
// once when an utterance is final, so a snapshot is always current and nothing
// has to stay reactive in between.
const targetGetters = new Map()
const contextGetters = new Map()

export const VOICE_SCOPE = Symbol('voiceScope')

export function registerTargets(getTargets) {
  const key = Symbol('targets')
  targetGetters.set(key, getTargets)
  return () => targetGetters.delete(key)
}

export function registerContext(getContext) {
  const key = Symbol('context')
  contextGetters.set(key, getContext)
  return () => contextGetters.delete(key)
}

export function snapshotTargets() {
  return [...targetGetters.values()].flatMap((getTargets) => getTargets() ?? [])
}

export function snapshotContext() {
  return Object.assign(
    { page: null, step: null },
    ...[...contextGetters.values()].map((getContext) => getContext() ?? {}),
  )
}

export function resetVoiceRegistry() {
  targetGetters.clear()
  contextGetters.clear()
}

// A section is active only when every section around it is.
export function nestedScope(parentActive, ownActive) {
  return () => parentActive() && ownActive()
}

export function provideVoiceScope(isActive) {
  const parentActive = inject(VOICE_SCOPE, () => true)
  provide(VOICE_SCOPE, nestedScope(parentActive, isActive))
}

// Hidden sections (the plan builder keeps all five mounted) offer nothing, so a
// command can never reach a field the user cannot see.
export function useVoiceCommands(getTargets) {
  const isActive = inject(VOICE_SCOPE, () => true)
  const unregister = registerTargets(() => (isActive() ? getTargets() : []))
  onBeforeUnmount(unregister)
}

export function useVoiceContext(getContext) {
  const unregister = registerContext(getContext)
  onBeforeUnmount(unregister)
}

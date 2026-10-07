<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useHouseholdStore } from '../../stores/household'
import { useLocalContextStore } from '../../stores/localContext'
import { useSafetyGuidanceStore } from '../../stores/safetyGuidance'
import { isStale } from '../../utils/guidanceFreshness'
import {
  EMERGENCY_MESSAGE,
  EMPTY_MESSAGE,
  MAX_QUESTION_LENGTH,
  NO_MATCH_MESSAGE,
  PRIVACY_NOTE,
  SAFETY_NOTICE,
  UNAVAILABLE_MESSAGE,
} from '../../utils/safetyGuidanceCopy'
import { locationNote } from '../../utils/safetyGuidanceNote'
import ErrorState from '../common/ErrorState.vue'
import LoadingState from '../common/LoadingState.vue'
import VoiceControl from './VoiceControl.vue'

const householdStore = useHouseholdStore()
const localContextStore = useLocalContextStore()
const store = useSafetyGuidanceStore()
const conversation = ref(null)
const showMore = ref(false)
const draft = ref('')

const note = computed(() =>
  locationNote({
    applied: store.locationConditionsApplied,
    locationVerified: Boolean(localContextStore.canLoadContext(localContextStore.location)),
  }),
)

function readOn(isoDate) {
  const date = new Date(`${isoDate}T00:00:00`)
  if (Number.isNaN(date.getTime())) return isoDate
  return date.toLocaleDateString('en-AU', { day: 'numeric', month: 'long', year: 'numeric' })
}

function load() {
  return store.loadFor(() => householdStore.ensureHousehold())
}

const FIXED_MESSAGES = {
  no_match: NO_MATCH_MESSAGE,
  emergency: EMERGENCY_MESSAGE,
  unavailable: UNAVAILABLE_MESSAGE,
}

function fixedMessage(kind) {
  return FIXED_MESSAGES[kind] ?? UNAVAILABLE_MESSAGE
}

async function send() {
  const sent = await store.askTyped(householdStore.householdId, draft.value)
  if (sent) draft.value = ''
}

// Keep the newest answer in view without moving the rest of the page.
watch(
  () => store.messages.length,
  async () => {
    await nextTick()
    conversation.value?.lastElementChild?.scrollIntoView?.({ block: 'nearest' })
  },
)

onMounted(load)
</script>

<template>
  <section class="card safety-chat" aria-labelledby="safety-chat-title" data-voice-section="safety-guidance">
    <h2 id="safety-chat-title" class="card-title">Safety guidance</h2>
    <p class="notice" role="note"><strong>{{ SAFETY_NOTICE }}</strong></p>
    <p class="intro">
      Pick a question to see what the Country Fire Authority advises. Answers are summarised by the FIREBREAK team
      and checked against CFA's pages. They are advice to read, not a forecast.
    </p>

    <LoadingState v-if="store.status === 'loading'" message="Loading safety guidance..." />
    <ErrorState v-else-if="store.status === 'error'" :message="store.error" @retry="load" />

    <template v-else-if="store.status === 'success'">
      <p v-if="!store.entries.length" class="empty">{{ EMPTY_MESSAGE }}</p>

      <template v-else>
        <div class="suggestions-panel">
          <h3 class="panel-title">Suggested questions</h3>
          <div class="chips">
            <button
              v-for="entry in store.suggested"
              :key="entry.id"
              class="chip"
              type="button"
              @click="store.ask(entry.id)"
            >
              {{ entry.question }}
            </button>
          </div>

          <template v-if="store.moreQuestions.length">
            <button
              class="more-toggle"
              type="button"
              :aria-expanded="showMore ? 'true' : 'false'"
              @click="showMore = !showMore"
            >
              {{ showMore ? 'Fewer questions' : 'More questions' }}
            </button>
            <div v-if="showMore" class="chips more-chips">
              <button
                v-for="entry in store.moreQuestions"
                :key="entry.id"
                class="chip"
                type="button"
                @click="store.ask(entry.id)"
              >
                {{ entry.question }}
              </button>
            </div>
          </template>

          <p v-if="note === 'verify'" class="note">
            Add and verify your household location to see guidance for bushfire-prone areas.
          </p>
          <p v-else-if="note === 'unavailable'" class="note">
            Guidance for bushfire-prone areas could not be checked right now. Try again later.
          </p>
        </div>

        <section class="chat-window" aria-labelledby="chat-window-title">
          <h3 id="chat-window-title" class="panel-title">Your conversation</h3>
          <p v-if="!store.messages.length" class="chat-empty">Your questions and answers appear here.</p>
          <div
            ref="conversation"
            class="conversation"
            :class="{ 'has-messages': store.messages.length > 0 }"
            role="log"
            aria-live="polite"
          >
            <template v-for="message in store.messages" :key="message.id">
              <div v-if="message.role === 'user'" class="message user">
                <p class="bubble">{{ message.text }}</p>
              </div>
              <div v-else-if="message.kind" class="message assistant">
                <p
                  class="bubble fixed"
                  :class="message.kind"
                  :role="message.kind === 'emergency' ? 'alert' : undefined"
                >
                  {{ fixedMessage(message.kind) }}
                </p>
              </div>
              <div v-else-if="store.entriesById[message.entryId]" class="message assistant">
                <div class="bubble">
                  <p>{{ store.entriesById[message.entryId].answer }}</p>
                  <p class="source">
                    Source:
                    <a :href="store.entriesById[message.entryId].source_url" target="_blank" rel="noopener noreferrer">{{
                      store.entriesById[message.entryId].source_name
                    }}</a>
                    · checked against the source page on {{ readOn(store.entriesById[message.entryId].retrieved_on) }}
                  </p>
                  <p v-if="isStale(store.entriesById[message.entryId].retrieved_on)" class="stale" role="note">
                    This was last checked more than six months ago. Please read the linked page for the latest advice.
                  </p>
                </div>
              </div>
            </template>
          </div>

          <VoiceControl />

          <form class="ask-form" @submit.prevent="send">
            <label class="sr-only" for="safety-question">Type your own question</label>
            <input
              id="safety-question"
              v-model="draft"
              class="ask-input"
              type="text"
              :maxlength="MAX_QUESTION_LENGTH"
              autocomplete="off"
              placeholder="Or type your own question"
            />
            <button class="ask-button" type="submit" :disabled="store.asking || !draft.trim()">
              {{ store.asking ? 'Asking…' : 'Ask' }}
            </button>
          </form>
          <p class="privacy">{{ PRIVACY_NOTE }}</p>

        </section>
      </template>
    </template>
  </section>
</template>

<style scoped>
.safety-chat { margin-top: 1.25rem; }
.notice { margin-top: 0.5rem; }
.intro, .empty, .note { color: var(--color-text-muted); margin-top: 0.5rem; }
.suggestions-panel { background: var(--color-bg-card-muted); border-radius: 0.9rem; margin-top: 1rem; padding: 0.85rem 1rem 1rem; }
.chat-window { border: 1.5px solid var(--color-border-strong); border-radius: 0.9rem; margin-top: 1rem; padding: 0.85rem 1rem 1rem; }
.panel-title { color: var(--color-text-muted); font-size: 0.8125rem; font-weight: 700; letter-spacing: 0.04em; margin: 0 0 0.6rem; text-transform: uppercase; }
.chat-empty { color: var(--color-text-muted); font-size: 0.9rem; font-style: italic; margin: 0; }
.conversation { display: grid; gap: 0.6rem; max-height: 22rem; overflow-y: auto; }
.conversation.has-messages { margin-top: 0.4rem; }
.message { display: flex; }
.message.user { justify-content: flex-end; }
.bubble { border: 1px solid var(--color-border-strong); border-radius: 0.9rem; max-width: 92%; overflow-wrap: anywhere; padding: 0.65rem 0.85rem; }
.message.user .bubble { background: var(--color-accent); border-color: var(--color-accent); color: var(--color-on-accent); }
.bubble p + p { margin-top: 0.5rem; }
.chips { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.5rem; }
.chip { background: transparent; border: 1px solid var(--color-accent); border-radius: 999px; color: var(--color-accent-ink); cursor: pointer; font: inherit; font-size: 0.9375rem; min-height: 2.75rem; padding: 0.5rem 1rem; text-align: left; }
.chip:hover { background: var(--color-accent); color: var(--color-on-accent); }
.source { color: var(--color-text-muted); font-size: 0.875rem; }
.more-toggle { background: none; border: 0; color: var(--color-accent-ink); cursor: pointer; font: inherit; font-size: 0.9375rem; margin-top: 0.6rem; min-height: 2.75rem; padding: 0.25rem 0; text-decoration: underline; }
.more-chips { margin-top: 0.4rem; }
.stale { color: var(--color-text-muted); font-size: 0.875rem; font-style: italic; }
.note { font-size: 0.9rem; margin-top: 0.75rem; }
.ask-form { border-top: 1px solid var(--color-border-strong); display: flex; gap: 0.5rem; margin-top: 0.85rem; padding-top: 0.85rem; }
.ask-input { background: var(--color-surface, transparent); border: 1px solid var(--color-border-strong); border-radius: 999px; color: inherit; flex: 1; font: inherit; font-size: 0.9375rem; min-height: 2.75rem; min-width: 0; padding: 0.45rem 1rem; }
.ask-button { background: var(--color-accent); border: 1px solid var(--color-accent); border-radius: 999px; color: var(--color-on-accent); cursor: pointer; font: inherit; font-size: 0.9375rem; font-weight: 600; min-height: 2.75rem; padding: 0.45rem 1.25rem; }
.privacy { color: var(--color-text-muted); font-size: 0.8125rem; margin-top: 0.4rem; }
.ask-button:disabled { cursor: not-allowed; opacity: 0.6; }
.bubble.emergency { border-color: var(--color-accent); font-weight: 700; }
</style>

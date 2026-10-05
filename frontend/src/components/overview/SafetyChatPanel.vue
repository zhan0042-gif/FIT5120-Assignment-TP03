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
  <section class="card safety-chat" aria-labelledby="safety-chat-title">
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
        <p class="suggestions-label">Suggested questions</p>
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

        <p v-if="note === 'verify'" class="note">
          Add and verify your household location to see guidance for bushfire-prone areas.
        </p>
        <p v-else-if="note === 'unavailable'" class="note">
          Guidance for bushfire-prone areas could not be checked right now. Try again later.
        </p>
      </template>
    </template>
  </section>
</template>

<style scoped>
.safety-chat { margin-top: 1.25rem; }
.notice { margin-top: 0.5rem; }
.intro, .empty, .note { color: var(--color-text-muted); margin-top: 0.5rem; }
.conversation { display: grid; gap: 0.6rem; max-height: 22rem; overflow-y: auto; }
.conversation.has-messages { margin-top: 1rem; }
.message { display: flex; }
.message.user { justify-content: flex-end; }
.bubble { border: 1px solid var(--color-summary-border); border-radius: 0.9rem; max-width: 92%; overflow-wrap: anywhere; padding: 0.65rem 0.85rem; }
.message.user .bubble { background: var(--color-accent-soft); color: var(--color-accent); }
.bubble p + p { margin-top: 0.5rem; }
.suggestions-label { color: var(--color-text-muted); font-size: 0.85rem; margin-top: 1rem; }
.chips { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.5rem; }
.chip { background: var(--color-accent-soft); border: 1px solid var(--color-accent); border-radius: 999px; color: var(--color-accent); cursor: pointer; font: inherit; font-size: 0.9rem; padding: 0.4rem 0.85rem; text-align: left; }
.chip:hover, .chip:focus-visible { background: var(--color-accent); color: var(--color-text-inverse); }
.source { color: var(--color-text-muted); font-size: 0.85rem; }
.more-toggle { background: none; border: 0; color: var(--color-accent); cursor: pointer; font: inherit; font-size: 0.9rem; margin-top: 0.6rem; padding: 0.25rem 0; text-decoration: underline; }
.more-chips { margin-top: 0.4rem; }
.stale { color: var(--color-text-muted); font-size: 0.85rem; font-style: italic; }
.note { font-size: 0.9rem; margin-top: 1rem; }
.sr-only { border: 0; clip: rect(0 0 0 0); height: 1px; margin: -1px; overflow: hidden; padding: 0; position: absolute; width: 1px; }
.ask-form { display: flex; gap: 0.5rem; margin-top: 1rem; }
.ask-input { background: var(--color-surface, transparent); border: 1px solid var(--color-summary-border); border-radius: 999px; color: inherit; flex: 1; font: inherit; font-size: 0.9rem; min-width: 0; padding: 0.45rem 0.9rem; }
.ask-button { background: var(--color-accent); border: 1px solid var(--color-accent); border-radius: 999px; color: var(--color-text-inverse); cursor: pointer; font: inherit; font-size: 0.9rem; padding: 0.45rem 1.1rem; }
.privacy { color: var(--color-text-muted); font-size: 0.8rem; margin-top: 0.4rem; }
.ask-button:disabled { cursor: not-allowed; opacity: 0.6; }
.bubble.emergency { border-color: var(--color-accent); font-weight: 700; }
</style>

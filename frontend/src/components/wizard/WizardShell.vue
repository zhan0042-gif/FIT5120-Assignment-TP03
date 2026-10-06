<script setup>
import { nextTick, onMounted, ref, useId, watch } from 'vue'
import AddressQuestion from './questions/AddressQuestion.vue'
import ChoiceQuestion from './questions/ChoiceQuestion.vue'
import MultiQuestion from './questions/MultiQuestion.vue'
import NumberQuestion from './questions/NumberQuestion.vue'
import TextQuestion from './questions/TextQuestion.vue'
import YesNoQuestion from './questions/YesNoQuestion.vue'

const props = defineProps({
  step: { type: Object, required: true },
  plan: { type: Object, required: true },
  error: { type: String, default: null },
  canGoBack: { type: Boolean, default: false },
})
const emit = defineEmits(['submit', 'skip', 'back', 'select', 'add-vehicle'])

const uid = useId()
const inputId = `${uid}-input`
const errorId = `${uid}-error`
const prompt = ref(null)
const value = ref(initial())

function initial() {
  return props.step.read ? props.step.read(props.plan) : null
}

// A question starts from what is already in the plan and takes focus, so a
// screen reader announces the prompt. The view re-keys the shell per question,
// so mounting is the usual path; the watcher covers a reused instance.
onMounted(() => prompt.value?.focus())
watch(() => props.step.key, async () => {
  value.value = initial()
  await nextTick()
  prompt.value?.focus()
})

const describedBy = () => (props.error ? errorId : undefined)

function submit() {
  emit('submit', props.step.key, value.value)
}

function answer(picked) {
  emit('submit', props.step.key, picked)
}
</script>

<template>
  <section class="shell" aria-labelledby="wizard-prompt">
    <h2 id="wizard-prompt" ref="prompt" class="prompt" tabindex="-1">{{ step.prompt }}</h2>
    <p v-if="step.helper" class="helper">{{ step.helper }}</p>

    <form class="body" @submit.prevent="submit">
      <template v-if="step.kind === 'text'">
        <label class="sr-only" :for="inputId">{{ step.prompt }}</label>
        <TextQuestion v-model="value" :id="inputId" :placeholder="step.placeholder ?? ''" :max-length="step.maxLength ?? 200" :described-by="describedBy()" />
      </template>

      <template v-else-if="step.kind === 'number'">
        <label class="sr-only" :for="inputId">{{ step.prompt }}</label>
        <NumberQuestion v-model="value" :id="inputId" :min="step.min ?? 0" :described-by="describedBy()" />
      </template>

      <ChoiceQuestion v-else-if="step.kind === 'choice' && step.options.length" v-model="value" :name="uid" :options="step.options" :described-by="describedBy()" @pick="answer" />

      <div v-else-if="step.kind === 'choice'" class="empty">
        <button v-if="step.addVehicle" type="button" class="btn btn-accent" @click="emit('add-vehicle')">Add another vehicle</button>
      </div>

      <MultiQuestion v-else-if="step.kind === 'multi'" v-model="value" :options="step.options" :described-by="describedBy()" />

      <AddressQuestion v-else-if="step.kind === 'address'" v-model="value" label="Address" :helper="''" @select="emit('select', step.key, $event)" />

      <YesNoQuestion v-else-if="step.kind === 'yesno'" :current="value" @answer="answer" />

      <p v-if="error" :id="errorId" class="field-error" role="alert">{{ error }}</p>

      <div class="controls">
        <button v-if="canGoBack" type="button" class="btn btn-ghost" @click="emit('back')">Back</button>
        <span class="spacer"></span>
        <template v-if="step.kind !== 'yesno'">
          <button type="button" class="btn btn-ghost" @click="emit('skip', step.key)">Skip for now</button>
          <button type="submit" class="btn btn-accent">Next</button>
        </template>
      </div>
    </form>
  </section>
</template>

<style scoped>
.shell { display: grid; gap: 1rem; }
.prompt { font-size: clamp(1.6rem, 4vw, 2.25rem); line-height: 1.15; }
.prompt:focus { outline: none; }
.helper { color: var(--color-text-muted); font-size: 1.0625rem; }
.body { display: grid; gap: 1.25rem; margin-top: 0.5rem; }
.controls { align-items: center; display: flex; flex-wrap: wrap; gap: 0.75rem; }
.spacer { flex: 1 1 0; }
.empty { display: grid; gap: 0.75rem; }
</style>

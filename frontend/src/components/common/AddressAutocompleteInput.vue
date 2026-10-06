<script setup>
import { onBeforeUnmount, ref, useId, watch } from 'vue'
import { api } from '../../api/client'

const props = defineProps({
  modelValue: { type: String, default: '' },
  label: { type: String, required: true },
  placeholder: { type: String, default: 'Start typing a Victorian street address' },
  helperText: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'select'])
const componentId = useId()
const suggestions = ref([])
const status = ref('idle')
const activeIndex = ref(-1)
let timer
let deadlineTimer
let activeController
let sequence = 0
let selectedValue = null

function meaningful(query) {
  return query.length >= 4 && /\d/.test(query) && /[a-z]/i.test(query)
}

function cancelActiveRequest() {
  if (deadlineTimer) clearTimeout(deadlineTimer)
  deadlineTimer = undefined
  if (activeController) activeController.abort()
  activeController = undefined
}

// The component is shared by household, primary-destination, and every dynamic
// backup-destination address. Debouncing limits provider traffic; `sequence`
// prevents an older response from replacing suggestions for newer text.
watch(() => props.modelValue, (value) => {
  if (value === selectedValue) {
    selectedValue = null
    return
  }
  // Any manual edit invalidates the previous candidate selection. The text is
  // still emitted because autocomplete failure must not block free-text saving.
  selectedValue = null
  if (timer) clearTimeout(timer)
  cancelActiveRequest()
  activeIndex.value = -1
  const query = value.trim()
  if (!meaningful(query)) {
    sequence += 1
    suggestions.value = []
    status.value = 'idle'
    return
  }
  status.value = 'loading'
  const request = ++sequence
  timer = setTimeout(async () => {
    const controller = new AbortController()
    activeController = controller
    deadlineTimer = setTimeout(() => controller.abort(), 6000)
    try {
      const results = await api.getAddressSuggestions(query, controller.signal)
      if (request !== sequence || props.modelValue.trim() !== query) return
      suggestions.value = results
      status.value = results.length ? 'success' : 'empty'
    } catch {
      if (request !== sequence) return
      suggestions.value = []
      status.value = 'error'
    } finally {
      if (activeController === controller) {
        if (deadlineTimer) clearTimeout(deadlineTimer)
        deadlineTimer = undefined
        activeController = undefined
      }
    }
  }, 350)
})

onBeforeUnmount(() => {
  if (timer) clearTimeout(timer)
  cancelActiveRequest()
  sequence += 1
})

function update(value) {
  emit('update:modelValue', value)
}

function select(suggestion) {
  // Selection emits the full official candidate for verification and also keeps
  // v-model text synchronized for all three address use cases.
  sequence += 1
  cancelActiveRequest()
  suggestions.value = []
  status.value = 'idle'
  activeIndex.value = -1
  selectedValue = suggestion.address
  emit('select', suggestion)
  emit('update:modelValue', suggestion.address)
}

function keydown(event) {
  // Maintain an active option separately from focus so the text input keeps
  // standard combobox keyboard behavior.
  if (!suggestions.value.length) return
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    activeIndex.value = (activeIndex.value + 1) % suggestions.value.length
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    activeIndex.value = activeIndex.value <= 0 ? suggestions.value.length - 1 : activeIndex.value - 1
  } else if (event.key === 'Enter' && activeIndex.value >= 0) {
    event.preventDefault()
    select(suggestions.value[activeIndex.value])
  } else if (event.key === 'Escape') {
    suggestions.value = []
    activeIndex.value = -1
  }
}
</script>

<template>
  <div class="address-input">
    <label :for="`${componentId}-input`">{{ label }}</label>
    <input
      :id="`${componentId}-input`"
      :value="modelValue"
      type="text"
      :placeholder="placeholder"
      autocomplete="street-address"
      :disabled="disabled"
      role="combobox"
      aria-autocomplete="list"
      :aria-controls="suggestions.length ? `${componentId}-listbox` : undefined"
      :aria-expanded="suggestions.length > 0"
      :aria-activedescendant="activeIndex >= 0 ? `${componentId}-suggestion-${activeIndex}` : undefined"
      @input="update($event.target.value)"
      @keydown="keydown"
    />
    <ul v-if="suggestions.length" :id="`${componentId}-listbox`" class="suggestion-list" role="listbox" aria-label="Victorian address suggestions">
      <li v-for="(suggestion, index) in suggestions" :id="`${componentId}-suggestion-${index}`" :key="`${suggestion.address}-${suggestion.latitude}-${suggestion.longitude}`" role="option" :aria-selected="index === activeIndex">
        <button type="button" :class="{ 'is-active': index === activeIndex }" @mousedown.prevent="select(suggestion)">
          <span>{{ suggestion.address }}</span>
          <small>{{ suggestion.suburb_or_locality }} · {{ suggestion.state }} {{ suggestion.postcode }}</small>
        </button>
      </li>
    </ul>
    <span class="field-help" role="status">
      <template v-if="status === 'loading'">Finding official Victorian addresses…</template>
      <template v-else-if="status === 'empty'">No official match yet. You can still save the address you entered.</template>
      <template v-else-if="status === 'error'">Suggestions are unavailable. You can still save the address you entered.</template>
      <template v-else-if="helperText">{{ helperText }}</template>
    </span>
  </div>
</template>

<style scoped>
.address-input {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  width: 100%;
  min-width: 0;
  gap: 0.35rem;
}
.address-input label {
  font-size: 0.875rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--color-text-muted);
}
.address-input input {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius);
  padding: 0.55rem 0.65rem;
  background: var(--color-bg-card);
  color: var(--color-text);
}
.address-input input:focus-visible {
  outline: 3px solid var(--color-focus);
  outline-offset: 1px;
}
.field-help { display: block; color: var(--color-text-muted); font-size: 0.875rem; }
.suggestion-list { position: absolute; z-index: 20; top: 100%; width: 100%; max-height: 16rem; overflow-y: auto; list-style: none; margin: 0.25rem 0 0; padding: 0; border: 1px solid var(--color-border); border-radius: var(--radius); background: var(--color-bg-card); box-shadow: 0 8px 20px rgba(0, 0, 0, 0.14); }
.suggestion-list li + li { border-top: 1px solid var(--color-border); }
.suggestion-list button { display: flex; width: 100%; flex-direction: column; gap: 0.15rem; border: 0; padding: 0.65rem 0.75rem; background: transparent; color: var(--color-text); text-align: left; cursor: pointer; }
.suggestion-list button:hover, .suggestion-list button.is-active { background: var(--color-bg-card-muted); }
.suggestion-list small { color: var(--color-text-muted); }
</style>

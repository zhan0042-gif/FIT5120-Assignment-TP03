// Builders for everything a page can offer to voice control. Every target has a
// stable id (never a person's name), a kind, a spoken label, and `run`, which
// performs it through the same code the mouse and keyboard use.

// A problem the user can fix by saying it differently. Its message is shown as-is;
// any other error from `run` is reported generically.
export class VoiceActionError extends Error {}

export function pageTarget({ id, label, go }) {
  return { id, kind: 'page', label, run: go }
}

export function commandTarget({ id, label, run }) {
  return { id, kind: 'command', label, run }
}

export function buttonTarget({ id, label, press, aliases = [], confirm = false, disabled = false }) {
  return { id, kind: 'button', label, aliases, confirm, disabled, run: press }
}

export function textTarget({ id, label, current, set }) {
  return { id, kind: 'text', label, current: current ?? '', run: set }
}

export function checkboxTarget({ id, label, current, set }) {
  return { id, kind: 'checkbox', label, current: Boolean(current), run: set }
}

// `choices` are { label, value } pairs taken from the constants the template
// renders. Repeated labels (two unnamed members) are numbered so each spoken
// option still maps to exactly one value.
export function selectTarget({ id, label, choices, current, set }) {
  const options = uniqueLabels(choices.map((choice) => choice.label))
  const valueByOption = new Map(options.map((option, index) => [option, choices[index].value]))
  const currentIndex = choices.findIndex((choice) => choice.value === current)
  return {
    id,
    kind: 'select',
    label,
    options,
    current: currentIndex === -1 ? null : options[currentIndex],
    run: (option) => set(valueByOption.get(option)),
  }
}

export function addressTarget({ id, label, current, setText, suggestions, choose }) {
  return { id, kind: 'address', label, current: current ?? '', run: setText, suggestions, choose }
}

export function uniqueLabels(labels) {
  const used = new Set()
  return labels.map((label) => {
    let candidate = label
    for (let count = 2; used.has(candidate); count += 1) candidate = `${label} (${count})`
    used.add(candidate)
    return candidate
  })
}

// "member 2" until the row has a name, because that is how the row reads.
export function rowName(name, noun, index) {
  return name?.trim() || `${noun} ${index + 1}`
}

const NUMBER_WORDS = {
  a: 1, an: 1, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6,
  seven: 7, eight: 8, nine: 9, ten: 10, eleven: 11, twelve: 12,
}

export function spokenWholeNumber(text) {
  const word = String(text).trim().toLowerCase()
  const value = NUMBER_WORDS[word] ?? (word === '' ? Number.NaN : Number(word))
  if (!Number.isInteger(value) || value < 1) {
    throw new VoiceActionError('Say the quantity as a whole number, such as 2.')
  }
  return value
}

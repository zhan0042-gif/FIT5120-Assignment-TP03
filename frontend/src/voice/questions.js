import { uniqueLabels } from './targets.js'

export const NONE_OF_THESE = 'none of these'
export const NO_SPAN = '(none)'
export const NO_SUGGESTION = 'none'
// The backend accepts 100 options per question; one is NONE_OF_THESE.
export const MAX_COMMANDS = 99

const MAX_QUESTIONS = 100
const MAX_OPTIONS = 100
const MAX_SPAN_WORDS = 8
const MAX_CURRENT = 500
const MAX_SUGGESTIONS = 9
const ORDINALS = ['first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth', 'ninth']

export function commandPhrase(target) {
  switch (target.kind) {
    case 'page':
      return `go to ${target.label}`
    case 'button':
      return target.aliases?.length
        ? `press ${target.label}, or say ${target.aliases.join(', or say ')}`
        : `press ${target.label}`
    case 'select':
      return `set ${target.label}`
    case 'text':
      return `fill in ${target.label}`
    case 'checkbox':
      return `tick or untick ${target.label}`
    case 'address':
      return `enter the address for ${target.label}`
    default:
      return target.label
  }
}

// One phrase per target; the phrases are the options the judge chooses among,
// so each must name exactly one target. Registration order decides what is kept
// when a page offers too much: the layout's pages and scroll commands come first.
export function buildCatalogue(targets) {
  const kept = targets.slice(0, MAX_COMMANDS)
  const phrases = uniqueLabels(kept.map(commandPhrase))
  return kept.map((target, index) => ({ phrase: phrases[index], target }))
}

function cleanWord(word) {
  return word.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, '')
}

// Every run of up to eight words, latest-starting first: values ("to Lan
// Nguyen") usually end the sentence, so those survive when the list is capped.
export function spanCandidates(transcript) {
  const words = transcript.split(/\s+/).map(cleanWord).filter(Boolean)
  const spans = []
  const seen = new Set()
  for (let start = words.length - 1; start >= 0; start -= 1) {
    const last = Math.min(words.length, start + MAX_SPAN_WORDS)
    for (let end = start + 1; end <= last; end += 1) {
      const span = words.slice(start, end).join(' ')
      if (!seen.has(span)) {
        seen.add(span)
        spans.push(span)
      }
    }
  }
  return [...spans.slice(0, MAX_OPTIONS - 1), NO_SPAN]
}

export function suggestionOptions(suggestions) {
  const numbered = suggestions
    .slice(0, MAX_SUGGESTIONS)
    .map((text, index) => `${index + 1} ${ORDINALS[index]}: ${text}`)
  return [...numbered, NO_SUGGESTION]
}

function describeTarget(target) {
  const summary = { id: target.id, kind: target.kind, label: target.label }
  if (target.current !== undefined && target.current !== null && target.current !== '') {
    summary.current = String(target.current).slice(0, MAX_CURRENT)
  }
  return summary
}

const yesNo = (id) => ({ id, type: 'yes_no', options: [] })

export function buildBatch({ transcript, targets, context, mode = 'normal', choosing = [] }) {
  const catalogue = mode === 'normal' ? buildCatalogue(targets) : []
  const state = {
    page: context?.page ?? 'unknown',
    step: context?.step ?? null,
    mode,
    transcript,
    targets: targets.slice(0, MAX_COMMANDS).map(describeTarget),
  }

  if (mode === 'confirming') {
    return { state, questions: [yesNo('confirm'), yesNo('stop')], catalogue }
  }
  if (mode === 'choosing') {
    const suggestion = { id: 'suggestion', type: 'pick_one', options: suggestionOptions(choosing) }
    return { state, questions: [suggestion, yesNo('stop')], catalogue }
  }

  // Every select's value is asked up front, so any command costs exactly one call.
  const optionQuestions = catalogue
    .filter((entry) => entry.target.kind === 'select')
    .slice(0, MAX_QUESTIONS - 4)
    .map((entry) => ({ id: `option:${entry.target.id}`, type: 'pick_one', options: entry.target.options }))

  const questions = [
    { id: 'command', type: 'pick_one', options: [...catalogue.map((entry) => entry.phrase), NONE_OF_THESE] },
    ...optionQuestions,
    { id: 'span', type: 'pick_one', options: spanCandidates(transcript) },
    yesNo('checked'),
    yesNo('stop'),
  ]
  return { state, questions, catalogue }
}

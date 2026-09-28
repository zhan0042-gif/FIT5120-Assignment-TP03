import { NONE_OF_THESE, NO_SPAN, NO_SUGGESTION } from './questions.js'

// Starting values. The turn log exists to replace them with measured ones.
export const ACT_AT = 0.85
export const ASK_AT = 0.5

function byId(answers) {
  return new Map(answers.map((answer) => [answer.id, answer]))
}

function stopRequested(answers) {
  const stop = answers.get('stop')
  return stop?.answer === 'yes' && stop.probability >= ASK_AT
}

// Replacing something the user already typed is never done on a guess about
// which row they meant: rows look alike ("Name (Minh)", "Name (member 2)").
function overwrites(target, value) {
  return Boolean(target.current) && target.current !== value
}

function settle(action, confidence, mustConfirm) {
  if (confidence < ASK_AT) return { type: 'reject' }
  if (mustConfirm || confidence < ACT_AT) return { type: 'confirm', action }
  return { type: 'execute', action }
}

export function decideCommand(answerList, catalogue) {
  const answers = byId(answerList)
  if (stopRequested(answers)) return { type: 'stop' }

  const command = answers.get('command')
  if (!command || command.answer === NONE_OF_THESE) return { type: 'reject' }
  const entry = catalogue.find((item) => item.phrase === command.answer)
  if (!entry) return { type: 'reject' }
  const { target } = entry

  // Addresses are long and one misheard word is a different street: always
  // dictated, never lifted out of a sentence.
  if (target.kind === 'address') {
    return command.probability >= ASK_AT ? { type: 'dictate', target } : { type: 'reject' }
  }

  if (target.kind === 'text') {
    const span = answers.get('span')
    const usable = span && span.answer !== NO_SPAN && span.probability >= ACT_AT
    if (!usable) {
      return command.probability >= ASK_AT ? { type: 'dictate', target } : { type: 'reject' }
    }
    return settle(
      { kind: 'text', target, value: span.answer },
      Math.min(command.probability, span.probability),
      overwrites(target, span.answer),
    )
  }

  if (target.kind === 'select') {
    const option = answers.get(`option:${target.id}`)
    if (!option) return { type: 'reject' }
    return settle(
      { kind: 'select', target, value: option.answer },
      Math.min(command.probability, option.probability),
      false,
    )
  }

  if (target.kind === 'checkbox') {
    const checked = answers.get('checked')
    if (!checked) return { type: 'reject' }
    return settle(
      { kind: 'checkbox', target, value: checked.answer === 'yes' },
      Math.min(command.probability, checked.probability),
      false,
    )
  }

  return settle({ kind: target.kind, target, value: null }, command.probability, target.confirm === true)
}

export function decideConfirmation(answerList) {
  const answers = byId(answerList)
  if (stopRequested(answers)) return { type: 'stop' }
  const confirm = answers.get('confirm')
  if (confirm?.answer === 'yes' && confirm.probability >= ACT_AT) return { type: 'execute' }
  if (confirm?.answer === 'no' && confirm.probability >= ASK_AT) return { type: 'cancel' }
  return { type: 'unclear' }
}

export function decideSuggestion(answerList) {
  const answers = byId(answerList)
  if (stopRequested(answers)) return { type: 'stop' }
  const suggestion = answers.get('suggestion')
  if (!suggestion || suggestion.probability < ACT_AT) return { type: 'unclear' }
  if (suggestion.answer === NO_SUGGESTION) return { type: 'keep' }
  const index = Number.parseInt(suggestion.answer, 10) - 1
  return Number.isInteger(index) && index >= 0 ? { type: 'choose', index } : { type: 'unclear' }
}
